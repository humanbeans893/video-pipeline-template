"""Generate a browser preview and serve byte ranges correctly."""

from __future__ import annotations

import csv
import json
import subprocess
from importlib.resources import files
from pathlib import Path

from .config import PipelineError, Project
from .timeline import build_shotlist, read_shotlist
from .timeutil import parse_clock


def _prepare_audio(project: Project) -> None:
    if not project.paths.preview_audio.is_file():
        raise PipelineError(
            "build/preview_audio.wav がありません。先に synthesize を実行してください。"
        )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(project.paths.preview_audio),
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(project.paths.preview / "audio.m4a"),
        ],
        check=True,
    )


def build_preview(project: Project) -> Path:
    """Write build/preview.html and browser-friendly audio."""
    project.paths.ensure_build_dirs()
    _prepare_audio(project)
    build_shotlist(project)
    shots = read_shotlist(project)
    cuts = []
    for shot in shots:
        source = Path(shot["source"])
        if shot["kind"] == "movie":
            preview_path = project.paths.preview / f"{source.stem}.mp4"
            src = f"preview/{preview_path.name}"
            kind = "video" if preview_path.is_file() else "missing"
        else:
            src = f"figures/{source.name}"
            kind = "image" if (project.paths.figures / source.name).is_file() else "missing"
        cuts.append(
            {
                "id": shot["cut_id"],
                "start": float(shot["start_seconds"]),
                "end": float(shot["end_seconds"]),
                "kind": kind,
                "src": src,
                "label": source.stem,
            }
        )
    with project.paths.timing_csv.open(encoding="utf-8") as stream:
        timing = list(csv.DictReader(stream))
    subtitles = [
        {
            "start": parse_clock(row["start"]),
            "end": parse_clock(row["end"]),
            "speaker": row["speaker_key"],
            "text": row["text"],
            "color": project.speakers[row["speaker_key"]]["color"],
        }
        for row in timing
    ]
    total = max(item["end"] for item in cuts)
    template = (
        files("video_pipeline.templates").joinpath("preview.html").read_text(encoding="utf-8")
    )
    output = project.paths.build / "preview.html"
    output.write_text(
        template.replace("__TITLE__", str(project.config["project"]["title"]))
        .replace("__CUTS__", json.dumps(cuts, ensure_ascii=False))
        .replace("__SUBTITLES__", json.dumps(subtitles, ensure_ascii=False))
        .replace("__TOTAL__", f"{total:.3f}"),
        encoding="utf-8",
    )
    print(f"preview: {output.relative_to(project.paths.root)}")
    return output

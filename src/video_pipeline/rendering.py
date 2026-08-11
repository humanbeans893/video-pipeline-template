"""Render still and movie cuts through a stable cut-module contract."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt

from . import style
from .config import PipelineError, Project
from .timeline import CutSpec, build_shotlist, cue_offset, discover_cuts, read_shotlist, read_timing


@dataclass(frozen=True)
class RenderContext:
    """Information exposed to a cut's draw(t, context) function."""

    project: Project
    cut_id: str
    duration: float
    start_seconds: float

    def line_start(self, line_id: str) -> float:
        """Return one line's start offset relative to this cut."""
        row = next((item for item in read_timing(self.project) if item["id"] == line_id), None)
        if row is None:
            raise PipelineError(f"line id がありません: {line_id}")
        if str(row["cut"]).zfill(2) != self.cut_id:
            raise PipelineError(f"line {line_id} は cut {self.cut_id} に属していません")
        return float(row["start_seconds"]) - self.start_seconds

    def cue(self, line_id: str, reading_prefix: str) -> float:
        """Return a cached VOICEVOX phrase cue relative to this cut."""
        return cue_offset(self.project, self.cut_id, line_id, reading_prefix)


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except FileNotFoundError as error:
        raise PipelineError(f"コマンドが見つかりません: {command[0]}") from error
    except subprocess.CalledProcessError as error:
        raise PipelineError(f"コマンドが失敗しました: {' '.join(command[:4])}") from error


def _save_figure(figure, path: Path, project: Project) -> None:
    figure.savefig(path, dpi=project.dpi, facecolor=figure.get_facecolor())
    plt.close(figure)


def _render_still(spec: CutSpec, context: RenderContext) -> Path:
    output = context.project.paths.figures / f"{spec.name}.png"
    _save_figure(spec.draw(context.duration, context), output, context.project)
    print(f"  CUT {context.cut_id} still -> {output.relative_to(context.project.paths.root)}")
    return output


def _render_movie(spec: CutSpec, context: RenderContext) -> Path:
    project = context.project
    output = project.paths.animations / f"{spec.name}.mov"
    reveal_seconds = min(
        context.duration,
        float(project.config["video"].get("reveal_seconds", 2.6)) + 0.4,
    )
    frame_count = max(2, round(reveal_seconds * project.fps))
    with tempfile.TemporaryDirectory(prefix=f"{spec.name}_") as temp_name:
        temp = Path(temp_name)
        for frame in range(frame_count):
            timestamp = min(frame / project.fps, context.duration)
            _save_figure(
                spec.draw(timestamp, context),
                temp / f"frame_{frame:05d}.png",
                project,
            )
        rendered_seconds = frame_count / project.fps
        padding = max(context.duration - rendered_seconds, 0.0)
        filters = []
        if padding > 0.001:
            filters = ["-vf", f"tpad=stop_mode=clone:stop_duration={padding:.3f}"]
        _run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-framerate",
                str(project.fps),
                "-i",
                str(temp / "frame_%05d.png"),
                *filters,
                "-t",
                f"{context.duration:.3f}",
                "-c:v",
                "prores_ks",
                "-profile:v",
                "3",
                "-pix_fmt",
                "yuv422p10le",
                str(output),
            ]
        )
    preview = project.paths.preview / f"{spec.name}.mp4"
    _run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(output),
            "-vf",
            "scale=960:-2",
            "-c:v",
            "libx264",
            "-crf",
            "25",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-an",
            str(preview),
        ]
    )
    print(f"  CUT {context.cut_id} movie -> {output.relative_to(project.paths.root)}")
    return output


def render_cuts(project: Project, selected: str | None = None) -> list[Path]:
    """Render one cut or all cuts."""
    project.paths.ensure_build_dirs()
    style.setup_font(project)
    if not project.paths.shotlist_csv.is_file():
        build_shotlist(project)
    shotlist = read_shotlist(project)
    specs = discover_cuts(project)
    selected_id = str(selected).zfill(2) if selected is not None else None
    outputs: list[Path] = []
    found = False
    for row in shotlist:
        cut_id = str(row["cut_id"]).zfill(2)
        if selected_id is not None and cut_id != selected_id:
            continue
        found = True
        context = RenderContext(
            project=project,
            cut_id=cut_id,
            duration=float(row["required_seconds"]),
            start_seconds=float(row["start_seconds"]),
        )
        spec = specs[cut_id]
        outputs.append(
            _render_movie(spec, context) if spec.kind == "movie" else _render_still(spec, context)
        )
    if selected_id is not None and not found:
        raise PipelineError(f"cut {selected_id} がありません")
    build_shotlist(project)
    return outputs

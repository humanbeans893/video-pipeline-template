"""Timeline, cut discovery, shot-list, and speech cue helpers."""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from .config import PipelineError, Project
from .timeutil import format_frame_timecode, parse_clock


@dataclass(frozen=True)
class CutSpec:
    """Public contract implemented by one cuts/cutNN_*.py module."""

    cut_id: str
    name: str
    kind: str
    draw: Callable[[float, Any], Any]
    module: ModuleType
    path: Path


def read_timing(project: Project) -> list[dict[str, Any]]:
    """Read generated timing rows and parse numeric fields."""
    if not project.paths.timing_csv.is_file():
        raise PipelineError("build/timing.csv がありません。先に synthesize を実行してください。")
    with project.paths.timing_csv.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["start_seconds"] = parse_clock(row["start"])
        row["end_seconds"] = parse_clock(row["end"])
        row["duration_seconds"] = float(row["duration_seconds"])
    return rows


def discover_cuts(project: Project) -> dict[str, CutSpec]:
    """Import and validate cut modules."""
    discovered: dict[str, CutSpec] = {}
    for path in sorted(project.paths.cuts.glob("cut*.py")):
        if path.name == "__init__.py":
            continue
        module_name = f"video_pipeline_user_cut_{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise PipelineError(f"カットを読み込めません: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        try:
            cut_id = str(module.CUT_ID).zfill(2)
            name = str(module.NAME)
            kind = str(module.KIND)
            draw = module.draw
        except AttributeError as error:
            raise PipelineError(f"{path.name} に CUT_ID / NAME / KIND / draw が必要です") from error
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
            raise PipelineError(f"{path.name} の NAME は英数字・_・-だけにしてください")
        if kind not in {"still", "movie"}:
            raise PipelineError(f"{path.name} の KIND は still または movie です")
        if not callable(draw):
            raise PipelineError(f"{path.name} の draw が関数ではありません")
        if cut_id in discovered:
            raise PipelineError(f"CUT_ID が重複しています: {cut_id}")
        discovered[cut_id] = CutSpec(cut_id, name, kind, draw, module, path)
    return discovered


def validate_cut_contract(project: Project) -> dict[str, CutSpec]:
    """Ensure every script cut has exactly one implementation."""
    specs = discover_cuts(project)
    expected = {str(line["cut"]).zfill(2) for line in project.lines}
    missing = sorted(expected - specs.keys())
    extra = sorted(specs.keys() - expected)
    if missing:
        raise PipelineError(f"実装がないカット: {', '.join(missing)}")
    if extra:
        print(f"! 台本から参照されないカット: {', '.join(extra)}")
    return specs


def _media_duration(path: Path) -> float | None:
    if not path.is_file() or path.suffix.lower() not in {".mov", ".mp4", ".webm"}:
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def build_shotlist(project: Project) -> list[dict[str, Any]]:
    """Derive the shot list from timing data and cut modules."""
    timing = read_timing(project)
    specs = validate_cut_contract(project)
    groups: list[dict[str, Any]] = []
    for row in timing:
        cut_id = str(row["cut"]).zfill(2)
        if groups and groups[-1]["cut_id"] == cut_id:
            groups[-1]["rows"].append(row)
        else:
            groups.append({"cut_id": cut_id, "rows": [row]})
    for group in groups:
        group["start_seconds"] = group["rows"][0]["start_seconds"]
    for index, group in enumerate(groups):
        group["end_seconds"] = (
            groups[index + 1]["start_seconds"]
            if index + 1 < len(groups)
            else group["rows"][-1]["end_seconds"]
        )

    output_rows: list[dict[str, Any]] = []
    fields = [
        "cut_id",
        "start_timecode",
        "start_seconds",
        "end_seconds",
        "required_seconds",
        "media_seconds",
        "source",
        "kind",
        "status",
        "line_ids",
    ]
    project.paths.build.mkdir(parents=True, exist_ok=True)
    with project.paths.shotlist_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for group in groups:
            spec = specs[group["cut_id"]]
            extension = ".mov" if spec.kind == "movie" else ".png"
            directory = project.paths.animations if spec.kind == "movie" else project.paths.figures
            media_path = directory / f"{spec.name}{extension}"
            media_seconds = _media_duration(media_path)
            required = group["end_seconds"] - group["start_seconds"]
            status = "ready" if media_path.is_file() else "missing"
            if media_seconds is not None and media_seconds + 0.15 < required:
                status = "short"
            line_ids = [row["id"] for row in group["rows"]]
            line_label = line_ids[0] if len(line_ids) == 1 else f"{line_ids[0]}-{line_ids[-1]}"
            row = {
                "cut_id": group["cut_id"],
                "start_timecode": format_frame_timecode(group["start_seconds"], project.fps),
                "start_seconds": f"{group['start_seconds']:.3f}",
                "end_seconds": f"{group['end_seconds']:.3f}",
                "required_seconds": f"{required:.3f}",
                "media_seconds": f"{media_seconds:.3f}" if media_seconds is not None else "",
                "source": str(media_path.relative_to(project.paths.root)),
                "kind": spec.kind,
                "status": status,
                "line_ids": line_label,
            }
            writer.writerow(row)
            output_rows.append(row)
    print(f"shot list: {len(output_rows)} cuts -> {project.paths.shotlist_csv}")
    return output_rows


def read_shotlist(project: Project) -> list[dict[str, Any]]:
    """Read the generated shot list."""
    if not project.paths.shotlist_csv.is_file():
        raise PipelineError("build/shotlist.csv がありません。先に shotlist を実行してください。")
    with project.paths.shotlist_csv.open(encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def line_phrase_times(project: Project, line_id: str) -> list[tuple[float, str]]:
    """Return phrase start offsets and readings from a cached audio query."""
    path = project.paths.queries / f"{line_id}.json"
    if not path.is_file():
        raise PipelineError(f"音声クエリがありません: {path}")
    record = json.loads(path.read_text(encoding="utf-8"))
    query = record["audio_query"]
    speed = float(query.get("speedScale", 1.0))
    cursor = float(query.get("prePhonemeLength", 0.0)) / speed
    result: list[tuple[float, str]] = []
    for phrase in query.get("accent_phrases", []):
        reading = "".join(str(mora.get("text", "")) for mora in phrase.get("moras", []))
        result.append((cursor, reading))
        for mora in phrase.get("moras", []):
            cursor += (
                float(mora.get("consonant_length") or 0.0) + float(mora.get("vowel_length") or 0.0)
            ) / speed
        pause = phrase.get("pause_mora")
        if pause:
            cursor += float(pause.get("vowel_length") or 0.0) / speed
    return result


def cue_offset(project: Project, cut_id: str, line_id: str, reading_prefix: str) -> float:
    """Return the cue offset from the start of a cut."""
    timing = read_timing(project)
    row = next((item for item in timing if item["id"] == line_id), None)
    if row is None:
        raise PipelineError(f"line id がありません: {line_id}")
    normalized_cut = str(cut_id).zfill(2)
    if str(row["cut"]).zfill(2) != normalized_cut:
        raise PipelineError(f"line {line_id} は cut {normalized_cut} に属していません")
    cut_start = next(
        item["start_seconds"] for item in timing if str(item["cut"]).zfill(2) == normalized_cut
    )
    phrase = next(
        (
            offset
            for offset, reading in line_phrase_times(project, line_id)
            if reading.startswith(reading_prefix)
        ),
        None,
    )
    if phrase is None:
        available = " / ".join(reading for _, reading in line_phrase_times(project, line_id))
        raise PipelineError(f"読み『{reading_prefix}』が line {line_id} にありません: {available}")
    return float(row["start_seconds"]) - float(cut_start) + phrase


def scaffold_missing_cuts(project: Project) -> int:
    """Create minimal modules for script cuts that do not exist."""
    existing = discover_cuts(project)
    expected = sorted({str(line["cut"]).zfill(2) for line in project.lines})
    created = 0
    template = '''"""Cut {cut_id}: replace this placeholder with your own visual."""

from video_pipeline import style

CUT_ID = "{cut_id}"
NAME = "cut{cut_id}_placeholder"
KIND = "still"


def draw(t, context):
    fig, ax = style.new_frame(context.project)
    style.title(fig, "CUT {cut_id}", "Edit cuts/cut{cut_id}_placeholder.py")
    ax.text(8, 4.2, "Replace this placeholder", ha="center", va="center",
            color=style.INK, fontsize=42, fontweight="bold")
    return fig
'''
    project.paths.cuts.mkdir(parents=True, exist_ok=True)
    for cut_id in expected:
        if cut_id in existing:
            continue
        path = project.paths.cuts / f"cut{cut_id}_placeholder.py"
        path.write_text(template.format(cut_id=cut_id), encoding="utf-8")
        print(f"created: {path}")
        created += 1
    return created

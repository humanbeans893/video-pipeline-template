"""Generate a reusable transparent lip-sync character overlay."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from .config import PipelineError, Project
from .timeline import read_timing

VOWEL_SHAPES = {
    "a": (0.75, 1.0),
    "i": (1.2, 0.32),
    "u": (0.55, 0.55),
    "e": (1.0, 0.64),
    "o": (0.7, 0.88),
    "N": (0.8, 0.18),
    "cl": (1.0, 0.08),
    "pau": (1.0, 0.08),
}


def _hex(value: str, alpha: int = 255) -> tuple[int, int, int, int]:
    value = value.lstrip("#")
    return (int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16), alpha)


def _query_events(project: Project, row: dict[str, Any]) -> list[tuple[float, float, str]]:
    record_path = project.paths.queries / f"{row['id']}.json"
    if not record_path.is_file():
        raise PipelineError(f"音声クエリがありません: {record_path}")
    query = json.loads(record_path.read_text(encoding="utf-8"))["audio_query"]
    speed = float(query.get("speedScale", 1.0))
    cursor = 0.0
    events: list[tuple[float, float, str]] = []

    def append(duration: float, shape: str) -> None:
        nonlocal cursor
        if duration > 0:
            events.append((cursor, duration, shape))
            cursor += duration

    append(float(query.get("prePhonemeLength", 0.0)) / speed, "cl")
    for phrase in query.get("accent_phrases", []):
        for mora in phrase.get("moras", []):
            duration = (
                float(mora.get("consonant_length") or 0.0) + float(mora.get("vowel_length") or 0.0)
            ) / speed
            append(duration, str(mora.get("vowel", "cl")))
        pause = phrase.get("pause_mora")
        if pause:
            append(float(pause.get("vowel_length") or 0.0) / speed, "cl")
    append(float(query.get("postPhonemeLength", 0.0)) / speed, "cl")
    wanted = float(row["duration_seconds"])
    if cursor < wanted:
        append(wanted - cursor, "cl")
    if cursor > wanted and events:
        overflow = cursor - wanted
        start, duration, shape = events[-1]
        events[-1] = (start, max(duration - overflow, 0.001), shape)
    return events


def build_lip_events(project: Project) -> list[tuple[float, float, str | None, str]]:
    """Return collapsed global (start, duration, active speaker, mouth shape) events."""
    timing = read_timing(project)
    events: list[tuple[float, float, str | None, str]] = []
    cursor = 0.0
    for row in timing:
        start = float(row["start_seconds"])
        if start > cursor:
            events.append((cursor, start - cursor, None, "cl"))
        for offset, duration, shape in _query_events(project, row):
            events.append((start + offset, duration, str(row["speaker_key"]), shape))
        cursor = float(row["end_seconds"])
    total = float(timing[-1]["end_seconds"])
    if cursor < total:
        events.append((cursor, total - cursor, None, "cl"))

    collapsed: list[tuple[float, float, str | None, str]] = []
    for start, duration, speaker, shape in events:
        shape = shape if shape in VOWEL_SHAPES else "cl"
        if duration <= 0:
            continue
        if collapsed and collapsed[-1][2:] == (speaker, shape):
            old_start, old_duration, _, _ = collapsed[-1]
            collapsed[-1] = (old_start, old_duration + duration, speaker, shape)
        else:
            collapsed.append((start, duration, speaker, shape))
    return collapsed


def _avatar_positions(project: Project) -> dict[str, tuple[int, int]]:
    per_side: dict[str, list[str]] = {"left": [], "right": []}
    for key, speaker in project.speakers.items():
        per_side[str(speaker["avatar"]["side"])].append(key)
    positions: dict[str, tuple[int, int]] = {}
    size, margin, gap = 220, 45, 20
    for side, keys in per_side.items():
        for index, key in enumerate(keys):
            x = margin + index * (size + gap)
            if side == "right":
                x = project.width - margin - size - index * (size + gap)
            positions[key] = (x, project.height - margin - size)
    return positions


def _draw_state(project: Project, active: str | None, shape: str) -> Image.Image:
    canvas = Image.new("RGBA", (project.width, project.height), (0, 0, 0, 0))
    positions = _avatar_positions(project)
    for key, speaker in project.speakers.items():
        avatar = speaker["avatar"]
        is_active = key == active
        alpha = 255 if is_active else 95
        x, y = positions[key]
        size = 220
        draw = ImageDraw.Draw(canvas, "RGBA")
        body = _hex(str(avatar["body_color"]), alpha)
        accent = _hex(str(avatar["accent_color"]), alpha)
        draw.rounded_rectangle(
            (x, y + 28, x + size, y + size), radius=62, fill=body, outline=accent, width=8
        )
        draw.ellipse((x + 48, y + 76, x + 76, y + 108), fill=(12, 28, 38, alpha))
        draw.ellipse((x + 144, y + 76, x + 172, y + 108), fill=(12, 28, 38, alpha))
        width_ratio, height_ratio = VOWEL_SHAPES[shape if is_active else "cl"]
        mouth_width = 66 * width_ratio
        mouth_height = max(5, 48 * height_ratio)
        center_x, center_y = x + size / 2, y + 151
        draw.ellipse(
            (
                center_x - mouth_width / 2,
                center_y - mouth_height / 2,
                center_x + mouth_width / 2,
                center_y + mouth_height / 2,
            ),
            fill=(37, 24, 32, alpha),
        )
        if is_active:
            draw.rounded_rectangle((x + 40, y + 12, x + size - 40, y + 30), radius=8, fill=accent)
    return canvas


def build_character_overlay(project: Project) -> Path:
    """Write a transparent ProRes overlay and browser WebM preview."""
    project.paths.ensure_build_dirs()
    events = build_lip_events(project)
    if not events:
        raise PipelineError("口パク用イベントがありません")
    output = project.paths.build / "characters.mov"
    preview = project.paths.preview / "characters.webm"
    with tempfile.TemporaryDirectory(prefix="characters_") as temp_name:
        temp = Path(temp_name)
        cache: dict[tuple[str | None, str], Path] = {}
        concat = ["ffconcat version 1.0"]
        for _, duration, active, shape in events:
            state = (active, shape)
            if state not in cache:
                path = temp / f"state_{len(cache):03d}.png"
                _draw_state(project, active, shape).save(path)
                cache[state] = path
            concat.extend([f"file '{cache[state].name}'", f"duration {duration:.6f}"])
        concat.append(f"file '{cache[(events[-1][2], events[-1][3])].name}'")
        concat_path = temp / "states.txt"
        concat_path.write_text("\n".join(concat) + "\n", encoding="utf-8")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-v",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_path),
                "-r",
                str(project.fps),
                "-c:v",
                "prores_ks",
                "-profile:v",
                "4444",
                "-pix_fmt",
                "yuva444p10le",
                str(output),
            ],
            check=True,
        )
    subprocess.run(
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
            "libvpx-vp9",
            "-crf",
            "34",
            "-b:v",
            "0",
            "-auto-alt-ref",
            "0",
            "-pix_fmt",
            "yuva420p",
            "-an",
            str(preview),
        ],
        check=True,
    )
    print(f"character overlay: {len(events)} events -> {output.relative_to(project.paths.root)}")
    return output

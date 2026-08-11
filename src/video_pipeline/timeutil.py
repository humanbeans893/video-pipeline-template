"""Timecode and caption helpers."""

from __future__ import annotations

import math
import re


def format_clock(seconds: float, separator: str = ".") -> str:
    """Format seconds as HH:MM:SS.mmm."""
    milliseconds = max(0, int(round(seconds * 1000)))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{milliseconds:03d}"


def parse_clock(value: str) -> float:
    """Parse HH:MM:SS.mmm or HH:MM:SS,mmm."""
    hours, minutes, seconds = re.split(r":", value, maxsplit=2)
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))


def format_frame_timecode(seconds: float, fps: int) -> str:
    """Format seconds as HH:MM:SS:FF."""
    frames = max(0, round(seconds * fps))
    return (
        f"{frames // fps // 3600:02d}:{frames // fps // 60 % 60:02d}:"
        f"{frames // fps % 60:02d}:{frames % fps:02d}"
    )


def format_ass_time(seconds: float) -> str:
    """Format seconds as ASS H:MM:SS.cc."""
    centiseconds = max(0, math.floor(seconds * 100 + 0.5 + 1e-9))
    hours, centiseconds = divmod(centiseconds, 360_000)
    minutes, centiseconds = divmod(centiseconds, 6_000)
    secs, centiseconds = divmod(centiseconds, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centiseconds:02d}"


def split_caption(text: str, limit: int = 22) -> list[str]:
    """Split a caption at Japanese punctuation, then by length."""
    pieces: list[str] = []
    buffer = ""
    for part in re.split(r"(?<=[。、？！!?])", text):
        if not part:
            continue
        if buffer and len(buffer) + len(part) > limit:
            pieces.append(buffer)
            buffer = part
        else:
            buffer += part
    if buffer:
        pieces.append(buffer)
    result: list[str] = []
    for piece in pieces:
        while len(piece) > limit + 6:
            result.append(piece[:limit])
            piece = piece[limit:]
        if piece.strip():
            result.append(piece)
    return result

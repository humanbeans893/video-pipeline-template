"""VOICEVOX synthesis and timeline artifact generation."""

from __future__ import annotations

import csv
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
from pathlib import Path
from typing import Any

from .config import PipelineError, Project
from .timeutil import format_ass_time, format_clock, split_caption


class VoicevoxClient:
    """Small client for the two VOICEVOX endpoints used by the pipeline."""

    def __init__(self, base_url: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def wait_ready(self, max_wait: float = 30.0) -> str:
        """Wait for the engine and return its reported version."""
        deadline = time.monotonic() + max_wait
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(
                    f"{self.base_url}/version", timeout=min(self.timeout, 3)
                ) as response:
                    return response.read().decode("utf-8").strip('"')
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                last_error = error
                time.sleep(0.5)
        raise PipelineError(f"VOICEVOX に接続できません: {self.base_url} ({last_error})")

    def post(self, endpoint: str, params: dict[str, Any], body: dict | None = None) -> bytes:
        """POST to a VOICEVOX endpoint."""
        url = f"{self.base_url}{endpoint}?{urllib.parse.urlencode(params)}"
        data = json.dumps(body).encode("utf-8") if body is not None else b""
        headers = {"Content-Type": "application/json"} if body is not None else {}
        request = urllib.request.Request(url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise PipelineError(
                f"VOICEVOX {endpoint} が失敗しました: {error.code} {detail}"
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise PipelineError(f"VOICEVOX {endpoint} に接続できません: {error}") from error

    def query(self, text: str, style_id: int) -> dict[str, Any]:
        """Create an audio query."""
        return json.loads(self.post("/audio_query", {"text": text, "speaker": style_id}))

    def synthesize(self, query: dict[str, Any], style_id: int) -> bytes:
        """Synthesize one WAV file."""
        return self.post("/synthesis", {"speaker": style_id}, query)


def apply_pronunciations(text: str, pronunciations: dict[str, str]) -> str:
    """Apply deterministic surface-to-reading replacements."""
    result = text
    for surface, reading in pronunciations.items():
        result = result.replace(surface, reading)
    return result


def wav_duration(wav_bytes: bytes) -> float:
    """Return the duration of in-memory WAV bytes."""
    with wave.open(io.BytesIO(wav_bytes), "rb") as stream:
        return stream.getnframes() / float(stream.getframerate())


def query_reading(query: dict[str, Any]) -> str:
    """Render accent phrases as a compact reading audit string."""
    parts: list[str] = []
    for phrase in query.get("accent_phrases", []):
        parts.append("".join(str(mora.get("text", "")) for mora in phrase.get("moras", [])))
        if phrase.get("pause_mora"):
            parts.append("、")
    return "|".join(parts).replace("|、|", "、").replace("|、", "、")


def _write_timing(rows: list[dict[str, Any]], path: Path) -> None:
    fields = [
        "id",
        "file",
        "cut",
        "start",
        "end",
        "duration_seconds",
        "speaker_key",
        "speaker_name",
        "chapter",
        "text",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "id": row["id"],
                    "file": row["file"],
                    "cut": row["cut"],
                    "start": format_clock(row["start"]),
                    "end": format_clock(row["end"]),
                    "duration_seconds": f"{row['duration']:.3f}",
                    "speaker_key": row["speaker_key"],
                    "speaker_name": row["speaker_name"],
                    "chapter": row["chapter"],
                    "text": row["text"],
                }
            )


def _caption_segments(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for row in rows:
        pieces = split_caption(row["text"], limit)
        total_characters = max(sum(len(piece) for piece in pieces), 1)
        cursor = row["start"]
        for piece in pieces:
            duration = row["duration"] * len(piece) / total_characters
            segments.append(
                {
                    "start": cursor,
                    "end": cursor + duration,
                    "speaker_key": row["speaker_key"],
                    "text": piece,
                }
            )
            cursor += duration
    return segments


def _write_srt(segments: list[dict[str, Any]], path: Path) -> None:
    blocks = []
    for index, segment in enumerate(segments, start=1):
        blocks.append(
            f"{index}\n{format_clock(segment['start'], ',')} --> "
            f"{format_clock(segment['end'], ',')}\n{segment['text']}\n"
        )
    path.write_text("\n".join(blocks), encoding="utf-8")


def _ass_color(rgb: str) -> str:
    clean = rgb.lstrip("#")
    red, green, blue = clean[0:2], clean[2:4], clean[4:6]
    return f"&H00{blue}{green}{red}".upper()


def _ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _write_ass(project: Project, segments: list[dict[str, Any]], path: Path) -> None:
    video = project.config["video"]
    subtitles = project.config["subtitles"]
    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video['width']}",
        f"PlayResY: {video['height']}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    style_names: dict[str, str] = {}
    for index, (key, speaker) in enumerate(project.speakers.items(), start=1):
        style_name = f"Speaker{index}"
        style_names[key] = style_name
        header.append(
            f"Style: {style_name},{subtitles['font']},{subtitles['font_size']},"
            f"{_ass_color(str(speaker['color']))},&H00FFFFFF,&H00101820,&HC0000000,"
            f"-1,0,0,0,100,100,0,0,3,3,0,2,40,40,{subtitles['margin_vertical']},1"
        )
    header.extend(
        [
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    for segment in segments:
        header.append(
            f"Dialogue: 0,{format_ass_time(segment['start'])},{format_ass_time(segment['end'])},"
            f"{style_names[segment['speaker_key']]},,0,0,0,,{_ass_escape(segment['text'])}"
        )
    path.write_text("\n".join(header) + "\n", encoding="utf-8")


def _write_preview_audio(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        raise PipelineError("音声がありません")
    first_path = Path(rows[0]["wav_path"])
    with wave.open(str(first_path), "rb") as first:
        params = first.getparams()
    with wave.open(str(path), "wb") as output:
        output.setparams(params)
        for row in rows:
            with wave.open(str(row["wav_path"]), "rb") as source:
                signature = (source.getnchannels(), source.getsampwidth(), source.getframerate())
                expected = (params.nchannels, params.sampwidth, params.framerate)
                if signature != expected:
                    raise PipelineError(f"WAV 形式が一致しません: {row['file']}")
                output.writeframes(source.readframes(source.getnframes()))
            silence_frames = round(row["gap_after"] * params.framerate)
            output.writeframes(b"\x00" * silence_frames * params.sampwidth * params.nchannels)


def _write_human_files(project: Project, rows: list[dict[str, Any]]) -> None:
    readings = ["# VOICEVOX reading audit", ""]
    for row in rows:
        readings.extend([f"[{row['id']}] {row['text']}", f"      {row['reading']}", ""])
    (project.paths.build / "readings.txt").write_text("\n".join(readings), encoding="utf-8")

    chapter_titles = {str(chapter["key"]): str(chapter["title"]) for chapter in project.chapters}
    script_lines = [f"# {project.config['project']['title']}", ""]
    current_chapter: str | None = None
    for row in rows:
        if row["chapter"] != current_chapter:
            current_chapter = row["chapter"]
            script_lines.extend([f"## {chapter_titles[current_chapter]}", ""])
        script_lines.extend([f"**{row['speaker_name']}**：{row['text']}", ""])
    (project.paths.build / "script.md").write_text("\n".join(script_lines), encoding="utf-8")

    credits = sorted({str(speaker["credit"]).strip() for speaker in project.speakers.values()})
    project.paths.credits_txt.write_text("\n".join(credits) + "\n", encoding="utf-8")


def synthesize_project(project: Project) -> list[dict[str, Any]]:
    """Synthesize all lines and generate timeline artifacts."""
    project.paths.ensure_build_dirs()
    for directory, pattern in (
        (project.paths.audio, "*.wav"),
        (project.paths.queries, "*.json"),
    ):
        for stale in directory.glob(pattern):
            stale.unlink()

    voice_config = project.config["voicevox"]
    client = VoicevoxClient(str(voice_config["url"]), float(voice_config["timeout_seconds"]))
    version = client.wait_ready()
    print(f"VOICEVOX: {version}")

    rows: list[dict[str, Any]] = []
    for line in project.lines:
        line_id = str(line["id"])
        speaker_key = str(line["speaker"])
        speaker = project.speakers[speaker_key]
        style_id = int(speaker["voicevox_style_id"])
        query_text = apply_pronunciations(str(line["text"]), project.pronunciations)
        query = client.query(query_text, style_id)
        query["outputSamplingRate"] = int(voice_config["output_sampling_rate"])
        query["speedScale"] = float(voice_config["speed_scale"])
        wav_bytes = client.synthesize(query, style_id)
        filename = f"{line_id}_{speaker_key}.wav"
        wav_path = project.paths.audio / filename
        wav_path.write_bytes(wav_bytes)
        duration = wav_duration(wav_bytes)
        query_record = {
            "line_id": line_id,
            "speaker_key": speaker_key,
            "style_id": style_id,
            "query_text": query_text,
            "audio_query": query,
        }
        (project.paths.queries / f"{line_id}.json").write_text(
            json.dumps(query_record, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rows.append(
            {
                "id": line_id,
                "chapter": str(line["chapter"]),
                "speaker_key": speaker_key,
                "speaker_name": str(speaker["display_name"]),
                "text": str(line["text"]),
                "cut": str(line["cut"]),
                "file": filename,
                "wav_path": wav_path,
                "duration": duration,
                "reading": query_reading(query),
                "gap_after": float(project.config["timing"]["gap_seconds"]),
            }
        )
        print(f"  {filename:<24} {duration:5.2f}s  {str(line['text'])[:36]}")

    chapter_gap = float(project.config["timing"]["chapter_gap_seconds"])
    for previous, following in zip(rows, rows[1:], strict=False):
        if previous["chapter"] != following["chapter"]:
            previous["gap_after"] = chapter_gap
    rows[-1]["gap_after"] = 0.0

    cursor = 0.0
    for row in rows:
        row["start"] = cursor
        row["end"] = cursor + row["duration"]
        cursor = row["end"] + row["gap_after"]

    _write_timing(rows, project.paths.timing_csv)
    segments = _caption_segments(rows, int(project.config["subtitles"].get("max_characters", 22)))
    _write_srt(segments, project.paths.subtitles_srt)
    _write_ass(project, segments, project.paths.subtitles_ass)
    _write_preview_audio(rows, project.paths.preview_audio)
    _write_human_files(project, rows)

    total = rows[-1]["end"]
    target = float(project.config["project"]["target_seconds"])
    tolerance = float(project.config["project"]["tolerance_seconds"])
    marker = "✓" if abs(total - target) <= tolerance else "!"
    print(f"{marker} timeline: {total:.2f}s (target {target:.1f}s ± {tolerance:.1f}s)")
    return rows

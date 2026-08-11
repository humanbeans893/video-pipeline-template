"""Assemble rendered cuts, character overlay, audio, and subtitles."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt

from . import style
from .config import PipelineError, Project
from .timeline import build_shotlist, read_shotlist


def _ffmpeg_subtitle_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "\\\\").replace(":", r"\:").replace("'", r"\'")


def _placeholder(project: Project, cut_id: str, source: str) -> Path:
    directory = project.paths.build / "placeholders"
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / f"cut{cut_id}.png"
    figure, axis = style.new_frame(project)
    style.title(figure, f"CUT {cut_id}", "Draft placeholder")
    axis.text(8, 4.8, "素材がありません", color="#FF7F6E", fontsize=46, ha="center", va="center")
    axis.text(8, 3.8, source, color=style.MUTED, fontsize=22, ha="center", va="center")
    figure.savefig(output, dpi=project.dpi, facecolor=figure.get_facecolor())
    plt.close(figure)
    return output


def _run(command: list[str]) -> None:
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as error:
        raise PipelineError(f"FFmpeg が失敗しました: {' '.join(command[:5])}") from error


def build_movie(project: Project, draft: bool = False, subtitles: bool = True) -> Path:
    """Build the final MP4. Missing cuts are allowed only for drafts."""
    style.setup_font(project)
    build_shotlist(project)
    shots = read_shotlist(project)
    missing = [row for row in shots if row["status"] != "ready"]
    if missing and not draft:
        labels = ", ".join(f"CUT {row['cut_id']} ({row['status']})" for row in missing)
        raise PipelineError(f"完成ビルドには不足素材があります: {labels}")
    if not project.paths.preview_audio.is_file():
        raise PipelineError(
            "build/preview_audio.wav がありません。先に synthesize を実行してください。"
        )

    output = project.paths.build / ("final-draft.mp4" if draft else "final.mp4")
    width, height = project.width, project.height
    with tempfile.TemporaryDirectory(prefix="video_pipeline_") as temp_name:
        temp = Path(temp_name)
        parts: list[Path] = []
        for index, shot in enumerate(shots):
            duration = float(shot["required_seconds"])
            source = project.paths.root / shot["source"]
            kind = shot["kind"]
            if not source.is_file():
                source = _placeholder(project, shot["cut_id"], shot["source"])
                kind = "still"
            part = temp / f"part_{index:03d}.mp4"
            if kind == "still":
                command = [
                    "ffmpeg",
                    "-y",
                    "-v",
                    "error",
                    "-loop",
                    "1",
                    "-framerate",
                    str(project.fps),
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    str(source),
                ]
                video_filter = (
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={project.config['video']['background']}"
                )
            else:
                command = ["ffmpeg", "-y", "-v", "error", "-i", str(source)]
                video_filter = (
                    f"tpad=stop_mode=clone:stop_duration={duration:.3f},"
                    f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={project.config['video']['background']},"
                    f"trim=duration={duration:.3f},setpts=PTS-STARTPTS"
                )
            _run(
                command
                + [
                    "-vf",
                    video_filter,
                    "-r",
                    str(project.fps),
                    "-c:v",
                    "libx264",
                    "-crf",
                    "18",
                    "-preset",
                    "veryfast",
                    "-pix_fmt",
                    "yuv420p",
                    "-an",
                    str(part),
                ]
            )
            parts.append(part)

        concat_file = temp / "parts.txt"
        concat_file.write_text(
            "\n".join(f"file '{part.as_posix()}'" for part in parts) + "\n", encoding="utf-8"
        )
        joined = temp / "joined.mp4"
        _run(
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
                str(concat_file),
                "-c",
                "copy",
                str(joined),
            ]
        )

        command = [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-i",
            str(joined),
            "-i",
            str(project.paths.preview_audio),
        ]
        overlay = project.paths.build / "characters.mov"
        if overlay.is_file():
            command += ["-i", str(overlay)]

        filters: list[str] = []
        current = "0:v"
        if overlay.is_file():
            filters.append("[0:v][2:v]overlay=0:0:format=auto[characters]")
            current = "characters"
        if subtitles:
            if not project.paths.subtitles_ass.is_file():
                raise PipelineError("build/subtitles.ass がありません")
            filters.append(
                f"[{current}]subtitles=filename='{_ffmpeg_subtitle_path(project.paths.subtitles_ass)}'[subbed]"
            )
            current = "subbed"
        if draft:
            filters.append(f"[{current}]scale=960:-2[draft]")
            current = "draft"
        if filters:
            command += ["-filter_complex", ";".join(filters), "-map", f"[{current}]", "-map", "1:a"]
        else:
            command += ["-map", "0:v", "-map", "1:a"]
        command += [
            "-c:v",
            "libx264",
            "-crf",
            "22" if draft else "19",
            "-preset",
            "veryfast" if draft else "medium",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(output),
        ]
        _run(command)
    relative = output.relative_to(project.paths.root)
    size_mb = output.stat().st_size / 1_000_000
    print(f"movie: {relative} ({size_mb:.1f} MB)")
    return output

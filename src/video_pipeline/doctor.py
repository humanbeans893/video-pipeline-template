"""Environment diagnostics."""

from __future__ import annotations

import shutil
import subprocess

import matplotlib.font_manager as font_manager

from .audio import VoicevoxClient
from .config import PipelineError, Project
from .timeline import validate_cut_contract


def run_doctor(project: Project, check_voicevox: bool = True) -> None:
    """Fail with actionable diagnostics when a prerequisite is missing."""
    for executable in ("ffmpeg", "ffprobe"):
        path = shutil.which(executable)
        if path is None:
            raise PipelineError(f"{executable} が見つかりません")
        print(f"✓ {executable}: {path}")
    filters = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True, check=True
    ).stdout
    if " subtitles " not in filters:
        raise PipelineError("FFmpeg に subtitles/libass フィルタがありません")
    print("✓ FFmpeg subtitles filter")
    configured_font = str(project.config["subtitles"]["font"])
    available = {font.name for font in font_manager.fontManager.ttflist}
    if configured_font not in available:
        alternatives = [name for name in ("Noto Sans JP", "IPAexGothic") if name in available]
        suffix = f"（利用可能: {', '.join(alternatives)}）" if alternatives else ""
        raise PipelineError(f"字幕フォントが見つかりません: {configured_font}{suffix}")
    print(f"✓ font: {configured_font}")
    validate_cut_contract(project)
    print("✓ cut contract")
    if check_voicevox:
        config = project.config["voicevox"]
        client = VoicevoxClient(str(config["url"]), float(config["timeout_seconds"]))
        print(f"✓ VOICEVOX: {client.wait_ready()}")

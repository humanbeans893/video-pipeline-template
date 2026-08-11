"""Configuration loading and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class PipelineError(RuntimeError):
    """A user-facing pipeline error."""


@dataclass(frozen=True)
class Paths:
    """All repository paths used by the pipeline."""

    root: Path
    project_yaml: Path
    script_yaml: Path
    dictionary_yaml: Path
    cuts: Path
    assets: Path
    build: Path
    audio: Path
    queries: Path
    figures: Path
    animations: Path
    preview: Path
    timing_csv: Path
    shotlist_csv: Path
    subtitles_srt: Path
    subtitles_ass: Path
    preview_audio: Path
    credits_txt: Path

    @classmethod
    def from_root(cls, root: Path) -> Paths:
        build = root / "build"
        return cls(
            root=root,
            project_yaml=root / "project.yaml",
            script_yaml=root / "script" / "script.yaml",
            dictionary_yaml=root / "script" / "dictionary.yaml",
            cuts=root / "cuts",
            assets=root / "assets",
            build=build,
            audio=build / "audio",
            queries=build / "queries",
            figures=build / "figures",
            animations=build / "animations",
            preview=build / "preview",
            timing_csv=build / "timing.csv",
            shotlist_csv=build / "shotlist.csv",
            subtitles_srt=build / "subtitles.srt",
            subtitles_ass=build / "subtitles.ass",
            preview_audio=build / "preview_audio.wav",
            credits_txt=build / "credits.txt",
        )

    def ensure_build_dirs(self) -> None:
        for directory in (
            self.build,
            self.audio,
            self.queries,
            self.figures,
            self.animations,
            self.preview,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Project:
    """Validated project configuration and script."""

    paths: Paths
    config: dict[str, Any]
    script: dict[str, Any]
    pronunciations: dict[str, str]

    @property
    def width(self) -> int:
        return int(self.config["video"]["width"])

    @property
    def height(self) -> int:
        return int(self.config["video"]["height"])

    @property
    def fps(self) -> int:
        return int(self.config["video"]["fps"])

    @property
    def dpi(self) -> int:
        return int(self.config["video"]["dpi"])

    @property
    def speakers(self) -> dict[str, dict[str, Any]]:
        return self.config["speakers"]

    @property
    def lines(self) -> list[dict[str, Any]]:
        return self.script["lines"]

    @property
    def chapters(self) -> list[dict[str, Any]]:
        return self.script["chapters"]


def find_root(start: Path | None = None) -> Path:
    """Find the nearest directory containing project.yaml."""
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "project.yaml").is_file():
            return candidate
    raise PipelineError("project.yaml が見つかりません。リポジトリ内で実行してください。")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise PipelineError(f"必要なファイルがありません: {path}")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise PipelineError(f"YAML の最上位はマッピングにしてください: {path}")
    return loaded


def _require(mapping: dict[str, Any], keys: set[str], label: str) -> None:
    missing = sorted(keys - mapping.keys())
    if missing:
        raise PipelineError(f"{label} に必須キーがありません: {', '.join(missing)}")


def _validate_color(value: str, label: str) -> None:
    if not re.fullmatch(r"#[0-9A-Fa-f]{6}", value):
        raise PipelineError(f"{label} は #RRGGBB 形式にしてください: {value}")


def load_project(root: Path | None = None) -> Project:
    """Load and validate project files."""
    paths = Paths.from_root((root or find_root()).resolve())
    config = _read_yaml(paths.project_yaml)
    script = _read_yaml(paths.script_yaml)
    dictionary = _read_yaml(paths.dictionary_yaml)

    _require(
        config,
        {"project", "video", "voicevox", "timing", "subtitles", "speakers"},
        "project.yaml",
    )
    _require(config["project"], {"title", "target_seconds", "tolerance_seconds"}, "project")
    _require(config["video"], {"width", "height", "fps", "dpi", "background"}, "video")
    _require(
        config["voicevox"],
        {"url", "output_sampling_rate", "speed_scale", "timeout_seconds"},
        "voicevox",
    )
    _require(config["timing"], {"gap_seconds", "chapter_gap_seconds"}, "timing")
    _require(config["subtitles"], {"font", "font_size", "margin_vertical"}, "subtitles")
    if not isinstance(config["speakers"], dict) or not config["speakers"]:
        raise PipelineError("speakers を1件以上定義してください")

    width, height, fps = (
        int(config["video"]["width"]),
        int(config["video"]["height"]),
        int(config["video"]["fps"]),
    )
    if width < 320 or height < 180 or fps < 1:
        raise PipelineError("video の width / height / fps が小さすぎます")
    _validate_color(str(config["video"]["background"]), "video.background")

    for key, speaker in config["speakers"].items():
        if not isinstance(speaker, dict):
            raise PipelineError(f"speaker {key} の設定が不正です")
        _require(
            speaker,
            {"display_name", "voicevox_style_id", "color", "credit", "avatar"},
            f"speaker {key}",
        )
        _validate_color(str(speaker["color"]), f"speaker {key}.color")
        if not str(speaker["credit"]).strip():
            raise PipelineError(f"speaker {key} の credit を空にできません")
        avatar = speaker["avatar"]
        _require(avatar, {"side", "body_color", "accent_color"}, f"speaker {key}.avatar")
        if avatar["side"] not in {"left", "right"}:
            raise PipelineError(f"speaker {key}.avatar.side は left または right です")
        _validate_color(str(avatar["body_color"]), f"speaker {key}.avatar.body_color")
        _validate_color(str(avatar["accent_color"]), f"speaker {key}.avatar.accent_color")

    _require(script, {"chapters", "lines"}, "script.yaml")
    if not isinstance(script["chapters"], list) or not script["chapters"]:
        raise PipelineError("chapters を1件以上定義してください")
    if not isinstance(script["lines"], list) or not script["lines"]:
        raise PipelineError("lines を1件以上定義してください")

    chapter_keys = {str(chapter["key"]) for chapter in script["chapters"]}
    seen_ids: set[str] = set()
    seen_cuts: list[str] = []
    for index, line in enumerate(script["lines"], start=1):
        if not isinstance(line, dict):
            raise PipelineError(f"lines[{index}] が不正です")
        _require(line, {"id", "chapter", "speaker", "text", "cut"}, f"lines[{index}]")
        line_id = str(line["id"])
        if line_id in seen_ids:
            raise PipelineError(f"重複した line id: {line_id}")
        seen_ids.add(line_id)
        if str(line["chapter"]) not in chapter_keys:
            raise PipelineError(f"未定義の chapter: {line['chapter']}（id={line_id}）")
        if str(line["speaker"]) not in config["speakers"]:
            raise PipelineError(f"未定義の speaker: {line['speaker']}（id={line_id}）")
        if not str(line["text"]).strip():
            raise PipelineError(f"空のセリフがあります: id={line_id}")
        seen_cuts.append(str(line["cut"]))

    closed: set[str] = set()
    previous = seen_cuts[0]
    for cut in seen_cuts[1:]:
        if cut != previous:
            closed.add(previous)
            if cut in closed:
                raise PipelineError(f"cut {cut} が離れた位置で再登場しています")
            previous = cut

    pronunciations_raw = dictionary.get("pronunciations") or {}
    if not isinstance(pronunciations_raw, dict):
        raise PipelineError("dictionary.yaml の pronunciations はマッピングにしてください")
    pronunciations = {str(key): str(value) for key, value in pronunciations_raw.items()}
    return Project(paths=paths, config=config, script=script, pronunciations=pronunciations)

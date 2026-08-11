# video-pipeline-template

A reusable pipeline that turns a YAML script into VOICEVOX speech, subtitles, timing
metadata, a shot list, rendered cuts, lip-sync characters, a browser preview, and a final MP4.

[日本語 README](README.md)

## Requirements

- Linux, macOS, or WSL on Windows
- Python 3.11+, [uv](https://docs.astral.sh/uv/), FFmpeg, and ffprobe
- FFmpeg support for libass, H.264, ProRes, and VP9
- The `IPAexGothic` font (or configure another Japanese font such as `Noto Sans CJK JP`)
- A running [VOICEVOX ENGINE](https://github.com/VOICEVOX/voicevox_engine)

For example, using the official Docker image:

```bash
docker run --rm -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
```

Before using or publishing generated audio, read the current
[VOICEVOX software terms](https://voicevox.hiroshiba.jp/term/) and the terms of every
voice library you select. The repository does not redistribute VOICEVOX.

## Quick start

```bash
uv sync --locked --all-groups
uv run video-pipeline doctor
uv run video-pipeline all
uv run video-pipeline serve
```

Open `http://127.0.0.1:8765/preview.html`. The final video is written to
`build/final.mp4`; reusable credit text is written to `build/credits.txt`.

Run individual stages when iterating:

```bash
uv run video-pipeline validate
uv run video-pipeline synthesize
uv run video-pipeline shotlist
uv run video-pipeline render --all
uv run video-pipeline characters
uv run video-pipeline preview
uv run video-pipeline build
```

Normal builds fail on missing cuts. `build --draft` fills them with visible placeholders,
and `build --no-subs` omits burned-in subtitles.

## Project inputs

- `project.yaml`: video, VOICEVOX, subtitle, speaker, avatar, and credit settings.
- `script/script.yaml`: ordered chapters and lines with `id`, `chapter`, `speaker`, `text`, and `cut`.
- `script/dictionary.yaml`: deterministic pronunciation replacements.
- `cuts/cutNN_name.py`: editable still or movie renderers implementing `CUT_ID`, `NAME`,
  `KIND`, and `draw(t, context)`.

`context.line_start(line_id)` returns a line's start within the current cut.
`context.cue(line_id, reading_prefix)` returns an exact phrase cue from the cached VOICEVOX
audio query. Run `video-pipeline scaffold` after adding new cut IDs to create missing modules.

All generated files live under `build/` and are excluded from Git.

## Contributing and license

Issues and pull requests are welcome. The protected `main` branch requires passing CI and
a CODEOWNER review for outside contributions. See [CONTRIBUTING.md](CONTRIBUTING.md).

The original code and example configuration use the MIT License. VOICEVOX, individual voice
libraries, FFmpeg, user assets, and generated media retain their own terms; see [NOTICE.md](NOTICE.md).

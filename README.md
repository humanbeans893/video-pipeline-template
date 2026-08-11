# video-pipeline-template

YAML台本から、VOICEVOX音声、字幕、タイミング表、香盤表、カット、口パク、
ブラウザプレビュー、完成MP4までを再生成できる動画制作テンプレートです。

[English README](README.en.md)

## 特徴

- 1行のセリフを1つのWAVとして生成し、字幕と映像の時刻を同じ正本からそろえます。
- 静止画と動画を同じ `draw(t, context)` 契約で作れます。
- `context.line_start()` と `context.cue()` で、発話に合わせて要素を表示できます。
- 不足カットを一覧化し、ドラフトだけプレースホルダーで完成形を確認できます。
- Range対応のローカルサーバーで、長い音声・動画も途中へシークできます。
- 生成物はすべて `build/` に集め、Gitへコミットしません。

## 必要なもの

- Linux、macOS、またはWindows上のWSL
- Python 3.11以上と [uv](https://docs.astral.sh/uv/)
- `ffmpeg` と `ffprobe`（libass、H.264、ProRes、VP9対応）
- 日本語フォント `IPAexGothic`（`Noto Sans CJK JP` などへ変更可能）
- 起動中の [VOICEVOX ENGINE](https://github.com/VOICEVOX/voicevox_engine)

公式Dockerイメージを使う例です。

```bash
docker run --rm -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
```

VOICEVOXと各音声ライブラリの規約は、利用前と公開前に必ず確認してください。
現在のVOICEVOXソフトウェア規約では、VOICEVOXを利用したことが分かるクレジットが
必要です。詳細は[公式利用規約](https://voicevox.hiroshiba.jp/term/)を参照してください。

## 最短の使い方

```bash
uv sync --locked --all-groups
uv run video-pipeline doctor
uv run video-pipeline all
uv run video-pipeline serve
```

ブラウザで `http://127.0.0.1:8765/preview.html` を開きます。完成品は
`build/final.mp4`、クレジット文は `build/credits.txt` に出ます。

工程を分けて実行する場合:

```bash
uv run video-pipeline validate
uv run video-pipeline synthesize
uv run video-pipeline shotlist
uv run video-pipeline render --all
uv run video-pipeline characters
uv run video-pipeline preview
uv run video-pipeline build
```

`build --draft` は不足素材を仮カードで補います。通常の `build` は不足素材があれば失敗し、
未完成の動画を完成品として書き出しません。字幕を焼き込まない場合は `--no-subs` を使います。

## カスタマイズ

1. `project.yaml` で解像度、FPS、話者のVOICEVOXスタイルID、色、クレジットを変更します。
2. `script/script.yaml` の章とセリフを書き換えます。`id` と `cut` は文字列で記述します。
3. 読み間違いを `script/dictionary.yaml` に追加します。
4. `cuts/cutNN_name.py` の `draw()` を動画の内容に合わせて実装します。

カットモジュールの最小契約:

```python
from video_pipeline import style

CUT_ID = "01"
NAME = "cut01_title"
KIND = "still"  # or "movie"


def draw(t, context):
    fig, ax = style.new_frame(context.project)
    style.title(fig, "タイトル")
    return fig
```

台本へ新しい `cut` を追加した後、`uv run video-pipeline scaffold` を実行すると不足分の
雛形を作れます。

## ディレクトリ

```text
project.yaml                 動画・VOICEVOX・話者設定
script/                      台本と読み辞書
cuts/                        編集するカットモジュール
src/video_pipeline/          再利用可能なパイプライン本体
assets/                      利用者が用意する素材
build/                       全生成物（Git対象外）
tests/                       単体テスト
```

## コントリビューション

変更提案はIssueまたはPull Requestで歓迎します。`main` は保護されており、外部PRは
CODEOWNERの承認と全CIチェックの成功が必要です。手順は [CONTRIBUTING.md](CONTRIBUTING.md)
を参照してください。

## ライセンス

コードとオリジナルのサンプル設定はMIT Licenseです。VOICEVOX、各音声ライブラリ、
FFmpeg、利用者の素材、生成された音声・動画にはそれぞれ別の条件が適用されます。
[NOTICE.md](NOTICE.md)も確認してください。

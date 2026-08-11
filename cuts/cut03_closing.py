"""Closing card with reusable credit text."""

from video_pipeline import style

CUT_ID = "03"
NAME = "cut03_closing"
KIND = "still"


def draw(t, context):
    fig, ax = style.new_frame(context.project)
    style.title(fig, "次は、あなたの動画です", "台本・配色・カットを自由に置き換えてください")
    ax.text(
        8,
        4.8,
        "uv run video-pipeline all",
        color=style.WARM,
        fontsize=42,
        fontweight="bold",
        family="monospace",
        ha="center",
        va="center",
    )
    credits = "  /  ".join(
        sorted({speaker["credit"] for speaker in context.project.speakers.values()})
    )
    ax.text(8, 3.4, credits, color=style.MUTED, fontsize=21, ha="center", va="center")
    style.telop(fig, "生成物では、利用する音声ライブラリの規約を確認してください")
    return fig

"""Animated three-step workflow."""

import matplotlib.pyplot as plt

from video_pipeline import style

CUT_ID = "02"
NAME = "cut02_workflow"
KIND = "movie"


def draw(t, context):
    fig, ax = style.new_frame(context.project)
    style.title(fig, "三つの工程", "カット単位で直しながら、最後に一本へ結合")
    start = context.line_start("003")
    steps = [
        ("1", "台本", "YAML", style.WARM),
        ("2", "カット", "PNG / MOV", style.ACCENT),
        ("3", "完成", "MP4", "#FF7F6E"),
    ]
    for index, (number, title, detail, color) in enumerate(steps):
        progress = style.reveal(t, start + index * 1.0, 0.7)
        if progress <= 0.01:
            continue
        x = 1.15 + index * 5.0
        y = 3.05
        ax.add_patch(
            plt.Rectangle(
                (x, y - 0.12 * (1 - progress)),
                4.05,
                2.25,
                facecolor=style.PANEL,
                edgecolor=color,
                linewidth=4,
                alpha=progress,
            )
        )
        ax.text(
            x + 0.55, y + 1.52, number, color=color, fontsize=34, fontweight="bold", alpha=progress
        )
        ax.text(
            x + 2.02,
            y + 1.36,
            title,
            color=style.INK,
            fontsize=34,
            fontweight="bold",
            ha="center",
            alpha=progress,
        )
        ax.text(
            x + 2.02, y + 0.58, detail, color=style.MUTED, fontsize=23, ha="center", alpha=progress
        )
        if index < 2:
            ax.annotate(
                "",
                xy=(x + 4.77, y + 1.0),
                xytext=(x + 4.25, y + 1.0),
                arrowprops={"arrowstyle": "-|>", "color": style.MUTED, "linewidth": 3},
                alpha=progress,
            )
    preview_start = context.line_start("004")
    style.telop(fig, "ブラウザで音声と画のタイミングを確認", style.reveal(t, preview_start, 0.6))
    return fig

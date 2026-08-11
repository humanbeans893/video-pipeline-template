"""Opening title and a short two-speaker exchange."""

import matplotlib.pyplot as plt

from video_pipeline import style

CUT_ID = "01"
NAME = "cut01_intro"
KIND = "still"


def draw(t, context):
    fig, ax = style.new_frame(context.project)
    style.title(
        fig,
        context.project.config["project"]["title"],
        context.project.config["project"].get("subtitle", ""),
    )
    cards = [
        (2.0, 3.2, 5.5, 1.6, style.WARM, "台本を書く"),
        (8.5, 3.2, 5.5, 1.6, style.ACCENT, "音声と字幕がそろう"),
    ]
    for x, y, width, height, color, label in cards:
        ax.add_patch(
            plt.Rectangle(
                (x, y), width, height, facecolor=style.PANEL, edgecolor=color, linewidth=4
            )
        )
        ax.text(
            x + width / 2,
            y + height / 2,
            label,
            color=style.INK,
            fontsize=31,
            fontweight="bold",
            ha="center",
            va="center",
        )
    ax.annotate(
        "",
        xy=(8.1, 4.0),
        xytext=(7.8, 4.0),
        arrowprops={"arrowstyle": "-|>", "color": style.MUTED, "linewidth": 3},
    )
    style.telop(fig, "YAMLを正本にして、派生物を再生成")
    return fig

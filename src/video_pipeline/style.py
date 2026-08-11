"""Small, reusable drawing helpers for cut modules."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager as font_manager  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

from .config import Project

INK = "#D8E6EB"
MUTED = "#8DA5B5"
PANEL = "#0B2C3E"
ACCENT = "#4BC8F0"
WARM = "#FCD064"


def setup_font(project: Project) -> str:
    """Select the configured font, with portable fallbacks."""
    preferred = str(project.config["subtitles"]["font"])
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in (preferred, "Noto Sans CJK JP", "Noto Sans JP", "IPAexGothic", "DejaVu Sans"):
        if candidate in available:
            plt.rcParams["font.family"] = candidate
            plt.rcParams["axes.unicode_minus"] = False
            if candidate != preferred:
                print(f"! font fallback: {preferred} -> {candidate}")
            return candidate
    return "sans-serif"


def new_frame(project: Project):
    """Create a 16-by-9 logical drawing surface at configured resolution."""
    background = str(project.config["video"]["background"])
    fig = plt.figure(
        figsize=(project.width / project.dpi, project.height / project.dpi),
        dpi=project.dpi,
        facecolor=background,
    )
    axis = fig.add_axes((0, 0, 1, 1), facecolor=background)
    axis.set_xlim(0, 16)
    axis.set_ylim(0, 9)
    axis.set_aspect("equal")
    axis.axis("off")
    return fig, axis


def title(fig, text: str, subtitle: str = "") -> None:
    """Place a consistent title block."""
    fig.text(0.055, 0.93, text, color=INK, fontsize=44, fontweight="bold", va="top")
    if subtitle:
        fig.text(0.055, 0.855, subtitle, color=MUTED, fontsize=23, va="top")


def telop(fig, text: str, alpha: float = 1.0) -> None:
    """Place a conclusion band above the subtitle zone."""
    if alpha <= 0.01:
        return
    fig.patches.append(
        plt.Rectangle(
            (0, 0.15),
            1,
            0.13,
            transform=fig.transFigure,
            facecolor=PANEL,
            edgecolor="none",
            alpha=min(alpha, 1.0) * 0.96,
        )
    )
    fig.text(
        0.5,
        0.215,
        text,
        color=INK,
        fontsize=32,
        fontweight="bold",
        ha="center",
        va="center",
        alpha=min(alpha, 1.0),
    )


def ease(value: float) -> float:
    """Smooth a value from zero to one."""
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def reveal(now: float, start: float, duration: float = 0.7) -> float:
    """Return smooth reveal progress for a timeline interval."""
    return ease((now - start) / duration)

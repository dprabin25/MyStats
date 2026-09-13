"""
Chart-building logic for the narrative Precision/Recall/F1 app, kept
separate from the Streamlit UI so the figure can be built and tested (e.g.
saved to a file and inspected) without launching the app.

This reproduces the exact chart styling from the original
`precision_f1_recall.py` -- the CVD-validated 3-color/3-hatch palette,
fonts, DPI, gridlines, spines, legend placement, and value-label placement
-- so a chart built here is visually identical to the one already
validated by hand against the original script's output.
"""

# Force the non-interactive Agg backend BEFORE importing pyplot. Without
# this, matplotlib can auto-select a GUI backend (e.g. the macOS Cocoa/
# AppKit backend) -- which is not thread-safe and will hard-crash the
# whole Python process (a segfault, taking Streamlit down with it, not a
# catchable Python exception) the moment a chart is drawn from Streamlit's
# background thread. Agg only ever renders to an in-memory image, which is
# exactly what st.pyplot()/fig.savefig() need, so nothing is lost.
import matplotlib
matplotlib.use("Agg")

import numpy as np
import matplotlib.pyplot as plt

# Colors are the first three slots of an 8-hue categorical palette that is
# pre-validated (not eyeballed) for this exact 3-series, all-pairs-compared
# case:
#   light mode -- CVD (deutan/protan) worst pair Delta-E 9.2, worst tritan
#     9.6, normal-vision worst pair Delta-E 24.0 (>=8 / >=15 targets both
#     cleared)
#   dark mode  -- CVD worst pair Delta-E 9.4, normal-vision 20.9
# Every bar also carries a direct value label in dark text (never in the
# series color), which is the fix for the one light-mode WARN (aqua vs.
# the light surface, 2.74:1, below the 3:1 contrast floor) -- so the fill
# color never has to carry meaning on its own. Hue alone also will not
# survive a grayscale print some journals require, so each metric ALSO
# gets its own hatch texture -- a second, redundant encoding channel that
# works with no color at all.
DEFAULT_METRIC_STYLE = {
    "Precision": {"color": "#2a78d6", "hatch": ""},     # blue,  solid
    "Recall":    {"color": "#eb6834", "hatch": "///"},  # orange, diagonal
    "F1":        {"color": "#1baf7a", "hatch": "..."},  # aqua,  dotted
}
METRICS = ["Precision", "Recall", "F1"]


def build_grouped_bar_chart(results_df, title="Precision, Recall, and F1 by Narrative",
                             metric_style=None, narrative_col="Narrative"):
    """results_df must have columns [narrative_col, 'Precision', 'Recall', 'F1']
    already rounded to 2 decimals (bar heights and labels are drawn straight
    from these values, matching the original script's behavior of rounding
    before plotting, not after)."""
    metric_style = metric_style or DEFAULT_METRIC_STYLE

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["Arial", "Helvetica", "DejaVu Sans"]
    plt.rcParams["font.size"] = 11
    plt.rcParams["pdf.fonttype"] = 42   # embed as real (editable/selectable) text, not curves
    plt.rcParams["ps.fonttype"] = 42

    narrative_labels = results_df[narrative_col].tolist()
    x = np.arange(len(narrative_labels))
    n_metrics = len(METRICS)
    # Each metric gets an equal-width slot within the group, but the bar
    # itself is drawn narrower than its slot (82%) so a visible white gap
    # separates adjacent bars -- outlined bars with no gap read as one
    # continuous, overlapping shape instead of three distinct boxes.
    slot_width = 0.8 / n_metrics
    bar_width = slot_width * 0.82

    fig, ax = plt.subplots(figsize=(max(7.5, 1.5 * len(narrative_labels)), 4.5), dpi=300)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.yaxis.grid(True, color="#d9d9d9", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    for i, metric in enumerate(METRICS):
        offset = (i - (n_metrics - 1) / 2) * slot_width
        values = results_df[metric].tolist()
        style = metric_style[metric]
        bars = ax.bar(
            x + offset, values, width=bar_width, label=metric,
            facecolor="white", edgecolor=style["color"], hatch=style["hatch"],
            linewidth=1.4, zorder=3,
        )
        for rect, value in zip(bars, values):
            ax.text(
                rect.get_x() + rect.get_width() / 2, rect.get_height() + 0.02,
                f"{value:.2f}", ha="center", va="bottom", fontsize=8, color="#1a1a1a",
            )

    ax.set_ylim(0, 1.08)
    ax.set_yticks(np.arange(0, 1.01, 0.2))
    ax.set_ylabel("Score", color="#1a1a1a", fontsize=11)
    ax.set_title(title, color="#0b0b0b", fontsize=13, fontweight="bold", pad=14)
    ax.set_xticks(x)
    ax.set_xticklabels(narrative_labels, color="#1a1a1a", fontsize=10)
    ax.tick_params(axis="y", colors="#1a1a1a", labelsize=10)

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#666666")
    ax.spines["bottom"].set_linewidth(0.8)

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=n_metrics,
              frameon=False, fontsize=10)

    fig.tight_layout()
    return fig

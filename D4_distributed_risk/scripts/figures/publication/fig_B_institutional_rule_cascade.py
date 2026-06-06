"""
Figure B — DRBC drought management flowcharts

Faithful schematic recreation of the DRBC training-slide flowcharts:
  • Basin-Wide (Water Code §2.5.3.E + FFMP) — NYC storage L3–L5
  • Lower-Basin (Water Code §2.5.6) — Beltzville / Blue Marsh elevations

Output
------
figures/publication/fig_B_institutional_rule_cascade.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from _paths import FIGS, set_style
from _drbc_flowchart import draw_basin_wide, draw_lower_basin

set_style()
FIGS.mkdir(parents=True, exist_ok=True)


def make_figure():
    fig = plt.figure(figsize=(15, 17), facecolor="white")
    ax_top = fig.add_axes([0.02, 0.505, 0.96, 0.47])
    ax_bot = fig.add_axes([0.02, 0.02, 0.96, 0.47])

    # Light panel backgrounds like DRBC slide
    for ax, ylabel in ((ax_top, "Basin-wide"), (ax_bot, "Lower basin")):
        ax.set_facecolor("#fafafa")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_color("#cccccc")

    draw_basin_wide(ax_top)
    draw_lower_basin(ax_bot)

    fig.suptitle(
        "Figure B — DRBC drought management flowcharts (institutional rule cascade)",
        fontsize=13, fontweight="bold", y=0.995,
    )
    fig.text(
        0.5, 0.005,
        "Adapted from DRBC Drought Management Plans · "
        "Basin-wide plan keyed to NYC combined storage · "
        "Lower-basin plan keyed to Beltzville + Blue Marsh pool elevations",
        ha="center", fontsize=8, color="#555555",
    )
    return fig


def main():
    fig = make_figure()
    out = FIGS / "fig_B_institutional_rule_cascade.png"
    fig.savefig(out, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()

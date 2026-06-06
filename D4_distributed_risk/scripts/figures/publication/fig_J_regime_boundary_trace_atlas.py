"""
Figure J — Regime-Boundary Trace Atlas

Pairs the phase-diagram state space with representative daily traces on
different sides of the regime boundary: diversion-limited, storage-limited,
co-limited, and near-boundary switching cases.

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet
D4_distributed_risk/results/baseline/member_*/obs_pub_*.hdf5

Output
------
figures/publication/fig_J_regime_boundary_trace_atlas.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

from _paths import PATHS, REGIME_COLORS, FIGS, set_style
from _figure_helpers import (
    LB_CAPACITY_MG,
    LB_CONSERVATION_FRAC,
    IERQ_MAX_MG,
    IERQ_EXHAUSTION_MG,
    REGIME_NAMES,
    load_member_regime_trace,
    select_regime_archetypes,
)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

TRACE_WINDOW = ("1985-01-01", "1995-12-31")
REGIME_FILL = {
    0: REGIME_COLORS["normal"] + "33",
    1: REGIME_COLORS["NYC-limited"] + "44",
    2: REGIME_COLORS["LB-limited"] + "44",
    3: REGIME_COLORS["co-limited"] + "44",
}
HIGHLIGHT_COLORS = ["#2166ac", "#4dac26", "#ca0020", "#f4a582", "#7b3294", "#984ea3"]


def _shade_regimes(ax, dates, labels, ylo, yhi):
    """Paint regime-colored vertical bands on a time-axis panel."""
    vals = labels.loc[dates[0]:dates[-1]].values
    idx = labels.loc[dates[0]:dates[-1]].index
    if len(vals) == 0:
        return
    start = 0
    for i in range(1, len(vals)):
        if vals[i] != vals[start]:
            ax.axvspan(idx[start], idx[i - 1], color=REGIME_FILL.get(vals[start], "#cccccc33"),
                       lw=0, zorder=0)
            start = i
    ax.axvspan(idx[start], idx[-1], color=REGIME_FILL.get(vals[start], "#cccccc33"), lw=0, zorder=0)


def make_figure(df: pd.DataFrame):
    archetypes = select_regime_archetypes(df)
    highlights = archetypes["highlights"]
    bg_ids = archetypes["background"]

    # Summary scatter in phase space (min state reached per member)
    summary_pts = []
    for mid in list(bg_ids) + list(highlights.values()):
        tr = load_member_regime_trace(int(mid))
        summary_pts.append({
            "member_id": mid,
            "ierq_min_frac": tr["ierq_min_frac"],
            "lb_min_frac": tr["lb_min_frac"],
            "highlight": mid in highlights.values(),
        })
    pts = pd.DataFrame(summary_pts)

    fig = plt.figure(figsize=(14, 9))
    gs = GridSpec(3, 3, figure=fig, width_ratios=[1.2, 1, 1], height_ratios=[1.1, 1, 1],
                  hspace=0.45, wspace=0.35)

    ax_phase = fig.add_subplot(gs[0, :])
    ax_phase.set_title(
        "State-space atlas: IERQ bank vs LB storage\n"
        "Thin traces = background ensemble  |  Bold = regime archetypes",
        fontsize=9,
    )

    # Background trajectories (subsample for speed)
    for mid in bg_ids[::2]:
        tr = load_member_regime_trace(mid)
        mask = (tr["dates"] >= TRACE_WINDOW[0]) & (tr["dates"] <= TRACE_WINDOW[1])
        ax_phase.plot(
            tr["ierq_frac"].loc[mask], tr["lb_frac"].loc[mask],
            color="gray", alpha=0.08, lw=0.4, zorder=1,
        )

    bg = pts[~pts["highlight"]]
    ax_phase.scatter(
        bg["ierq_min_frac"], bg["lb_min_frac"],
        c="#bdbdbd", s=12, alpha=0.5, edgecolors="none", zorder=2, label="Ensemble minima",
    )

    # Highlight trajectories + endpoints
    for i, (label, mid) in enumerate(highlights.items()):
        color = HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]
        tr = load_member_regime_trace(int(mid))
        mask = (tr["dates"] >= TRACE_WINDOW[0]) & (tr["dates"] <= TRACE_WINDOW[1])
        ax_phase.plot(
            tr["ierq_frac"].loc[mask], tr["lb_frac"].loc[mask],
            color=color, lw=2.0, alpha=0.9, zorder=4, label=f"{label} (m={mid})",
        )
        ax_phase.scatter(
            tr["ierq_min_frac"], tr["lb_min_frac"],
            c=color, s=60, edgecolors="black", lw=0.6, zorder=5,
        )

    # Regime boundary lines
    ax_phase.axvline(IERQ_EXHAUSTION_MG / IERQ_MAX_MG, color=REGIME_COLORS["NYC-limited"],
                     ls="--", lw=1.2, alpha=0.8)
    ax_phase.axhline(LB_CONSERVATION_FRAC, color=REGIME_COLORS["LB-limited"],
                     ls="--", lw=1.2, alpha=0.8)
    ax_phase.text(0.02, LB_CONSERVATION_FRAC + 0.02, "LB conservation pool",
                  fontsize=7, color=REGIME_COLORS["LB-limited"])
    ax_phase.text(IERQ_EXHAUSTION_MG / IERQ_MAX_MG + 0.01, 0.95, "IERQ exhaustion",
                  fontsize=7, color=REGIME_COLORS["NYC-limited"], rotation=90, va="top")

    ax_phase.set_xlabel("IERQ bank fraction (Trenton)", fontsize=9)
    ax_phase.set_ylabel("LB combined storage fraction", fontsize=9)
    ax_phase.set_xlim(-0.02, 1.05)
    ax_phase.set_ylim(-0.02, 1.05)
    ax_phase.legend(fontsize=7, loc="upper right", ncol=2, framealpha=0.92)

    # Time-trace panels (first 5 highlights in 2x3 grid bottom)
    trace_axes = [
        fig.add_subplot(gs[1, 0]),
        fig.add_subplot(gs[1, 1]),
        fig.add_subplot(gs[1, 2]),
        fig.add_subplot(gs[2, 0]),
        fig.add_subplot(gs[2, 1]),
    ]

    for i, (ax, (label, mid)) in enumerate(zip(trace_axes, list(highlights.items())[:5])):
        color = HIGHLIGHT_COLORS[i % len(HIGHLIGHT_COLORS)]
        tr = load_member_regime_trace(int(mid))
        t0, t1 = pd.Timestamp(TRACE_WINDOW[0]), pd.Timestamp(TRACE_WINDOW[1])
        dates = tr["dates"][(tr["dates"] >= t0) & (tr["dates"] <= t1)]
        ierq = tr["ierq_frac"].loc[dates]
        lb = tr["lb_frac"].loc[dates]
        labs = tr["labels"].loc[dates]

        _shade_regimes(ax, dates, tr["labels"], 0, 1)
        ax2 = ax.twinx()
        ax.plot(dates, ierq, color=color, lw=1.4, label="IERQ bank")
        ax2.plot(dates, lb, color="black", lw=1.0, alpha=0.65, ls="--", label="LB storage")
        ax.axhline(IERQ_EXHAUSTION_MG / IERQ_MAX_MG, color=REGIME_COLORS["NYC-limited"],
                   ls=":", lw=0.8, alpha=0.7)
        ax2.axhline(LB_CONSERVATION_FRAC, color=REGIME_COLORS["LB-limited"],
                    ls=":", lw=0.8, alpha=0.7)

        ax.set_title(f"{label}\nmember {mid}", fontsize=8, color=color, fontweight="bold")
        ax.set_ylim(-0.02, 1.05)
        ax2.set_ylim(-0.02, 1.05)
        ax.set_xlim(dates[0], dates[-1])
        ax.tick_params(labelsize=7)
        ax2.tick_params(labelsize=7)
        if ax is trace_axes[0]:
            ax.set_ylabel("IERQ fraction", fontsize=8)
        if ax is trace_axes[3]:
            ax.set_ylabel("IERQ fraction", fontsize=8)
        if ax in (trace_axes[0], trace_axes[3]):
            ax2.set_ylabel("LB fraction", fontsize=8)
        if ax in (trace_axes[3], trace_axes[4]):
            ax.set_xlabel("Date", fontsize=8)

    # Regime legend in empty cell
    ax_leg = fig.add_subplot(gs[2, 2])
    ax_leg.axis("off")
    patches = [
        mpatches.Patch(color=REGIME_COLORS["normal"], alpha=0.5, label="Normal"),
        mpatches.Patch(color=REGIME_COLORS["NYC-limited"], alpha=0.7, label="NYC / diversion-limited"),
        mpatches.Patch(color=REGIME_COLORS["LB-limited"], alpha=0.7, label="LB / storage-limited"),
        mpatches.Patch(color=REGIME_COLORS["co-limited"], alpha=0.7, label="Co-limited"),
    ]
    ax_leg.legend(handles=patches, loc="center", fontsize=8, title="Daily regime (shaded bands)",
                  title_fontsize=8, framealpha=0.95)
    ax_leg.text(
        0.5, 0.15,
        "Pairing state-space position with\ndaily constraint activation links\n"
        "the phase diagram to operational sequence.",
        transform=ax_leg.transAxes, ha="center", fontsize=8, color="#444444",
    )

    fig.suptitle(
        "Figure J — Regime-Boundary Trace Atlas\n"
        "RQ2: Representative trajectories on different sides of the operating-regime boundary",
        fontsize=11, y=1.01,
    )

    out = FIGS / "fig_J_regime_boundary_trace_atlas.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = pd.read_parquet(PATHS["rrv_summary"])
    make_figure(df)

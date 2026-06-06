"""
Figure G — Shortfall Sequence and First-Hit Order

Shows the order in which parties move into shortfall as drought
severity increases across the ensemble. Uses an alluvial/ribbon
structure colored by party, sorted by first-hit reliability threshold.

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet
  Must include: regime_first, n_days_regime_* columns from updated metrics.py

Output
------
figures/publication/fig_G_shortfall_sequence.png
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch
from _paths import (PATHS, PARTIES, PARTY_LABELS, PARTY_COLORS,
                    PARTY_RELIABILITY, FIGS, set_style)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

THRESHOLDS = [0.99, 0.95, 0.90, 0.80, 0.70, 0.50]


def load_data() -> pd.DataFrame:
    return pd.read_parquet(PATHS["rrv_summary"])


def compute_exceedance(df: pd.DataFrame) -> dict:
    """
    For each party, compute fraction of members below each reliability threshold.
    Returns dict: party -> array of exceedance fractions at THRESHOLDS.
    """
    exc = {}
    for p in PARTIES:
        col = PARTY_RELIABILITY[p]
        vals = df[col].dropna().values
        exc[p] = np.array([(vals < t).mean() for t in THRESHOLDS])
    return exc


def make_figure(df: pd.DataFrame):
    exc = compute_exceedance(df)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        "Figure G — Party Shortfall Sequence: When Does Each Party Fail?\n"
        "Left: Exceedance probability curves  |  Right: First-hit ranking by reliability threshold",
        fontsize=10, y=1.01,
    )

    # ── Panel 1: Exceedance curves ──
    ax = axes[0]
    for p in PARTIES:
        ax.plot(THRESHOLDS[::-1], exc[p][::-1],
                color=PARTY_COLORS[p], lw=2.2, marker="o", ms=5,
                label=PARTY_LABELS[p].replace("\n", " "))
        ax.fill_between(THRESHOLDS[::-1], 0, exc[p][::-1],
                        color=PARTY_COLORS[p], alpha=0.08)

    ax.set_xlabel("Reliability threshold (fraction of days meeting obligation)", fontsize=9)
    ax.set_ylabel("Fraction of ensemble members\nbelow threshold", fontsize=9)
    ax.set_title("Exceedance Probability Curves\n"
                 "Higher curve = party fails more often at that threshold", fontsize=8)
    ax.legend(fontsize=7, loc="upper left")
    ax.set_xlim(1.02, 0.48)
    ax.set_ylim(-0.02, 1.05)

    # Annotate crossings
    for t_idx, t in enumerate(THRESHOLDS):
        ranked = sorted(PARTIES, key=lambda p: exc[p][t_idx], reverse=True)
        if exc[ranked[0]][t_idx] > 0.05:
            ax.annotate(f"  {ranked[0]}", (t, exc[ranked[0]][t_idx]),
                        fontsize=6.5, color=PARTY_COLORS[ranked[0]], va="bottom")

    # ── Panel 2: Rank heatmap at each threshold ──
    ax2 = axes[1]

    # Rank parties at each threshold (1 = most vulnerable)
    rank_matrix = np.zeros((len(PARTIES), len(THRESHOLDS)))
    for t_idx, t in enumerate(THRESHOLDS):
        sorted_parties = sorted(PARTIES,
                                key=lambda p: exc[p][t_idx],
                                reverse=True)
        for rank, p in enumerate(sorted_parties):
            rank_matrix[PARTIES.index(p), t_idx] = rank + 1

    im = ax2.imshow(rank_matrix, cmap="RdYlGn_r", aspect="auto",
                    vmin=1, vmax=5)
    plt.colorbar(im, ax=ax2, label="Vulnerability rank (1=most vulnerable)", shrink=0.8)

    ax2.set_xticks(range(len(THRESHOLDS)))
    ax2.set_xticklabels([f"{t:.0%}" for t in THRESHOLDS], fontsize=8)
    ax2.set_yticks(range(len(PARTIES)))
    ax2.set_yticklabels([PARTY_LABELS[p].replace("\n", " ") for p in PARTIES], fontsize=8)
    ax2.set_xlabel("Reliability threshold", fontsize=9)
    ax2.set_title("Vulnerability Rank at Each Threshold\n"
                  "Red = most vulnerable at that threshold", fontsize=8)

    # Annotate rank values
    for i in range(len(PARTIES)):
        for j in range(len(THRESHOLDS)):
            ax2.text(j, i, f"{int(rank_matrix[i,j])}",
                     ha="center", va="center", fontsize=9,
                     fontweight="bold",
                     color="white" if rank_matrix[i,j] <= 2 else "black")

    out = FIGS / "fig_G_shortfall_sequence.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = load_data()
    make_figure(df)

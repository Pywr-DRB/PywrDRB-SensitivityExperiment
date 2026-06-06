"""
Figure E — Party Obligations vs Realized Exposure

Dumbbell / bubble plot comparing each party's institutional obligation
weight against their modeled drought-risk burden (mean reliability,
median shortfall fraction, and asymmetry contribution).

Tests the core RQ1 claim: is risk proportional to obligation?

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet

Output
------
figures/publication/fig_E_obligations_vs_exposure.png
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
import matplotlib.lines as mlines
from _paths import (PATHS, PARTIES, PARTY_COLORS,
                    OBLIGATION_WEIGHTS, PARTY_RELIABILITY, FIGS, set_style)

# Override labels to clarify metric basis per party
PARTY_LABELS = {
    "DE":  "Delaware\n(Trenton TFO reliability)",
    "NYC": "New York City\n(IERQ bank reliability)",
    "PA":  "Pennsylvania\n(LB conservation pool)",
    "NJ":  "New Jersey\n(diversion cap compliance)",
    "NY":  "New York State\n(Montague TFO)†",
}

set_style()
FIGS.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    return pd.read_parquet(PATHS["rrv_summary"])


def make_figure(df: pd.DataFrame):
    # --- Compute per-party summary statistics ---
    means, p10s, p90s = {}, {}, {}
    for p in PARTIES:
        col = PARTY_RELIABILITY[p]
        vals = df[col].dropna()
        means[p] = vals.mean()
        p10s[p]  = vals.quantile(0.10)
        p90s[p]  = vals.quantile(0.90)

    obligation = [OBLIGATION_WEIGHTS[p] for p in PARTIES]
    reliability = [means[p] for p in PARTIES]

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.suptitle(
        "Figure E — Institutional Obligation vs Realized Drought-Risk Burden\n"
        "RQ1: Is risk distributed proportionally to legal obligation?",
        fontsize=10, y=1.01,
    )

    # ── Panel 1: Dumbbell — obligation vs mean reliability ──
    ax = axes[0]
    y = np.arange(len(PARTIES))

    for i, p in enumerate(PARTIES):
        # Error bar: 10th–90th percentile of ensemble
        ax.plot([p10s[p], p90s[p]], [i, i], color=PARTY_COLORS[p],
                lw=3, alpha=0.4, solid_capstyle="round")
        # Mean reliability
        ax.scatter(means[p], i, color=PARTY_COLORS[p], s=80, zorder=5,
                   edgecolor="black", linewidth=0.8, label=p)
        # Obligation share (scaled to [0,1] reliability axis)
        ax.scatter(OBLIGATION_WEIGHTS[p], i, color=PARTY_COLORS[p],
                   s=80, marker="D", zorder=5, edgecolor="black",
                   linewidth=0.8, alpha=0.5)
        # Arrow from obligation to reliability
        dx = means[p] - OBLIGATION_WEIGHTS[p]
        ax.annotate("", xy=(means[p] - 0.005 * np.sign(dx), i),
                    xytext=(OBLIGATION_WEIGHTS[p] + 0.005 * np.sign(dx), i),
                    arrowprops=dict(arrowstyle="->", color=PARTY_COLORS[p],
                                   lw=1.2, alpha=0.7))

    ax.axvline(0.20, color="gray", lw=0.8, ls="--", alpha=0.5,
               label="Equal weight (0.20)")
    ax.set_yticks(y)
    ax.set_yticklabels([PARTY_LABELS[p] for p in PARTIES], fontsize=8)
    ax.set_xlabel("Value (obligation weight / reliability fraction)", fontsize=9)
    ax.set_title("Mean Reliability vs Obligation Weight\n"
                 "Diamond = obligation  •  Circle = mean reliability  |  Bar = 10th–90th pct",
                 fontsize=8)
    ax.set_xlim(-0.02, 1.05)

    # Manual legend
    circ = mlines.Line2D([], [], color="gray", marker="o", linestyle="None",
                         markersize=7, label="Mean reliability")
    diam = mlines.Line2D([], [], color="gray", marker="D", linestyle="None",
                         markersize=7, alpha=0.5, label="Obligation weight")
    ax.legend(handles=[circ, diam], fontsize=8, loc="lower right")

    # ── Panel 2: Scatter — obligation vs shortfall exposure ──
    ax2 = axes[1]

    shortfall_exposure = [1.0 - means[p] for p in PARTIES]  # 1 - reliability = risk burden

    sc = ax2.scatter(obligation, shortfall_exposure,
                     c=[PARTY_COLORS[p] for p in PARTIES],
                     s=[200 * OBLIGATION_WEIGHTS[p] * 10 for p in PARTIES],
                     edgecolors="black", linewidth=0.8, zorder=5, alpha=0.85)

    # Labels
    for i, p in enumerate(PARTIES):
        ax2.annotate(p, (obligation[i], shortfall_exposure[i]),
                     textcoords="offset points", xytext=(8, 3),
                     fontsize=9, fontweight="bold", color=PARTY_COLORS[p])

    # Proportionality line
    lim = max(max(obligation), max(shortfall_exposure)) * 1.1
    ax2.plot([0, lim], [0, lim], color="gray", lw=1, ls="--", alpha=0.5,
             label="Proportional (risk = obligation)")
    ax2.set_xlabel("Institutional Obligation Weight", fontsize=9)
    ax2.set_ylabel("Risk Burden (1 − Mean Reliability)", fontsize=9)
    ax2.set_title("Proportionality Test\nPoint size ∝ obligation weight",
                  fontsize=8)
    ax2.legend(fontsize=8)

    # Annotation: above/below line
    for i, p in enumerate(PARTIES):
        diff = shortfall_exposure[i] - obligation[i]
        label = "bears excess risk" if diff > 0.02 else ("under-exposed" if diff < -0.02 else "")
        if label:
            ax2.annotate(label, (obligation[i], shortfall_exposure[i]),
                         textcoords="offset points", xytext=(8, -12),
                         fontsize=6.5, color="gray", style="italic")

    # Footnote clarifying NY metric
    fig.text(0.01, -0.02,
             "† NY reliability = fraction of days Montague flow objective met "
             "(upstream tributary flows, not a diversion-based metric).\n"
             "  High NY reliability reflects favorable upstream hydrology, "
             "not necessarily Decree compliance relative to institutional burden.",
             fontsize=7, color="gray", va="top")

    out = FIGS / "fig_E_obligations_vs_exposure.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = load_data()
    make_figure(df)

"""
Figure K — Global Sensitivity of Asymmetry Metrics (Sobol Indices)

Two-panel figure:
  Left:  First-order (S1) and total-order (ST) Sobol indices per parameter
         for obligation-weighted risk asymmetry.
  Right: S2 parameter-interaction heat map.

Data required
-------------
D4_distributed_risk/results/sobol*/sobol_indices.parquet
D4_distributed_risk/results/sobol*/sobol_mean_metrics.parquet

Output
------
figures/publication/fig_K_sobol_sensitivity.png
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm

from _paths import PARAM_LABELS, FIGS, set_style
from _figure_helpers import (
    sobol_paths,
    add_asymmetry_columns,
    ensure_asymmetry_indices,
)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

FOCUS_METRIC = "asym_reliability_obligation"
SECONDARY_METRIC = "party_vulnerability_gap"


def load_data():
    sp = sobol_paths()
    if not sp["sobol_indices"].exists():
        raise FileNotFoundError(
            f"sobol_indices.parquet not found under {sp['root']}\n"
            "Run sobol_analysis.py after the Sobol sweep completes."
        )
    idx = pd.read_parquet(sp["sobol_indices"])
    s2 = pd.read_parquet(sp["sobol_S2"]) if sp["sobol_S2"].exists() else pd.DataFrame()
    mean_df = pd.read_parquet(sp["sobol_mean_metrics"])
    mean_df = add_asymmetry_columns(mean_df)
    idx, s2 = ensure_asymmetry_indices(idx, s2, mean_df)
    return idx, s2, sp["root"].name


def make_figure(idx: pd.DataFrame, s2: pd.DataFrame, sweep_label: str):
    metric = FOCUS_METRIC if FOCUS_METRIC in idx["metric"].values else SECONDARY_METRIC
    sub = idx[idx["metric"] == metric].copy()
    if sub.empty:
        raise ValueError("No Sobol indices available for asymmetry metrics.")

    params = sub["parameter"].tolist()
    short = [PARAM_LABELS.get(p, p).split("\n")[0] for p in params]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5),
                             gridspec_kw={"width_ratios": [1.5, 1]})
    fig.suptitle(
        "Figure K — Global Sensitivity of Risk Asymmetry\n"
        f"Output: obligation-weighted party reliability gap  |  {sweep_label}  |  k=6  |  N=1,024",
        fontsize=10, y=1.02,
    )

    # ── Panel 1: S1 and ST grouped bars ──
    ax = axes[0]
    x = np.arange(len(params))
    w = 0.36
    s1 = sub.set_index("parameter").reindex(params)["S1"].values
    st = sub.set_index("parameter").reindex(params)["ST"].values
    s1c = sub.set_index("parameter").reindex(params)["S1_conf"].values
    stc = sub.set_index("parameter").reindex(params)["ST_conf"].values

    ax.bar(x - w / 2, s1, w, color="#92c5de", label="S1 (first-order)", edgecolor="white", lw=0.4)
    ax.bar(x + w / 2, st, w, color="#2166ac", label="ST (total-order)", edgecolor="white", lw=0.4)
    ax.errorbar(x - w / 2, s1, yerr=s1c, fmt="none", color="black", capsize=2, lw=0.8)
    ax.errorbar(x + w / 2, st, yerr=stc, fmt="none", color="black", capsize=2, lw=0.8)

    ax.set_xticks(x)
    ax.set_xticklabels(short, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("Sobol index", fontsize=9)
    ax.set_title("First- and Total-Order Indices\n"
                 "Which legal parameters drive asymmetry?", fontsize=8)
    ax.legend(fontsize=8, loc="upper right")
    ax.set_ylim(-0.05, max(1.05, float(np.nanmax(st) + 0.1)))

    # ── Panel 2: S2 interaction heatmap ──
    ax2 = axes[1]
    asym_s2 = s2[s2["metric"] == metric] if not s2.empty else pd.DataFrame()
    n = len(params)
    mat = np.zeros((n, n))
    for _, row in asym_s2.iterrows():
        pi = params.index(row["param_i"]) if row["param_i"] in params else -1
        pj = params.index(row["param_j"]) if row["param_j"] in params else -1
        if pi >= 0 and pj >= 0:
            mat[pi, pj] = row["S2"]
            mat[pj, pi] = row["S2"]

    vmax = max(abs(mat).max(), 0.01)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0, vmax=vmax)
    im = ax2.imshow(mat, cmap="RdBu_r", norm=norm, aspect="auto")
    plt.colorbar(im, ax=ax2, label="S2 (interaction)", shrink=0.85)

    ax2.set_xticks(range(n))
    ax2.set_yticks(range(n))
    ax2.set_xticklabels(short, rotation=45, ha="right", fontsize=7)
    ax2.set_yticklabels(short, fontsize=7)
    ax2.set_title("Parameter Interaction Heat Map\n"
                  "Non-additive effects on asymmetry", fontsize=8)

    for i in range(n):
        for j in range(n):
            if abs(mat[i, j]) > 0.02:
                ax2.text(j, i, f"{mat[i, j]:.2f}",
                         ha="center", va="center", fontsize=7,
                         color="white" if abs(mat[i, j]) > 0.08 else "black")

    out = FIGS / "fig_K_sobol_sensitivity.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    idx, s2, sweep_label = load_data()
    make_figure(idx, s2, sweep_label)

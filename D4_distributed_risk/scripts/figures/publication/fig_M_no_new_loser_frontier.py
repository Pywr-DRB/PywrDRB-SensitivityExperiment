"""
Figure M — SA Coordination Space and No-New-Loser Frontier

Capstone figure:
  Left:  Parameter scatter colored by asymmetry reduction class, with
         promising-region boxes.
  Right: Pareto-style frontier — asymmetry reduction vs worst-party harm.

Data required
-------------
D4_distributed_risk/results/sobol*/sobol_mean_metrics.parquet

Output
------
figures/publication/fig_M_no_new_loser_frontier.png
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
from matplotlib.patches import Rectangle

from _paths import PARTIES, PARTY_RELIABILITY, FIGS, set_style
from _figure_helpers import sobol_paths, add_asymmetry_columns

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

ASYM_COL = "asym_reliability_obligation"


def load_data() -> tuple[pd.DataFrame, str]:
    sp = sobol_paths()
    if not sp["sobol_mean_metrics"].exists():
        raise FileNotFoundError(
            f"sobol_mean_metrics.parquet not found under {sp['root']}\n"
            "Run sobol_analysis.py after the Sobol sweep completes."
        )
    df = add_asymmetry_columns(pd.read_parquet(sp["sobol_mean_metrics"]))
    return df, sp["root"].name


def classify_tradeoff(row: pd.Series, baseline: dict) -> str:
    deltas = {p: row[PARTY_RELIABILITY[p]] - baseline[p] for p in PARTIES
              if PARTY_RELIABILITY[p] in row.index}
    n_pos = sum(d > 0.001 for d in deltas.values())
    n_neg = sum(d < -0.001 for d in deltas.values())
    if n_neg == 0 and n_pos > 0:
        return "win-win"
    if n_pos == 0 and n_neg > 0:
        return "lose-lose"
    if n_neg == 0:
        return "no-new-loser"
    return "redistribution"


def make_figure(df: pd.DataFrame, sweep_label: str):
    baseline = {p: df[PARTY_RELIABILITY[p]].median() for p in PARTIES
                if PARTY_RELIABILITY[p] in df.columns}
    baseline_asym = df[ASYM_COL].median()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        "Figure M — Coordination Space and No-New-Loser Frontier\n"
        f"RQ3: Parameter combinations that reduce asymmetry without creating a new losing party  |  {sweep_label}",
        fontsize=10, y=1.02,
    )

    df = df.copy()
    df["tradeoff_class"] = df.apply(classify_tradeoff, axis=1, baseline=baseline)
    df["delta_asym"] = df[ASYM_COL] - baseline_asym
    df["asym_reduction"] = baseline_asym - df[ASYM_COL]
    df["worst_delta_rel"] = df.apply(
        lambda r: min(r[PARTY_RELIABILITY[p]] - baseline[p]
                      for p in PARTIES if PARTY_RELIABILITY[p] in r.index),
        axis=1,
    )

    tc_colors = {
        "win-win": "#2ca02c",
        "no-new-loser": "#98df8a",
        "redistribution": "#ff7f0e",
        "lose-lose": "#d62728",
    }

    # ── Panel 1: coordination space ──
    ax = axes[0]
    for tc, color in tc_colors.items():
        sub = df[df["tradeoff_class"] == tc]
        if len(sub) == 0:
            continue
        ax.scatter(sub["alpha_betz_warning"], sub["alpha_bm_warning"],
                   c=color, alpha=0.22, s=10, label=f"{tc} ({len(sub):,})", rasterized=True)

    promising = df[(df["worst_delta_rel"] >= -0.001) & (df["asym_reduction"] > 0)]
    if len(promising) > 0:
        x0, x1 = promising["alpha_betz_warning"].min(), promising["alpha_betz_warning"].max()
        y0, y1 = promising["alpha_bm_warning"].min(), promising["alpha_bm_warning"].max()
        pad = 0.02
        rect = Rectangle((x0 - pad, y0 - pad), (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad,
                         fill=False, edgecolor="#2ca02c", lw=2, ls="--", zorder=6)
        ax.add_patch(rect)
        ax.text(x0, y1 + pad, "Promising region\n(no harm + ↓ asymmetry)",
                fontsize=7, color="#2ca02c", va="bottom")

    nnl = df[df["tradeoff_class"].isin(["win-win", "no-new-loser"])]
    if len(nnl) > 0:
        ax.scatter(nnl["alpha_betz_warning"], nnl["alpha_bm_warning"],
                   c="#2ca02c", s=28, alpha=0.85, edgecolors="black", lw=0.4, zorder=5)

    ax.axvline(df["alpha_betz_warning"].median(), color="black", lw=1, ls="--", alpha=0.4)
    ax.axhline(df["alpha_bm_warning"].median(), color="black", lw=1, ls="--", alpha=0.4)
    ax.scatter(df["alpha_betz_warning"].median(), df["alpha_bm_warning"].median(),
               color="black", s=90, marker="*", zorder=10, label="Baseline (median)")

    ax.set_xlabel("α_BW (Beltzville warning threshold)", fontsize=9)
    ax.set_ylabel("α_BMW (Blue Marsh warning threshold)", fontsize=9)
    ax.set_title("Institutional Coordination Space\n"
                 "LB warning thresholds × asymmetry outcome class", fontsize=8)
    ax.legend(fontsize=7, loc="upper left", markerscale=1.5)

    # ── Panel 2: no-new-loser frontier ──
    ax2 = axes[1]
    for tc, color in tc_colors.items():
        sub = df[df["tradeoff_class"] == tc]
        ax2.scatter(sub["asym_reduction"], sub["worst_delta_rel"],
                    c=color, alpha=0.18, s=8, rasterized=True)

    nnl_front = df[df["worst_delta_rel"] >= -0.001].sort_values("asym_reduction", ascending=False)
    if len(nnl_front) > 5:
        ax2.scatter(nnl_front["asym_reduction"], nnl_front["worst_delta_rel"],
                    c="#2ca02c", alpha=0.45, s=12, zorder=4,
                    label=f"No-new-loser samples (n={len(nnl_front):,})")

        # Pareto envelope: best asymmetry reduction at each harm level
        harm_bins = np.linspace(nnl_front["worst_delta_rel"].min(), 0, 25)
        pareto_x, pareto_y = [], []
        for i in range(len(harm_bins) - 1):
            band = nnl_front[
                (nnl_front["worst_delta_rel"] >= harm_bins[i])
                & (nnl_front["worst_delta_rel"] < harm_bins[i + 1])
            ]
            if len(band) > 0:
                j = band["asym_reduction"].idxmax()
                pareto_x.append(band.loc[j, "asym_reduction"])
                pareto_y.append(band.loc[j, "worst_delta_rel"])
        if pareto_x:
            order = np.argsort(pareto_y)
            ax2.plot(np.array(pareto_x)[order], np.array(pareto_y)[order],
                     color="#1b7837", lw=2.2, zorder=6, label="No-new-loser frontier")

    ax2.axhline(0, color="black", lw=1, ls="--", alpha=0.5)
    ax2.axvline(0, color="black", lw=1, ls="--", alpha=0.5)
    ax2.scatter(0, 0, color="black", s=100, marker="*", zorder=10, label="Baseline")
    xmax = max(ax2.get_xlim()[1], 0.001)
    ax2.fill_between([0, xmax], 0, 0.02, color="#2ca02c", alpha=0.08)

    ax2.set_xlabel("Asymmetry reduction (Δ obligation-weighted gap)", fontsize=9)
    ax2.set_ylabel("Worst-party reliability change (Δ)", fontsize=9)
    ax2.set_title("Pareto Frontier: Asymmetry vs Robustness\n"
                  "Target: upper-right (less asymmetry, no new loser)", fontsize=8)
    ax2.legend(fontsize=7, loc="lower right")

    out = FIGS / "fig_M_no_new_loser_frontier.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df, sweep_label = load_data()
    make_figure(df, sweep_label)

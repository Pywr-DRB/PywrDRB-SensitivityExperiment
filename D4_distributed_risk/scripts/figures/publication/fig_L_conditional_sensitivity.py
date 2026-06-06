"""
Figure L — Sensitivity Through Drought Progression

Two panels:
  Left:  Stacked ribbon of regime occupancy by day-of-year (ensemble baseline).
  Right: Parameter variance contributions (ST) across drought-severity bins
         from the Sobol sample space.

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet + member HDF5
D4_distributed_risk/results/sobol*/sobol_mean_metrics.parquet

Output
------
figures/publication/fig_L_conditional_sensitivity.png
"""

from __future__ import annotations

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

from _paths import PATHS, PARAM_LABELS, FIGS, set_style
from _figure_helpers import (
    sobol_paths,
    add_asymmetry_columns,
    load_member_regime_trace,
)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

FOCUS_METRIC = "asym_reliability_obligation"
PARAM_SHORT = {
    "alpha_betz_warning": "α_BW",
    "alpha_bm_warning": "α_BMW",
    "m_lb": "m_LB",
    "ierq_max_bg": "I_max",
    "erq_cap_mg": "C_ERQ",
    "q_nj_warning": "Q_NJ",
    "tau_recovery": "τ_R",
}
N_DOY_MEMBERS = 60
N_BINS = 5


def _regime_ribbon_by_doy(member_ids: list[int]) -> pd.DataFrame:
    """Fraction of days in each regime by day-of-year, pooled across members/years."""
    counts = {r: np.zeros(366) for r in (0, 1, 2, 3)}
    for mid in member_ids:
        tr = load_member_regime_trace(mid)
        doy = tr["labels"].index.dayofyear
        labs = tr["labels"].values
        for r in counts:
            for d in range(1, 366):
                mask = doy == d
                if mask.any():
                    counts[r][d] += (labs[mask] == r).sum()

    rows = []
    for d in range(1, 366):
        tot = sum(counts[r][d] for r in counts)
        if tot == 0:
            continue
        row = {"doy": d}
        for r, name in [(0, "normal"), (1, "NYC"), (2, "LB"), (3, "co")]:
            row[name] = counts[r][d] / tot
        rows.append(row)
    return pd.DataFrame(rows)


def _importance_by_drought_bin(mean_df: pd.DataFrame, problem: dict) -> pd.DataFrame:
    """
    Rank-based sensitivity per drought-severity bin.

    Saltelli subsamples cannot be re-analyzed on arbitrary subsets, so we use
    normalized |Spearman r| between each parameter and the asymmetry metric
    within DE-reliability quantile bins as a drought-conditional importance proxy.
    """
    metric_col = FOCUS_METRIC if FOCUS_METRIC in mean_df.columns else "de_reliability"
    params = problem["names"]
    bins = pd.qcut(mean_df["de_reliability"], q=N_BINS, duplicates="drop")
    rows = []
    for b_idx, (_, sub) in enumerate(mean_df.groupby(bins, observed=True)):
        if len(sub) < 30:
            continue
        corrs = []
        for p in params:
            if p not in sub.columns:
                corrs.append(0.0)
                continue
            r = sub[p].corr(sub[metric_col], method="spearman")
            corrs.append(abs(r) if pd.notna(r) else 0.0)
        corrs = np.array(corrs)
        s = corrs.sum()
        weights = corrs / s if s > 0 else corrs
        for p, w in zip(params, weights):
            rows.append({
                "bin": b_idx,
                "bin_label": (
                    f"Q{b_idx + 1}\n"
                    f"({sub['de_reliability'].min():.3f}–{sub['de_reliability'].max():.3f})"
                ),
                "parameter": p,
                "weight": float(w),
            })
    return pd.DataFrame(rows)


def make_figure(df: pd.DataFrame, mean_df: pd.DataFrame, sweep_label: str):
    mean_df = add_asymmetry_columns(mean_df)
    sp = sobol_paths()
    with open(sp["sobol_design"]) as f:
        problem = json.load(f)

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        "Figure L — Sensitivity Through Drought Progression\n"
        "Left: when constraints bind through the year  |  "
        f"Right: which parameters matter under increasing drought stress ({sweep_label})",
        fontsize=10, y=1.02,
    )

    # ── Panel 1: regime occupancy ribbon by DOY ──
    ax = axes[0]
    rng = np.random.default_rng(7)
    sample_ids = rng.choice(df["realization_id"].astype(int).values,
                            size=min(N_DOY_MEMBERS, len(df)), replace=False)
    ribbon = _regime_ribbon_by_doy(list(sample_ids))

    stack_colors = ["#d0e8d0", "#f4a582", "#92c5de", "#ca0020"]
    stack_labels = ["Normal", "NYC-limited", "LB-limited", "Co-limited"]
    y_stack = [ribbon["normal"].values, ribbon["NYC"].values,
               ribbon["LB"].values, ribbon["co"].values]
    ax.stackplot(ribbon["doy"], y_stack, labels=stack_labels,
                 colors=stack_colors, alpha=0.85)
    ax.set_xlim(1, 365)
    ax.set_ylim(0, 1)
    ax.set_xlabel("Day of year", fontsize=9)
    ax.set_ylabel("Fraction of member-days in regime", fontsize=9)
    ax.set_title("Regime Composition Through the Calendar Year\n"
                 "Stacked ribbon across ensemble subsample", fontsize=8)
    ax.legend(fontsize=7, loc="upper right", ncol=2)

    # ── Panel 2: stacked ST contributions by drought bin ──
    ax2 = axes[1]
    strat = _importance_by_drought_bin(mean_df, problem)
    if strat.empty:
        ax2.text(0.5, 0.5, "Insufficient samples for\nbinned sensitivity analysis",
                 transform=ax2.transAxes, ha="center", va="center", fontsize=10, color="gray")
    else:
        params = problem["names"]
        short = [PARAM_SHORT.get(p, p) for p in params]
        bins = strat["bin"].unique()
        bin_labels = [strat.loc[strat["bin"] == b, "bin_label"].iloc[0] for b in bins]
        mat = np.zeros((len(params), len(bins)))
        for j, b in enumerate(bins):
            sub = strat[strat["bin"] == b].set_index("parameter").reindex(params)
            mat[:, j] = sub["weight"].fillna(0).values

        bottom = np.zeros(len(bins))
        colors = plt.cm.Set2(np.linspace(0, 1, len(params)))
        for i, (p, color) in enumerate(zip(params, colors)):
            ax2.bar(range(len(bins)), mat[i], bottom=bottom, color=color,
                    label=short[i], edgecolor="white", lw=0.3)
            bottom += mat[i]

        ax2.set_xticks(range(len(bins)))
        ax2.set_xticklabels(bin_labels, fontsize=7)
        ax2.set_ylabel("Normalized |ρ| contribution", fontsize=9)
        ax2.set_xlabel("Drought-stress bin (DE reliability quantile)", fontsize=9)
        ax2.set_title("Parameter Importance Shifts With Drought Severity\n"
                      "Stacked rank-correlation shares (asymmetry metric)", fontsize=8)
        ax2.legend(fontsize=6, loc="upper left", ncol=2, framealpha=0.9)

    out = FIGS / "fig_L_conditional_sensitivity.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = pd.read_parquet(PATHS["rrv_summary"])
    sp = sobol_paths()
    if not sp["sobol_mean_metrics"].exists():
        raise FileNotFoundError(f"sobol_mean_metrics not found under {sp['root']}")
    mean_df = pd.read_parquet(sp["sobol_mean_metrics"])
    make_figure(df, mean_df, sp["root"].name)

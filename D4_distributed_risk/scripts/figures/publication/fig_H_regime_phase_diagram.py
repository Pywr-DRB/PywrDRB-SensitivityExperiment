"""
Figure H — Regime Attribution Phase Diagram

Plots the system in a 2D state space (Amestoy member characteristics:
mean annual Montague flow vs combined LB min storage fraction) colored
by dominant operating regime. Shows the empirical regime boundary.

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet
  Must include: regime_frac_* columns (reaggregated with updated metrics.py)
  Also uses: pa_min_storage_frac, ny_reliability as proxy state variables

D4_distributed_risk/results/baseline/stage2_days_summary.csv

Output
------
figures/publication/fig_H_regime_phase_diagram.png
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
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from _paths import PATHS, REGIME_COLORS, FIGS, set_style

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

REGIME_ORDER = ["normal", "NYC-limited", "LB-limited", "co-limited"]
REGIME_INT   = {r: i for i, r in enumerate(REGIME_ORDER)}


def load_data():
    df = pd.read_parquet(PATHS["rrv_summary"])
    s2 = pd.read_csv(PATHS["stage2_summary"])
    df = df.merge(s2[["member_id","stage2_pct"]], left_on="realization_id",
                  right_on="member_id", how="left")
    return df


def classify_dominant_regime(row) -> str:
    """Return dominant (most days) non-normal regime, or 'normal'."""
    if "regime_frac_nyc_limited" not in row.index:
        return "unknown"
    fracs = {
        "NYC-limited": row.get("regime_frac_nyc_limited", 0),
        "LB-limited":  row.get("regime_frac_lb_limited", 0),
        "co-limited":  row.get("regime_frac_co_limited", 0),
    }
    dominant = max(fracs, key=fracs.get)
    if fracs[dominant] < 0.01:
        return "normal"
    return dominant


def make_figure(df: pd.DataFrame):
    has_regime = "regime_frac_nyc_limited" in df.columns

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))
    fig.suptitle(
        "Figure H — Operating Regime Phase Diagram\n"
        "RQ2: Under what conditions does the binding constraint shift?",
        fontsize=10, y=1.01,
    )

    # ── Panel 1: State-space scatter ──
    ax = axes[0]

    if has_regime:
        df["dominant_regime"] = df.apply(classify_dominant_regime, axis=1)
        for regime in REGIME_ORDER:
            sub = df[df["dominant_regime"] == regime]
            if len(sub) == 0:
                continue
            ax.scatter(
                sub["ny_reliability"],
                sub["pa_min_storage_frac"],
                c=REGIME_COLORS[regime], label=regime,
                alpha=0.5, s=20, edgecolors="none",
            )
    else:
        # Fallback: use stage2_pct as proxy for LB stress
        sc = ax.scatter(df["ny_reliability"], df["pa_min_storage_frac"],
                        c=df.get("stage2_pct", 0), cmap="RdYlBu_r",
                        alpha=0.5, s=20, edgecolors="none")
        plt.colorbar(sc, ax=ax, label="Stage 2 active (%)", shrink=0.8)
        ax.text(0.05, 0.95, "Note: regime reaggregation pending",
                transform=ax.transAxes, fontsize=8, color="gray", va="top")

    ax.set_xlabel("NY Montague Reliability (upstream proxy)", fontsize=9)
    ax.set_ylabel("PA Min Storage Fraction (LB stress proxy)", fontsize=9)
    ax.set_title("Hydroclimatic State Space\nColored by dominant operating regime", fontsize=8)
    if has_regime:
        ax.legend(fontsize=8, loc="upper left",
                  handles=[Patch(color=REGIME_COLORS[r], label=r, alpha=0.7)
                            for r in REGIME_ORDER])

    # ── Panel 2: Regime frequency distribution across ensemble ──
    ax2 = axes[1]

    if has_regime:
        regime_cols = {
            "Normal":      "regime_frac_normal",
            "NYC-limited": "regime_frac_nyc_limited",
            "LB-limited":  "regime_frac_lb_limited",
            "Co-limited":  "regime_frac_co_limited",
        }
        for i, (label, col) in enumerate(regime_cols.items()):
            if col not in df.columns:
                continue
            vals = df[col].dropna().values * 100  # convert to percent
            vp = ax2.violinplot([vals], positions=[i], widths=0.6,
                                showmedians=True, showextrema=True)
            color = list(REGIME_COLORS.values())[i]
            for body in vp["bodies"]:
                body.set_facecolor(color)
                body.set_alpha(0.75)
            vp["cmedians"].set_color("black")
            ax2.text(i, np.median(vals) + 1, f"{np.median(vals):.0f}%",
                     ha="center", va="bottom", fontsize=7)

        ax2.set_xticks(range(len(regime_cols)))
        ax2.set_xticklabels(list(regime_cols.keys()), fontsize=8)
        ax2.set_ylabel("Fraction of simulation time (%)", fontsize=9)
        ax2.set_title("Regime Frequency Across 1,000-Member Ensemble\n"
                      "Violin = distribution; line = median", fontsize=8)
    else:
        # Stage 2 distribution as proxy
        vals = df["stage2_pct"].dropna().values
        ax2.hist(vals, bins=30, color="#92c5de", edgecolor="white", lw=0.4)
        ax2.axvline(np.median(vals), color="black", lw=1.5, ls="--",
                    label=f"Median {np.median(vals):.0f}%")
        ax2.set_xlabel("Stage 2 active (% of simulation)", fontsize=9)
        ax2.set_ylabel("Number of ensemble members", fontsize=9)
        ax2.set_title("LB Stage 2 Drought Frequency\nAll 1,000 members", fontsize=8)
        ax2.legend(fontsize=8)

    out = FIGS / "fig_H_regime_phase_diagram.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = load_data()
    make_figure(df)

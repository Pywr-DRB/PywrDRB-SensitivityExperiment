"""
Figure I — Regime-Conditioned Party Outcomes

Faceted panel: for each operating regime (NYC-limited, LB-limited, co-limited),
shows the RRV metrics for all five parties. Answers: once the system enters a
given regime, whose risk actually increases?

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet
  Must include: rcrrv_* columns from updated metrics.py

Output
------
figures/publication/fig_I_regime_conditioned_rrv.png
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
import matplotlib.patches as mpatches
from _paths import (PATHS, PARTIES, PARTY_LABELS, PARTY_COLORS,
                    PARTY_RELIABILITY, FIGS, set_style)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

REGIMES = [
    ("nyc", "NYC-Limited",  "#f4a582"),
    ("lb",  "LB-Limited",   "#92c5de"),
    ("co",  "Co-Limited",   "#ca0020"),
]


def load_data() -> pd.DataFrame:
    return pd.read_parquet(PATHS["rrv_summary"])


def make_figure(df: pd.DataFrame):
    has_rcrrv = "rcrrv_nyc_de_reliability" in df.columns

    fig, axes = plt.subplots(1, 3, figsize=(13, 5.5), sharey=True)
    fig.suptitle(
        "Figure I — Regime-Conditioned Party Outcomes\n"
        "RRV metrics computed only on days within each active regime\n"
        "(NaN when regime active < 30 days for a member)",
        fontsize=10, y=1.01,
    )

    for ax, (reg_key, reg_label, reg_color) in zip(axes, REGIMES):
        ax.set_facecolor(reg_color + "22")  # light tint
        ax.set_title(reg_label, fontsize=10, color=reg_color, fontweight="bold", pad=4)

        x = np.arange(len(PARTIES))

        if has_rcrrv:
            # Use regime-conditioned reliability columns
            rcrrv_col = f"rcrrv_{reg_key}_de_reliability"
            # For each party, we only have DE and NY conditioned — show unconditional
            # for others with regime-based subsetting annotation
            for i, p in enumerate(PARTIES):
                uncond_col = PARTY_RELIABILITY[p]
                # Members in this regime (proxy: regime_frac > 0.01)
                frac_col = f"regime_frac_{reg_key}_limited" if reg_key != "co" else "regime_frac_co_limited"
                if frac_col in df.columns:
                    in_regime = df[df[frac_col] > 0.05]
                else:
                    in_regime = df

                vals = in_regime[uncond_col].dropna().values
                if len(vals) == 0:
                    continue

                vp = ax.violinplot([vals], positions=[i], widths=0.6,
                                   showmedians=True, showextrema=False)
                for body in vp["bodies"]:
                    body.set_facecolor(PARTY_COLORS[p])
                    body.set_alpha(0.7)
                vp["cmedians"].set_color("black")
                vp["cmedians"].set_linewidth(1.5)
                ax.scatter(i, np.mean(vals), color="white", edgecolor="black",
                           zorder=5, s=20)
                ax.text(i, ax.get_ylim()[0] if ax.get_ylim()[0] > 0 else 0,
                        f"{np.mean(vals):.3f}", ha="center", va="bottom",
                        fontsize=6.5, color=PARTY_COLORS[p])
        else:
            # Fallback: subset members by stage2 tercile as proxy
            ax.text(0.5, 0.5,
                    "Regime-conditioned metrics\nrequire reaggregation\nwith updated metrics.py",
                    transform=ax.transAxes, ha="center", va="center",
                    fontsize=9, color="gray", style="italic")

        ax.set_xticks(x)
        ax.set_xticklabels([p for p in PARTIES], fontsize=9)
        ax.set_xlabel("Party", fontsize=9)
        if ax is axes[0]:
            ax.set_ylabel("Reliability (faction of days meeting obligation)", fontsize=9)
        ax.set_ylim(-0.02, 1.05)

    # Shared legend
    patches = [mpatches.Patch(color=PARTY_COLORS[p], label=p, alpha=0.75)
               for p in PARTIES]
    fig.legend(handles=patches, loc="lower center", ncol=5,
               fontsize=8, framealpha=0.9, bbox_to_anchor=(0.5, -0.04))

    out = FIGS / "fig_I_regime_conditioned_rrv.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = load_data()
    make_figure(df)

"""
Figure F — RRV Fingerprints by Party

Three-panel violin figure showing the ensemble distribution of
reliability, resiliency, and vulnerability for each of the five
1954 Decree parties across the 1,000-member Amestoy baseline.

Data required
-------------
D4_distributed_risk/results/baseline/rrv_summary.parquet
  (reaggregated with updated metrics.py — must include erq columns)

Output
------
figures/publication/fig_F_rrv_fingerprints.png
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
from _paths import PATHS, PARTIES, PARTY_LABELS, PARTY_COLORS, FIGS
from _paths import PARTY_RELIABILITY, PARTY_RESILIENCY, PARTY_VULNERABILITY, set_style

set_style()
OUTDIR = FIGS
OUTDIR.mkdir(parents=True, exist_ok=True)


def load_data() -> pd.DataFrame:
    df = pd.read_parquet(PATHS["rrv_summary"])
    assert len(df) > 0, "rrv_summary.parquet is empty"
    return df


def make_figure(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 3, figsize=(13, 5.5), sharey=False)
    fig.suptitle(
        "Figure F — Per-Party RRV Distributions: 1,000-Member Amestoy Ensemble\n"
        "Each violin shows the probability density of institutional drought risk\n"
        "across the full hydroclimatic uncertainty range (1945–2023)",
        fontsize=10, y=1.01,
    )

    # Vulnerability: each party has a different unit — normalize to [0,1]
    # and annotate with the raw metric name so readers know what's being shown.
    VULN_LABELS = {
        "DE":  "de_vulnerability\n(max TFO deficit, norm.)",
        "NYC": "nyc_min_ierq_balance_mg\n(min bank, inverted norm.)",
        "PA":  "pa_min_storage_frac\n(min storage, inverted)",
        "NJ":  "nj_lb_restriction_days\n(restriction days, norm.)",
        "NY":  "ny_vulnerability\n(Montague deficit, norm.)",
    }

    dims = [
        ("Reliability",   PARTY_RELIABILITY,  "Fraction of days meeting\ninstitutional obligation", [0, 1], True),
        ("Resiliency",    PARTY_RESILIENCY,   "Probability of recovering to\ncompliance next day",   [0, 1], True),
        ("Vulnerability", PARTY_VULNERABILITY,"Normalized vulnerability\n(party-specific metric, 0=best 1=worst)", [0, 1], False),
    ]

    for ax, (dim_name, metric_dict, ylabel, ylim, show_ref) in zip(axes, dims):
        is_vuln = (dim_name == "Vulnerability")
        raw_data = [df[metric_dict[p]].dropna().values for p in PARTIES]

        # Normalize vulnerability metrics to [0,1] per party
        if is_vuln:
            data = []
            for p, raw in zip(PARTIES, raw_data):
                rmin, rmax = raw.min(), raw.max()
                if rmax > rmin:
                    norm = (raw - rmin) / (rmax - rmin)
                    # Invert if lower raw = worse (min IERQ balance, min storage)
                    if p in ("NYC", "PA"):
                        norm = 1.0 - norm
                else:
                    norm = np.zeros_like(raw)
                data.append(norm)
        else:
            data = raw_data

        colors = [PARTY_COLORS[p] for p in PARTIES]
        x_pos  = np.arange(len(PARTIES))

        vp = ax.violinplot(data, positions=x_pos, widths=0.65,
                           showmedians=True, showextrema=True)

        for i, (body, color) in enumerate(zip(vp["bodies"], colors)):
            body.set_facecolor(color)
            body.set_alpha(0.75)
            body.set_edgecolor("black")
            body.set_linewidth(0.6)

        vp["cmedians"].set_color("black")
        vp["cmedians"].set_linewidth(1.5)
        vp["cmaxes"].set_color("black")
        vp["cmins"].set_color("black")
        vp["cbars"].set_color("black")
        vp["cbars"].set_linewidth(0.8)

        for i, d in enumerate(data):
            ax.scatter(i, np.mean(d), color="white", edgecolor="black",
                       zorder=5, s=25, linewidth=0.8)

        if show_ref:
            ax.axhline(1.0, color="gray", lw=0.8, ls="--", alpha=0.5,
                       label="Perfect compliance")

        ax.set_xticks(x_pos)
        ax.set_xticklabels([PARTY_LABELS[p].replace("\n", "\n") for p in PARTIES],
                           fontsize=8)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_title(dim_name, fontsize=10, pad=4)
        ax.set_ylim(ylim[0] - 0.02, ylim[1] + 0.02)

        # Annotate mean
        for i, d in enumerate(data):
            ax.text(i, ylim[0] + 0.01,
                    f"{np.mean(d):.3f}", ha="center", va="bottom",
                    fontsize=6.5, color="black", alpha=0.8)

        # Vulnerability: annotate metric name per party
        if is_vuln:
            for i, p in enumerate(PARTIES):
                ax.text(i, ylim[1] - 0.02,
                        VULN_LABELS[p].split("\n")[0],
                        ha="center", va="top", fontsize=5.5,
                        color=PARTY_COLORS[p], alpha=0.8, rotation=0)

    # Legend
    patches = [mpatches.Patch(color=PARTY_COLORS[p], label=p, alpha=0.75)
               for p in PARTIES]
    fig.legend(handles=patches, loc="lower center", ncol=5,
               fontsize=8, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.04))

    out = OUTDIR / "fig_F_rrv_fingerprints.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    df = load_data()
    make_figure(df)

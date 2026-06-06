"""
D4 — Lower Basin storage validation figure.

Shows daily Beltzville + Blue Marsh storage for three representative Amestoy
ensemble members (dry, median, wet) with FFMP drought stage threshold lines.

Answers: does Stage 2 (LB Drought) actually activate in the simulation?
How deep and how often?

Usage
-----
    cd ~/dissertation
    python D4_distributed_risk/figures/plot_lb_storage_validation.py
"""

from __future__ import annotations
import pathlib, sys
import h5py
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = pathlib.Path(__file__).resolve().parents[3]
BASELINE = REPO / "D4_distributed_risk" / "results" / "baseline"
OUTDIR   = REPO / "D4_distributed_risk" / "figures"
OUTDIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Reservoir constants (DRBC usable storage)
# ---------------------------------------------------------------------------
BETZ_CAP_MG = 13_500.0   # Beltzville usable
BM_CAP_MG   =  7_450.0   # Blue Marsh usable
LB_CAP_MG   = BETZ_CAP_MG + BM_CAP_MG  # 20,950 MG

# Threshold fractions (Water Code §2.5.6)
WARNING_FRAC  = (0.737 * BETZ_CAP_MG + 0.689 * BM_CAP_MG) / LB_CAP_MG   # ≈ 0.720
STAGE2_BETZ   = 0.380   # Beltzville Stage 2 entry (§2.5.6.D)
STAGE2_BM     = 0.368   # Blue Marsh  Stage 2 entry (§2.5.6.D)
STAGE2_FRAC   = (STAGE2_BETZ * BETZ_CAP_MG + STAGE2_BM * BM_CAP_MG) / LB_CAP_MG  # ≈ 0.376

WARNING_MG  = WARNING_FRAC * LB_CAP_MG
STAGE2_MG   = STAGE2_FRAC  * LB_CAP_MG

# ---------------------------------------------------------------------------
# Members to plot
# ---------------------------------------------------------------------------
MEMBERS = {
    "Dry (m=0718)":    718,
    "Median (m=0143)": 143,
    "Wet (m=0146)":    146,
}


def load_lb_storage(member_id: int) -> pd.Series:
    """Load combined usable LB storage (MG) for one Amestoy member."""
    mdir = BASELINE / f"member_{member_id:04d}"
    hdf  = next(mdir.glob("*.hdf5"))
    with h5py.File(hdf, "r") as f:
        betz = f["reservoir_beltzvilleCombined"][:].ravel()
        bm   = f["reservoir_blueMarsh"][:].ravel()
    dates = pd.date_range("1945-01-01", periods=len(betz), freq="D")
    betz_s = pd.Series(betz, index=dates).clip(upper=BETZ_CAP_MG)
    bm_s   = pd.Series(bm,   index=dates).clip(upper=BM_CAP_MG)
    return (betz_s + bm_s).clip(lower=0.0)


def stage2_mask(storage: pd.Series) -> pd.Series:
    """Boolean mask: both reservoirs below Stage 2 threshold simultaneously."""
    return storage < STAGE2_MG


def count_stage2_days(storage: pd.Series) -> int:
    return int(stage2_mask(storage).sum())


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------
def make_figure():
    fig = plt.figure(figsize=(13, 12))
    # 3 timeseries panels + 1 distribution panel
    gs = fig.add_gridspec(4, 1, height_ratios=[2, 2, 2, 2.2], hspace=0.45)
    ts_axes  = [fig.add_subplot(gs[i]) for i in range(3)]
    dist_ax  = fig.add_subplot(gs[3])

    fig.suptitle(
        "Lower Basin Reservoir Stage 2 Drought Activation — Amestoy Ensemble (1945–2023)\n"
        "Beltzville + Blue Marsh combined usable storage  |  DRBC Water Code §2.5.6",
        fontsize=11, y=0.99,
    )

    colors = {"Dry (m=0718)": "#d62728", "Median (m=0143)": "#1f77b4", "Wet (m=0146)": "#2ca02c"}
    threshold_alpha = 0.85

    # --- Timeseries panels ---
    for ax, (label, mid) in zip(ts_axes, MEMBERS.items()):
        storage = load_lb_storage(mid)
        frac    = storage / LB_CAP_MG

        ax.fill_between(storage.index, frac, alpha=0.30, color=colors[label])
        ax.plot(storage.index, frac, lw=0.5, color=colors[label])

        ax.axhline(WARNING_FRAC, color="darkorange", lw=1.3, ls="--",
                   alpha=threshold_alpha, label=f"Warning ({WARNING_FRAC:.2f})")
        ax.axhline(STAGE2_FRAC,  color="firebrick",  lw=1.3, ls=":",
                   alpha=threshold_alpha, label=f"Stage 2 ({STAGE2_FRAC:.2f})")
        ax.axhline(0.0, color="black", lw=0.6, alpha=0.4)

        mask = stage2_mask(storage)
        ax.fill_between(storage.index, 0, frac.where(mask, np.nan),
                        color="firebrick", alpha=0.40, label="Stage 2 active")

        n_warning = int((frac < WARNING_FRAC).sum())
        n_stage2  = count_stage2_days(storage)
        ax.text(0.01, 0.05,
                f"Below Warning: {n_warning:,} d ({n_warning/len(frac)*100:.0f}%)   "
                f"Stage 2 active: {n_stage2:,} d ({n_stage2/len(frac)*100:.0f}%)",
                transform=ax.transAxes, fontsize=8,
                va="bottom", ha="left",
                bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85))

        ax.set_ylabel("Fraction of\nusable capacity", fontsize=8.5)
        ax.set_ylim(-0.02, 1.05)
        ax.set_xlim(storage.index[0], storage.index[-1])
        ax.set_title(label, fontsize=9.5, loc="left", pad=2)
        ax.legend(fontsize=7.5, loc="upper right", framealpha=0.85, ncol=3)
        ax.grid(axis="y", alpha=0.25, lw=0.5)
        ax.tick_params(labelsize=8)
        if ax is not ts_axes[-1]:
            ax.set_xticklabels([])

    ts_axes[-1].set_xlabel("Year", fontsize=9)

    # --- Distribution panel ---
    s2_csv = BASELINE / "stage2_days_summary.csv"
    df_s2  = pd.read_csv(s2_csv)
    pcts   = df_s2["stage2_pct"].values

    n_bins = 40
    dist_ax.hist(pcts, bins=n_bins, color="#5a7fb5", edgecolor="white",
                 linewidth=0.4, alpha=0.85)

    # Mark the three highlighted members
    member_pcts = {}
    for label, mid in MEMBERS.items():
        row = df_s2[df_s2["member_id"] == mid]
        if len(row):
            pct = float(row["stage2_pct"].values[0])
            member_pcts[label] = pct
            dist_ax.axvline(pct, color=colors[label], lw=1.8, ls="-",
                            label=f"{label.split('(')[0].strip()}: {pct:.0f}%")

    # Ensemble percentiles
    p5, p50, p95 = np.percentile(pcts, [5, 50, 95])
    dist_ax.axvline(p50, color="black", lw=1.4, ls="--",
                    label=f"Median: {p50:.0f}%")
    dist_ax.axvspan(p5, p95, alpha=0.08, color="black",
                    label=f"5th–95th: {p5:.0f}–{p95:.0f}%")

    dist_ax.set_xlabel("Fraction of 79-year simulation with Stage 2 active (%)", fontsize=9)
    dist_ax.set_ylabel("Number of\nensemble members", fontsize=8.5)
    dist_ax.set_title(
        f"Ensemble distribution — Stage 2 activation across 1,000 Amestoy members\n"
        f"All 1,000 members experience Stage 2  |  mean {pcts.mean():.0f}%  "
        f"[5th–95th: {p5:.0f}–{p95:.0f}%]",
        fontsize=9, loc="left", pad=3,
    )
    dist_ax.legend(fontsize=8, loc="upper left", framealpha=0.85)
    dist_ax.grid(axis="y", alpha=0.25, lw=0.5)
    dist_ax.tick_params(labelsize=8)

    out = OUTDIR / "lb_storage_validation.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    make_figure()

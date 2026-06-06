"""
D4 — Run pywrdrb with observed pub_nhmv10_BC_withObsScaled flows and
produce a Lower Basin drought stage validation figure.

Panels
------
1. Full 1945–2023 daily LB combined usable storage vs Warning / Stage 2 thresholds
2. Zoom: three historical drought periods (1963, 1998–2002, 2016)
3. Model drought stage time series vs storage-derived stage

Usage
-----
    cd ~/dissertation
    module load python/3.11.5 && source venv/bin/activate
    python D4_distributed_risk/scripts/figures/run_pub_validation.py
"""

from __future__ import annotations
import sys, pathlib, json

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "shared"))
sys.path.insert(0, str(REPO))

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

import pywrdrb
from pywrdrb_utils.run_model import run_single
from D4_distributed_risk.lib.rrv_metrics.metrics import (
    compute_all_party_rrv,
    LB_BELTZVILLE_CAPACITY_MG,
    LB_BLUEMARSH_CAPACITY_MG,
    LB_CONSERVATION_FRAC,
)
from D4_distributed_risk.experiments.run_d4_baseline import LB_CAPACITY_MG

OUTDIR = REPO / "D4_distributed_risk" / "figures"
OUTDIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
BETZ_CAP   = LB_BELTZVILLE_CAPACITY_MG   # 13,500 MG
BM_CAP     = LB_BLUEMARSH_CAPACITY_MG    #  7,450 MG
LB_CAP     = LB_CAPACITY_MG              # 20,950 MG

WARNING_FRAC = LB_CONSERVATION_FRAC       # ≈ 0.720  (§2.5.6.C)
STAGE2_FRAC  = (0.380 * BETZ_CAP + 0.368 * BM_CAP) / LB_CAP  # ≈ 0.376  (§2.5.6.D)

# Historical drought periods to zoom
DROUGHT_PERIODS = {
    "1963 drought":    ("1962-01-01", "1964-12-31"),
    "1998–2002 drought": ("1997-01-01", "2003-12-31"),
    "2016 drought":    ("2015-01-01", "2018-12-31"),
}

# ---------------------------------------------------------------------------
# Step 1 — Load observed flows and run model
# ---------------------------------------------------------------------------
INFLOW_TYPE = "pub_nhmv10_BC_withObsScaled"

print(f"Loading historical flows ({INFLOW_TYPE}) ...")
pn_config = pywrdrb.get_pn_config()
flow_csv  = pathlib.Path(pn_config[f"flows/{INFLOW_TYPE}"]) / "catchment_inflow_mgd.csv"
flow_df   = pd.read_csv(flow_csv, index_col=0, parse_dates=True)
print(f"  Flows loaded: {flow_df.index[0].date()} – {flow_df.index[-1].date()}, {flow_df.shape[1]} nodes")

print("Running pywrdrb ...")
outputs = run_single(
    flow_df=flow_df,
    inflow_type=INFLOW_TYPE,
    cleanup=True,
)
print("  Model run complete.")

# ---------------------------------------------------------------------------
# Step 2 — Extract storage and drought stage
# ---------------------------------------------------------------------------
betz_raw = outputs.get("beltzville_volume", pd.Series(dtype=float))
bm_raw   = outputs.get("blueMarsh_volume",   pd.Series(dtype=float))
lb_stage = outputs.get("lb_drought_stage",   pd.Series(dtype=float))

betz = betz_raw.clip(upper=BETZ_CAP)
bm   = bm_raw.clip(upper=BM_CAP)
lb_combined = (betz + bm).clip(lower=0.0)
lb_frac     = lb_combined / LB_CAP

# Storage-derived stage for comparison
stage_derived = pd.Series(0, index=lb_frac.index, dtype=int)
stage_derived[lb_frac < WARNING_FRAC] = 1   # Warning
stage_derived[lb_frac < STAGE2_FRAC]  = 2   # Stage 2 Drought

# ---------------------------------------------------------------------------
# Step 3 — Compute and print metrics
# ---------------------------------------------------------------------------
metrics = compute_all_party_rrv(outputs, lb_capacity_mg=LB_CAP)
print("\n=== Observed-flow RRV metrics ===")
for k, v in metrics.items():
    if isinstance(v, float):
        print(f"  {k:<35s} {v:.4f}")

metrics_path = OUTDIR / "pub_validation_metrics.json"
with open(metrics_path, "w") as f:
    json.dump({k: (round(v, 6) if isinstance(v, float) else v) for k, v in metrics.items()}, f, indent=2)
print(f"\nMetrics saved: {metrics_path}")

# ---------------------------------------------------------------------------
# Step 4 — Figure
# ---------------------------------------------------------------------------
stage_colors = {0: "#d0e8d0", 1: "#ffd966", 2: "#e06c6c"}
stage_labels = {0: "Normal", 1: "Warning", 2: "Stage 2 Drought"}

fig = plt.figure(figsize=(14, 13))
gs  = GridSpec(3, 3, figure=fig, height_ratios=[3, 2.5, 2.5], hspace=0.5, wspace=0.35)

ax_full  = fig.add_subplot(gs[0, :])          # full timeseries
zoom_axes = [fig.add_subplot(gs[1, i]) for i in range(3)]   # 3 drought zooms
ax_stage = fig.add_subplot(gs[2, :])          # drought stage comparison

fig.suptitle(
    "Lower Basin Drought Stage Validation — Observed Flows (pub_nhmv10_BC_withObsScaled, 1945–2023)\n"
    "Beltzville + Blue Marsh combined usable storage  |  DRBC Water Code §2.5.6",
    fontsize=11, y=1.01,
)

# ── Panel 1: Full timeseries ──
ax = ax_full
ax.fill_between(lb_frac.index, lb_frac, alpha=0.35, color="#4878d0")
ax.plot(lb_frac.index, lb_frac, lw=0.5, color="#4878d0")

ax.axhline(WARNING_FRAC, color="darkorange", lw=1.5, ls="--",
           label=f"Warning threshold ({WARNING_FRAC:.2f})", alpha=0.9)
ax.axhline(STAGE2_FRAC,  color="firebrick",  lw=1.5, ls=":",
           label=f"Stage 2 threshold ({STAGE2_FRAC:.2f})", alpha=0.9)

mask_s2 = lb_frac < STAGE2_FRAC
ax.fill_between(lb_frac.index, 0, lb_frac.where(mask_s2, np.nan),
                color="firebrick", alpha=0.45, label="Stage 2 active")

n_warn = int((lb_frac < WARNING_FRAC).sum())
n_s2   = int(mask_s2.sum())
ax.text(0.01, 0.04,
        f"Below Warning: {n_warn:,} days ({n_warn/len(lb_frac)*100:.0f}%)   "
        f"Stage 2 active: {n_s2:,} days ({n_s2/len(lb_frac)*100:.0f}%)",
        transform=ax.transAxes, fontsize=8.5,
        va="bottom", bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.85))

# Mark drought zoom windows
zoom_colors = ["#8B4513", "#2F4F4F", "#8B008B"]
for (label, (t0, t1)), zc in zip(DROUGHT_PERIODS.items(), zoom_colors):
    ax.axvspan(pd.Timestamp(t0), pd.Timestamp(t1), alpha=0.12, color=zc)

ax.set_ylabel("Fraction of usable capacity", fontsize=9)
ax.set_ylim(-0.02, 1.05)
ax.set_xlim(lb_frac.index[0], lb_frac.index[-1])
ax.set_title("Full simulation period", fontsize=9.5, loc="left", pad=3)
ax.legend(fontsize=8, loc="upper right", framealpha=0.9, ncol=3)
ax.grid(axis="y", alpha=0.25, lw=0.5)
ax.tick_params(labelsize=8)

# ── Panels 2a-c: Drought zooms ──
for ax_z, (label, (t0, t1)), zc in zip(zoom_axes, DROUGHT_PERIODS.items(), zoom_colors):
    sub = lb_frac.loc[t0:t1]
    ax_z.fill_between(sub.index, sub, alpha=0.35, color="#4878d0")
    ax_z.plot(sub.index, sub, lw=0.8, color="#4878d0")
    ax_z.axhline(WARNING_FRAC, color="darkorange", lw=1.3, ls="--", alpha=0.9)
    ax_z.axhline(STAGE2_FRAC,  color="firebrick",  lw=1.3, ls=":",  alpha=0.9)

    mask_sub = sub < STAGE2_FRAC
    ax_z.fill_between(sub.index, 0, sub.where(mask_sub, np.nan),
                      color="firebrick", alpha=0.45)

    n_s2_sub = int(mask_sub.sum())
    ax_z.text(0.03, 0.04,
              f"Stage 2: {n_s2_sub:,} d ({n_s2_sub/len(sub)*100:.0f}%)",
              transform=ax_z.transAxes, fontsize=7.5,
              va="bottom", bbox=dict(boxstyle="round,pad=0.25", fc="white", alpha=0.85))

    ax_z.set_ylim(-0.02, 1.05)
    ax_z.set_xlim(pd.Timestamp(t0), pd.Timestamp(t1))
    ax_z.set_title(label, fontsize=9, loc="left", pad=2, color=zc, fontweight="bold")
    ax_z.grid(axis="y", alpha=0.25, lw=0.5)
    ax_z.tick_params(labelsize=7.5)
    ax_z.set_ylabel("Fraction of usable capacity", fontsize=8)

# ── Panel 3: Stage comparison ──
ax = ax_stage

# Model stage
if len(lb_stage) > 0:
    for stage_val, color in stage_colors.items():
        mask = lb_stage == stage_val
        ax.fill_between(lb_stage.index, 2.1, 3.0,
                        where=mask.values, color=color, alpha=0.85,
                        step="mid")
    ax.text(lb_stage.index[len(lb_stage)//2], 2.55, "Model stage",
            ha="center", va="center", fontsize=8, fontweight="bold")
else:
    ax.text(0.5, 0.75, "lb_drought_stage not recorded in this run",
            transform=ax.transAxes, ha="center", fontsize=9, color="gray")

# Derived stage
for stage_val, color in stage_colors.items():
    mask = stage_derived == stage_val
    ax.fill_between(stage_derived.index, 0, 0.9,
                    where=mask.values, color=color, alpha=0.85,
                    step="mid")
ax.text(stage_derived.index[len(stage_derived)//2], 0.45, "Storage-derived stage",
        ha="center", va="center", fontsize=8, fontweight="bold")

ax.set_xlim(lb_frac.index[0], lb_frac.index[-1])
ax.set_ylim(-0.1, 3.2)
ax.set_yticks([])
ax.set_xlabel("Year", fontsize=9)
ax.set_title("LB drought stage: model output vs storage-derived  (Normal / Warning / Stage 2)",
             fontsize=9, loc="left", pad=3)
ax.grid(axis="x", alpha=0.2, lw=0.5)
ax.tick_params(labelsize=8)

# Legend for stage colors
patches = [mpatches.Patch(color=c, label=stage_labels[s], alpha=0.85)
           for s, c in stage_colors.items()]
ax.legend(handles=patches, fontsize=8, loc="upper right", framealpha=0.9)

out = OUTDIR / "lb_storage_pub_validation.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"\nFigure saved: {out}")

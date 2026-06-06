"""
NJ Delivery Coupling Figure — LB × NYC drought factor interaction.

Shows how the combined NJ delivery cap is the minimum of the LB drought factor
and the NYC storage-indexed factor, with actual delivery_nj plotted against it.

Usage
-----
    cd ~/dissertation
    source venv/bin/activate
    python shared/lower_basin_ffmp_dev/plot_nj_lb_coupling.py \\
        [--hdf5 path/to/member.hdf5] \\
        [--outdir shared/lower_basin_ffmp_dev/figures]

Institutional grounding
-----------------------
NJ 100 MGD baseline: 1954 Decree Art. V.B.1
NJ Warning cap (70 MGD): Water Code §2.5.6.C.1
NJ Drought cap (65 MGD): Water Code §2.5.6.D.1
NYC-indexed factor:  FFMP 2017 — delivery_factor varies by NYC drought level
LB×NYC combined:     combined_drought_factor_delivery_nj = min(lb_factor, nyc_factor)

Output
------
    figures/nj_lb_coupling_diagnostic.png  — 4-panel figure
"""

from __future__ import annotations

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd

HERE   = pathlib.Path(__file__).parent
FIGDIR = HERE / "figures"
FIGDIR.mkdir(exist_ok=True)

# Default HDF5: first baseline member (longest run, richest data)
DEFAULT_HDF5 = pathlib.Path(
    "~/dissertation/D4_distributed_risk/results/baseline"
    "/member_0000/obs_pub_nhmv10_BC_ObsScaled_m0000.hdf5"
).expanduser()

# Decree / Water Code thresholds
NJ_NORMAL_MGD  = 100.0
NJ_WARNING_MGD =  70.0
NJ_DROUGHT_MGD =  65.0


def load_hdf5_series(hdf5_path: pathlib.Path) -> dict[str, pd.Series]:
    """Load relevant recorders from pywrdrb HDF5 output."""
    import h5py

    keys_wanted = [
        "combined_drought_factor_delivery_nj",
        "lb_drought_factor_delivery_nj",
        "drought_factor_delivery_nj",   # NYC-only factor
        "delivery_nj",
        "demand_nj",
        "drought_level_agg_lb",
        "drought_level_agg_nyc",
    ]

    with h5py.File(hdf5_path, "r") as f:
        # Determine simulation start date from HDF5 shape
        n_steps = f["delivery_nj"].shape[0]
        # pywrdrb baseline uses 1945-01-01 start
        dates = pd.date_range("1945-01-01", periods=n_steps, freq="D")

        out = {}
        for key in keys_wanted:
            if key in f:
                arr = np.array(f[key])
                vals = arr[:, 0] if arr.ndim == 2 else arr
                out[key] = pd.Series(vals, index=dates, name=key)
            else:
                print(f"  WARNING: {key} not in HDF5 — skipping")

    return out


def make_nj_coupling_figure(data: dict[str, pd.Series], out_path: pathlib.Path):
    """
    4-panel diagnostic figure.

    Panel 1: Factor timeseries — LB factor, NYC factor, combined=min(LB,NYC)
    Panel 2: Implied effective cap (100 × combined) vs actual delivery_nj
    Panel 3: LB and NYC drought stages (drives the factors)
    Panel 4: Regime attribution — days per coupling mode each year
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.dates as mdates
    import matplotlib.ticker as ticker

    # Focus on a representative window: longest period with drought action
    # Use full run for panels 3-4, zoom 2003-2005 for panels 1-2
    combined_factor = data.get("combined_drought_factor_delivery_nj")
    lb_factor       = data.get("lb_drought_factor_delivery_nj")
    nyc_factor      = data.get("drought_factor_delivery_nj")
    delivery        = data.get("delivery_nj")
    lb_stage        = data.get("drought_level_agg_lb")
    nyc_stage       = data.get("drought_level_agg_nyc")

    if combined_factor is None or delivery is None:
        print("ERROR: required keys missing from HDF5")
        return

    # Full-run date index
    full_dates = combined_factor.index

    # Zoom window for panels 1-2: pick the period with most LB drought action
    # Use 2003-01-01 to 2006-12-31 (covers 2004 Drought + surrounding)
    zoom_start = "2003-01-01"
    zoom_end   = "2006-12-31"
    zm = (full_dates >= zoom_start) & (full_dates <= zoom_end)
    dates_z = full_dates[zm]

    def clip(s):
        return s[zm] if s is not None else None

    # Implied effective cap
    eff_cap  = combined_factor * NJ_NORMAL_MGD
    eff_cap_z = clip(eff_cap)

    # Regime classification (per day, full run)
    # "normal"   : combined_factor == 1.0
    # "lb_only"  : lb_factor < 1.0, nyc_factor == 1.0
    # "nyc_only" : lb_factor == 1.0, nyc_factor < 1.0
    # "co_limited": both < 1.0
    if lb_factor is not None and nyc_factor is not None:
        is_lb_limited  = (lb_factor < 0.999) & (nyc_factor >= 0.999)
        is_nyc_limited = (lb_factor >= 0.999) & (nyc_factor < 0.999)
        is_co_limited  = (lb_factor < 0.999) & (nyc_factor < 0.999)
        is_normal      = (lb_factor >= 0.999) & (nyc_factor >= 0.999)
    else:
        is_lb_limited  = combined_factor < 0.999
        is_nyc_limited = pd.Series(False, index=full_dates)
        is_co_limited  = pd.Series(False, index=full_dates)
        is_normal      = ~is_lb_limited

    REGIME_COLORS = {
        "normal":      "#d5f5e3",
        "lb_only":     "#fdebd0",
        "nyc_only":    "#d6eaf8",
        "co_limited":  "#fadbd8",
    }

    # ---- Figure layout --------------------------------------------------------
    fig, axes = plt.subplots(
        4, 1, figsize=(15, 14),
        gridspec_kw={"height_ratios": [2, 2, 1.5, 2]},
    )
    fig.suptitle(
        "NJ Delivery Coupling: LB × NYC Drought Factor Interaction\n"
        "combined_drought_factor_delivery_nj = min(lb_factor, nyc_factor)\n"
        "Decree Art. V.B.1 · Water Code §2.5.6.B/C/D · FFMP 2017",
        fontsize=12, fontweight="bold", y=0.998,
    )

    def shade_regime(ax, dates, mask_lb, mask_nyc, mask_co, mask_norm):
        """Add coloured background for each coupling regime."""
        for mask, color in [
            (mask_norm, REGIME_COLORS["normal"]),
            (mask_lb,   REGIME_COLORS["lb_only"]),
            (mask_nyc,  REGIME_COLORS["nyc_only"]),
            (mask_co,   REGIME_COLORS["co_limited"]),
        ]:
            m = mask.reindex(dates, fill_value=False)
            i = 0
            while i < len(dates):
                if m.iloc[i]:
                    j = i
                    while j < len(dates) and m.iloc[j]:
                        j += 1
                    ax.axvspan(dates[i], dates[min(j, len(dates)-1)],
                               alpha=0.25, color=color, zorder=0)
                    i = j
                else:
                    i += 1

    # ============================================================
    # Panel 1: Factor timeseries (zoomed window)
    # ============================================================
    ax1 = axes[0]
    shade_regime(ax1, dates_z,
                 is_lb_limited[zm], is_nyc_limited[zm],
                 is_co_limited[zm], is_normal[zm])

    if lb_factor is not None:
        ax1.step(dates_z, clip(lb_factor), where="post",
                 color="#e67e22", lw=1.8, label="lb_drought_factor (LB stage → NJ cap)")
    if nyc_factor is not None:
        ax1.step(dates_z, clip(nyc_factor), where="post",
                 color="#2980b9", lw=1.8, label="drought_factor_delivery_nj (NYC stage → NJ cap)")
    ax1.step(dates_z, clip(combined_factor), where="post",
             color="#c0392b", lw=2.2, ls="--",
             label="combined = min(LB, NYC)  [model uses this]")

    ax1.axhline(1.00, color="k",      lw=0.7, ls=":", alpha=0.5, label="Normal (100 MGD)")
    ax1.axhline(0.70, color="#e67e22", lw=0.7, ls=":",  alpha=0.5, label="Warning (0.70 × 100 = 70 MGD)")
    ax1.axhline(0.65, color="#c0392b", lw=0.7, ls=":",  alpha=0.5, label="Drought (0.65 × 100 = 65 MGD)")

    ax1.set_ylabel("Delivery factor\n(× 100 MGD normal cap)", fontsize=10)
    ax1.set_ylim(0.60, 1.08)
    ax1.set_xlim(dates_z[0], dates_z[-1])
    ax1.legend(fontsize=8, loc="lower right", ncol=2)
    ax1.set_title(
        "NJ Delivery Factors  (§2.5.6.B: normal 1.0  ·  §2.5.6.C: warning 0.70  ·  §2.5.6.D: drought 0.65)",
        fontsize=9, loc="left",
    )
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # ============================================================
    # Panel 2: Effective cap vs actual delivery (zoomed)
    # ============================================================
    ax2 = axes[1]
    shade_regime(ax2, dates_z,
                 is_lb_limited[zm], is_nyc_limited[zm],
                 is_co_limited[zm], is_normal[zm])

    ax2.fill_between(dates_z, NJ_NORMAL_MGD, eff_cap_z.values,
                     step="post", alpha=0.35, color="#e74c3c",
                     label="Active restriction band (below 100 MGD cap)")
    ax2.step(dates_z, eff_cap_z, where="post",
             color="#c0392b", lw=2.0, label="Effective cap (100 × combined factor)")
    ax2.step(dates_z, clip(delivery), where="post",
             color="#2c3e50", lw=1.2, alpha=0.8, label="Actual delivery_nj (MGD)")

    ax2.axhline(NJ_NORMAL_MGD,  color="k",       ls=":", lw=1.0,
                label=f"Normal cap {NJ_NORMAL_MGD:.0f} MGD (Decree Art. V.B.1)")
    ax2.axhline(NJ_WARNING_MGD, color="#e67e22",  ls=":", lw=1.0,
                label=f"Warning cap {NJ_WARNING_MGD:.0f} MGD (§2.5.6.C.1)")
    ax2.axhline(NJ_DROUGHT_MGD, color="#c0392b",  ls=":", lw=1.0,
                label=f"Drought cap {NJ_DROUGHT_MGD:.0f} MGD (§2.5.6.D.1)")

    ax2.set_ylabel("NJ delivery\n(MGD)", fontsize=10)
    ax2.set_ylim(55, 115)
    ax2.set_xlim(dates_z[0], dates_z[-1])
    ax2.legend(fontsize=8, loc="lower right", ncol=2)
    ax2.set_title(
        "Effective NJ Cap vs Actual Delivery  (cap = 100 × combined factor)",
        fontsize=9, loc="left",
    )
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # ============================================================
    # Panel 3: LB and NYC drought stages (zoomed)
    # ============================================================
    ax3 = axes[2]

    if lb_stage is not None:
        ax3.step(dates_z, clip(lb_stage).astype(int), where="post",
                 color="#e67e22", lw=2.0, label="LB drought stage (0–2)")
    if nyc_stage is not None:
        ax3_r = ax3.twinx()
        ax3_r.step(dates_z, clip(nyc_stage).astype(int), where="post",
                   color="#2980b9", lw=1.5, ls="--", alpha=0.7,
                   label="NYC drought level (0–6)")
        ax3_r.set_ylim(-0.5, 7)
        ax3_r.set_yticks([0, 2, 4, 6])
        ax3_r.set_ylabel("NYC drought level", fontsize=9, color="#2980b9")
        ax3_r.tick_params(axis="y", labelcolor="#2980b9")

    ax3.set_ylabel("LB drought stage", fontsize=10, color="#e67e22")
    ax3.tick_params(axis="y", labelcolor="#e67e22")
    ax3.set_ylim(-0.3, 2.6)
    ax3.set_yticks([0, 1, 2])
    ax3.set_yticklabels(["0 Normal", "1 Warning", "2 Drought"], fontsize=8)
    ax3.set_xlim(dates_z[0], dates_z[-1])
    ax3.set_title(
        "Driving Factors: LB Drought Stage (orange, left) · NYC Drought Level (blue, right)",
        fontsize=9, loc="left",
    )
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # ============================================================
    # Panel 4: Annual regime attribution (full run bar chart)
    # ============================================================
    ax4 = axes[3]

    regime_df = pd.DataFrame({
        "Normal":      is_normal.astype(int),
        "LB-limited":  is_lb_limited.astype(int),
        "NYC-limited": is_nyc_limited.astype(int),
        "Co-limited":  is_co_limited.astype(int),
    }, index=full_dates)

    annual_regime = regime_df.resample("YS").sum()
    years = [str(y.year) for y in annual_regime.index]
    x = np.arange(len(years))

    bottom = np.zeros(len(years))
    colors  = [REGIME_COLORS["normal"], REGIME_COLORS["lb_only"],
               REGIME_COLORS["nyc_only"], REGIME_COLORS["co_limited"]]
    labels  = ["Normal (factor = 1.0)", "LB-limited", "NYC-limited", "Co-limited (both)"]
    edgecolors = ["#27ae60", "#e67e22", "#2980b9", "#c0392b"]

    for col, color, label, edge in zip(annual_regime.columns, colors, labels, edgecolors):
        vals = annual_regime[col].values
        ax4.bar(x, vals, bottom=bottom, color=color, edgecolor=edge,
                linewidth=0.8, label=label, alpha=0.85)
        bottom += vals

    ax4.set_xticks(x[::5])
    ax4.set_xticklabels(years[::5], fontsize=8, rotation=45)
    ax4.set_ylabel("Days per year", fontsize=10)
    ax4.set_title(
        "Annual NJ Delivery Coupling Regime  (NJ restricted whenever combined_factor < 1.0)",
        fontsize=9, loc="left",
    )
    ax4.legend(fontsize=8, loc="upper right")
    ax4.axhline(365, color="k", lw=0.5, ls=":")

    # ============================================================
    # Shared legend patches
    # ============================================================
    legend_patches = [
        mpatches.Patch(color=REGIME_COLORS["normal"],     alpha=0.6,
                       label="Normal — factor = 1.0 (NJ gets full 100 MGD)"),
        mpatches.Patch(color=REGIME_COLORS["lb_only"],    alpha=0.6,
                       label="LB-limited — LB drought binding (§2.5.6.C/D)"),
        mpatches.Patch(color=REGIME_COLORS["nyc_only"],   alpha=0.6,
                       label="NYC-limited — NYC storage binding (FFMP 2017)"),
        mpatches.Patch(color=REGIME_COLORS["co_limited"], alpha=0.6,
                       label="Co-limited — both constraints active"),
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=4,
               fontsize=8, frameon=True, bbox_to_anchor=(0.5, 0.00))

    plt.tight_layout(rect=[0, 0.04, 1, 0.995])
    plt.savefig(str(out_path), dpi=150, bbox_inches="tight")
    print(f"  Figure saved → {out_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hdf5",   type=pathlib.Path, default=DEFAULT_HDF5)
    parser.add_argument("--outdir", type=pathlib.Path, default=FIGDIR)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    out_path = args.outdir / "nj_lb_coupling_diagnostic.png"

    print(f"Loading {args.hdf5} …")
    data = load_hdf5_series(args.hdf5)
    print(f"  Loaded {len(data)} series, {len(next(iter(data.values())))} timesteps")

    # Report regime statistics
    combined = data.get("combined_drought_factor_delivery_nj")
    lb_f     = data.get("lb_drought_factor_delivery_nj")
    nyc_f    = data.get("drought_factor_delivery_nj")
    if combined is not None:
        n_total = len(combined)
        n_restricted = (combined < 0.999).sum()
        n_warning    = (combined == 0.70).sum()
        n_drought    = (combined == 0.65).sum()
        if lb_f is not None and nyc_f is not None:
            n_lb_only  = ((lb_f < 0.999) & (nyc_f >= 0.999)).sum()
            n_nyc_only = ((lb_f >= 0.999) & (nyc_f < 0.999)).sum()
            n_co       = ((lb_f < 0.999) & (nyc_f < 0.999)).sum()
            print(f"\n  Regime summary (full run, {n_total} days):")
            print(f"    Normal (factor=1.0)  : {n_total - n_restricted:6d} days ({100*(n_total-n_restricted)/n_total:.1f}%)")
            print(f"    LB-limited only      : {n_lb_only:6d} days ({100*n_lb_only/n_total:.1f}%)")
            print(f"    NYC-limited only     : {n_nyc_only:6d} days ({100*n_nyc_only/n_total:.1f}%)")
            print(f"    Co-limited (both)    : {n_co:6d} days ({100*n_co/n_total:.1f}%)")
        print(f"    Days at warning cap  : {n_warning:6d}  ({100*n_warning/n_total:.1f}%)")
        print(f"    Days at drought cap  : {n_drought:6d}  ({100*n_drought/n_total:.1f}%)")

    make_nj_coupling_figure(data, out_path)


if __name__ == "__main__":
    main()

"""
Figure D — Ensemble drought stress envelope

Tier 1: Amestoy 1000-member inflow fan + storage envelope from baseline reruns.
Tier 2: Kirsch–Nowak 50-realization SOW fan (inset).

Output
------
figures/publication/fig_D_ensemble_drought_envelope.png
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "shared"))
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _paths import FIGS, set_style
from _opening_figures import (
    load_amestoy_ensemble_inflow,
    amestoy_highlight_ids,
    load_ensemble_inflow,
    drought_highlight_ids,
    load_baseline_storage_envelope,
)

set_style()
FIGS.mkdir(parents=True, exist_ok=True)

HIGHLIGHT = {
    "dry":    {"color": "#ca0020", "label": "Dry trace"},
    "normal": {"color": "#4dac26", "label": "Median trace"},
    "wet":    {"color": "#2166ac", "label": "Wet trace"},
}


def _smooth(y: np.ndarray, window: int = 30) -> np.ndarray:
    k = np.ones(window) / window
    return np.convolve(y, k, mode="same")


def _fan_panel(ax, dates, cube, highlights, title, ylab, t_start="1980-01-01", t_end="1990-12-31"):
    smooth = np.vstack([_smooth(row) for row in cube])
    mask = (dates >= np.datetime64(t_start)) & (dates <= np.datetime64(t_end))
    t = np.arange(mask.sum())
    sub = smooth[:, mask]
    p10, p50, p90 = np.percentile(sub, [10, 50, 90], axis=0)

    ax.fill_between(t, p10, p90, color="#92c5de", alpha=0.45,
                    label=f"P10–P90 ({cube.shape[0]} members)")
    ax.plot(t, p50, color="#2166ac", lw=1.0, label="Median")
    for key, ridx in highlights.items():
        if ridx < sub.shape[0]:
            ax.plot(t, sub[ridx], color=HIGHLIGHT[key]["color"], lw=1.3,
                    label=HIGHLIGHT[key]["label"])
    ax.set_title(title, fontsize=9)
    ax.set_ylabel(ylab, fontsize=8)
    ax.legend(loc="upper right", fontsize=6)
    return ax


def make_figure():
    # --- Tier 1: Amestoy ---
    dates_a, cube_a = load_amestoy_ensemble_inflow()
    hi_a = amestoy_highlight_ids(cube_a)

    # --- Tier 2: Kirsch–Nowak ---
    dates_k, cube_k, log_k = load_ensemble_inflow()
    hi_k = drought_highlight_ids(log_k)

    # --- Storage from baseline reruns ---
    storage = load_baseline_storage_envelope(max_members=100)

    fig = plt.figure(figsize=(14, 9))
    gs = fig.add_gridspec(2, 2, height_ratios=[1, 1], hspace=0.35, wspace=0.28)

    ax_a = fig.add_subplot(gs[0, 0])
    _fan_panel(ax_a, dates_a, cube_a, hi_a,
               "Tier 1 — Amestoy inflow envelope (1000 members)",
               "30-day mean basin inflow [MGD]")
    ax_a.set_xlabel("Days (1980–1990 excerpt)", fontsize=8)

    ax_s = fig.add_subplot(gs[0, 1])
    if storage is not None:
        s_dates, nyc_cube, lb_cube = storage
        mask = (s_dates >= np.datetime64("1980-01-01")) & (s_dates <= np.datetime64("1990-12-31"))
        t = np.arange(mask.sum())
        # Fraction of approximate usable capacity
        nyc_cap = np.nanmax(nyc_cube) or 1.0
        lb_cap = 20_950.0  # combined LB usable MG (decree mapping)
        nyc_frac = nyc_cube[:, mask] / nyc_cap
        lb_frac = lb_cube[:, mask] / lb_cap
        for frac, color, label in [
            (nyc_frac, "#f4a582", "NYC combined storage"),
            (lb_frac, "#4dac26", "LB combined storage"),
        ]:
            p10, p50, p90 = np.percentile(frac, [10, 50, 90], axis=0)
            ax_s.fill_between(t, p10, p90, color=color, alpha=0.25)
            ax_s.plot(t, p50, color=color, lw=1.2, label=label)
        ax_s.set_ylim(0, 1.05)
        ax_s.set_ylabel("Storage / usable capacity [-]", fontsize=8)
        ax_s.set_title("Tier 1 — Storage envelope (100 baseline members)", fontsize=9)
        ax_s.legend(loc="lower left", fontsize=6)
        ax_s.set_xlabel("Days (1980–1990 excerpt)", fontsize=8)
    else:
        ax_s.text(0.5, 0.5, "Baseline storage outputs\nnot available",
                  ha="center", va="center", transform=ax_s.transAxes)
        ax_s.axis("off")

    ax_k = fig.add_subplot(gs[1, :])
    _fan_panel(ax_k, dates_k, cube_k, hi_k,
               "Tier 2 — Kirsch–Nowak SOW envelope (50 realizations; ±20% mean shift)",
               "30-day mean basin inflow [MGD]")
    ax_k.set_xlabel("Days (1980–1990 excerpt)", fontsize=8)

    fig.suptitle(
        "Figure D — Hydrologic forcing and storage stress before policy outcomes",
        fontsize=12, fontweight="bold", y=0.98,
    )
    fig.text(
        0.5, 0.01,
        "Tier 1: Amestoy et al. (2025) reconstruction  ·  "
        "Tier 2: Kirsch–Nowak synthetic flows (Sobol sweep 3)  ·  "
        "Storage: Pywr-DRB baseline rerun subset",
        ha="center", fontsize=7.5, color="#666666",
    )
    return fig


def main():
    fig = make_figure()
    out = FIGS / "fig_D_ensemble_drought_envelope.png"
    fig.savefig(out, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()

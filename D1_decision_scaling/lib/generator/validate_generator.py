"""
D1 — Generator calibration validation figure.

Usage
-----
    python validate_generator.py [--out figures/generator_validation.png]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "shared"))

from pywrdrb_utils.kirsch_flows import (
    KIRSCH_SITES,
    calibrate,
    generate_realization,
    get_historical_inflows,
    load_fitted_models,
    validate_against_historical,
)

FITTED_DIRS = [
    _REPO / "D4_distributed_risk" / "results" / "sobol" / "synthetic_flows",
    Path(__file__).parent / "fitted_model",
]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent.parent / "figures" / "generator_validation.png",
    )
    ap.add_argument("--refit", action="store_true")
    args = ap.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    Q_hist = get_historical_inflows()

    fitted_dir = next(
        (d for d in FITTED_DIRS if (d / "kirsch_fitted.pkl").exists()),
        FITTED_DIRS[-1],
    )
    if args.refit or not (fitted_dir / "kirsch_fitted.pkl").exists():
        kirsch_gen, nowak_disagg = calibrate(Q_hist, fitted_dir)
    else:
        kirsch_gen, nowak_disagg = load_fitted_models(fitted_dir)

    val_df = validate_against_historical(kirsch_gen, nowak_disagg, Q_hist, n_samples=10)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))

    # Panel 1: mean annual flow
    ax = axes[0]
    x = np.arange(len(KIRSCH_SITES))
    w = 0.35
    ax.bar(x - w / 2, val_df["historical"], w, label="Historical")
    ax.bar(x + w / 2, val_df["synthetic"], w, label="Synthetic (mean)")
    ax.set_xticks(x)
    ax.set_xticklabels(KIRSCH_SITES, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Mean annual flow (MGD)")
    ax.set_title("Mean annual flow")
    ax.legend(fontsize=8)

    # Panel 2: relative error
    ax = axes[1]
    ax.bar(KIRSCH_SITES, val_df["rel_error"] * 100)
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xticklabels(KIRSCH_SITES, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Rel. error (%)")
    ax.set_title("Synthetic vs historical mean")

    # Panel 3: sample delMontague trace (first year)
    ax = axes[2]
    syn = generate_realization(kirsch_gen, nowak_disagg, Q_hist, seed=42)
    hist = Q_hist["delMontague"].loc["1946-01-01":"1946-12-31"]
    syn_y1 = syn["delMontague"].loc["1945-01-01":"1945-12-31"]
    ax.plot(hist.values, label="Historical 1946", alpha=0.8)
    ax.plot(syn_y1.values, label="Synthetic yr 1", alpha=0.8)
    ax.set_xlabel("Day of year")
    ax.set_ylabel("Montague flow (MGD)")
    ax.set_title("Daily Montague (year 1)")
    ax.legend(fontsize=8)

    fig.suptitle("D1 Kirsch-Nowak generator validation", fontsize=11)
    fig.tight_layout()
    fig.savefig(args.out, dpi=150)
    print(f"Saved {args.out}")
    val_df.to_csv(args.out.with_suffix(".csv"), index=False)


if __name__ == "__main__":
    main()

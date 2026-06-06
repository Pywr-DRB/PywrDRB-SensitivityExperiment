"""
D1 RQ2 — Attribution shift across scenario space (NYC-limited vs LB-limited).

Usage
-----
    python analysis/rq2_attribution_shift.py \
        --summary results/failure_surface/d1_v1_7x6x3_r30/failure_surface_summary.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "D1_decision_scaling" / "experiments"))
from config import CONFIG_NAME


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    default = _REPO / "D1_decision_scaling" / "results" / "failure_surface" / CONFIG_NAME
    ap.add_argument("--summary", type=Path, default=default / "failure_surface_summary.parquet")
    ap.add_argument("--outdir", type=Path, default=default / "analysis" / "rq2")
    ap.add_argument("--lb-level", default="LB1")
    args = ap.parse_args()

    df = pd.read_parquet(args.summary)
    if args.lb_level:
        df = df[df["lb_level_id"] == args.lb_level]
    failed = df[df["cell_fails"]].copy()

    args.outdir.mkdir(parents=True, exist_ok=True)

    if failed.empty:
        print("No failed cells in summary — run sweep first.")
        failed.to_csv(args.outdir / "regime_by_slr.csv", index=False)
        return

    by_slr = (
        failed.groupby("slr_id")["dominant_regime"]
        .value_counts(normalize=True)
        .unstack(fill_value=0.0)
        .reset_index()
    )
    by_slr.to_csv(args.outdir / "regime_fraction_by_slr.csv", index=False)

    by_flow = (
        failed.groupby("flow_bin_id")["dominant_regime"]
        .value_counts(normalize=True)
        .unstack(fill_value=0.0)
        .reset_index()
    )
    by_flow.to_csv(args.outdir / "regime_fraction_by_flow_bin.csv", index=False)

    print("RQ2 regime fractions by SLR (failed cells only):")
    print(by_slr.to_string(index=False))
    print(f"\nWrote → {args.outdir}")


if __name__ == "__main__":
    main()

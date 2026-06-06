"""
D1 RQ1 — Failure boundary and shift vs flow target (SLR/TFO).

Usage
-----
    python analysis/rq1_failure_boundary.py \
        --summary results/failure_surface/d1_v1_7x6x3_r30/failure_surface_summary.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "D1_decision_scaling" / "experiments"))
from config import CONFIG_NAME, SLR_LEVELS, STREAMFLOW_BINS


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    default = _REPO / "D1_decision_scaling" / "results" / "failure_surface" / CONFIG_NAME
    ap.add_argument("--summary", type=Path, default=default / "failure_surface_summary.parquet")
    ap.add_argument("--outdir", type=Path, default=default / "analysis" / "rq1")
    ap.add_argument("--lb-level", default="LB1")
    args = ap.parse_args()

    df = pd.read_parquet(args.summary)
    if args.lb_level:
        df = df[df["lb_level_id"] == args.lb_level]

    args.outdir.mkdir(parents=True, exist_ok=True)

    # Failure area vs SLR (fraction of flow bins failing)
    by_slr = (
        df.groupby("slr_id")
        .agg(
            n_cells=("cell_fails", "count"),
            n_failed=("cell_fails", "sum"),
            mean_failure_fraction=("failure_fraction", "mean"),
        )
        .reset_index()
    )
    by_slr["failure_area_fraction"] = by_slr["n_failed"] / by_slr["n_cells"]
    by_slr.to_csv(args.outdir / "failure_area_by_slr.csv", index=False)

    # Heatmap data: flow_bin × slr
    pivot = df.pivot_table(
        index="flow_bin_id",
        columns="slr_id",
        values="failure_fraction",
        aggfunc="mean",
    )
    pivot.to_csv(args.outdir / "failure_fraction_heatmap.csv")

    print("RQ1 outputs:")
    print(by_slr.to_string(index=False))
    print(f"\nWrote → {args.outdir}")


if __name__ == "__main__":
    main()

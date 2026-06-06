"""
D1 RQ3 — GCM-weighted failure mass vs flow target level; tipping-point SLR.

P(fail | GCM, SLR) = sum over flow bins of [bin_weight × P(fail | flow_bin, SLR)]

Usage
-----
    python analysis/rq3_gcm_failure_mass.py \
        --summary results/failure_surface/d1_v1_7x6x3_r30/failure_surface_summary.parquet \
        --weights scenario_extraction/cmip6_cell_weights_montague.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO / "D1_decision_scaling" / "experiments"))
from config import CONFIG_NAME, SLR_LEVELS


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    default = _REPO / "D1_decision_scaling" / "results" / "failure_surface" / CONFIG_NAME
    ap.add_argument("--summary", type=Path, default=default / "failure_surface_summary.parquet")
    ap.add_argument(
        "--weights",
        type=Path,
        default=_REPO / "D1_decision_scaling" / "lib" / "scenario_extraction" / "cmip6_cell_weights_montague.csv",
    )
    ap.add_argument("--outdir", type=Path, default=default / "analysis" / "rq3")
    ap.add_argument("--lb-level", default="LB1")
    args = ap.parse_args()

    summary = pd.read_parquet(args.summary)
    if args.lb_level:
        summary = summary[summary["lb_level_id"] == args.lb_level]

    weights = pd.read_csv(args.weights)
    bin_w = (
        weights.groupby("streamflow_bin_id")["bin_weight"]
        .first()
        .to_dict()
    )

    args.outdir.mkdir(parents=True, exist_ok=True)
    rows = []

    for slr in [s["id"] for s in SLR_LEVELS]:
        slr_cells = summary[summary["slr_id"] == slr]
        weighted_fail = 0.0
        total_w = 0.0
        for bin_id, w in bin_w.items():
            cell = slr_cells[slr_cells["flow_bin_id"] == bin_id]
            if cell.empty:
                continue
            p_fail = float(cell.iloc[0]["failure_fraction"])
            weighted_fail += w * p_fail
            total_w += w

        # Bins with zero CMIP6 weight still contribute to structural dry-tail analysis
        unweighted_mean = slr_cells["failure_fraction"].mean() if len(slr_cells) else 0.0

        rows.append({
            "slr_id": slr,
            "gcm_weighted_failure_fraction": weighted_fail,
            "gcm_weight_coverage": total_w,
            "unweighted_mean_failure_fraction": unweighted_mean,
            "majority_gcm_plausible": weighted_fail >= 0.5,
        })

    out = pd.DataFrame(rows)
    out.to_csv(args.outdir / "gcm_weighted_failure_by_slr.csv", index=False)

    tipping = out[out["majority_gcm_plausible"]]
    if not tipping.empty:
        tip_slr = tipping.iloc[0]["slr_id"]
        print(f"First SLR where GCM-weighted failure ≥ 50%: {tip_slr}")
    else:
        print("No SLR level reaches 50% GCM-weighted failure fraction.")

    print(out.to_string(index=False))
    print(f"\nWrote → {args.outdir}")


if __name__ == "__main__":
    main()

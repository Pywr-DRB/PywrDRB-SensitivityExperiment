#!/usr/bin/env python3
"""
Verify D1 fast-path prerequisites before submitting failure-surface sweep.

Exit 0 if ready; exit 1 with message otherwise.

Usage
-----
    python check_d1_ready.py
    python check_d1_ready.py --realizations 10
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config import REALIZATIONS_PER_CELL, STREAMFLOW_BINS

FLOWS_DIR = Path(__file__).parent.parent / "generator" / "synthetic_flows"
CACHE_DIR = FLOWS_DIR / "predicted_inflows_cache"
ML_DIR = Path(__file__).parent.parent / "stochastic_experiment" / "PywrDRB-ML"


def _inflow_type(bin_id: str, r: int) -> str:
    return f"d1_{bin_id}_r{r:03d}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--realizations", type=int, default=REALIZATIONS_PER_CELL)
    args = ap.parse_args()

    errors: list[str] = []

    if not (ML_DIR / "models" / "SalinityLSTM" / "SalinityLSTM.yml").exists():
        errors.append(f"PywrDRB-ML missing: {ML_DIR}")

    missing_flows = []
    for b in STREAMFLOW_BINS:
        bid = b["id"]
        for r in range(args.realizations):
            p = FLOWS_DIR / bid / f"realization_{r:03d}.parquet"
            if not p.exists():
                missing_flows.append(str(p))
    if missing_flows:
        errors.append(
            f"Synthetic flows missing: {len(missing_flows)} files "
            f"(e.g. {missing_flows[0]})"
        )

    missing_cache = []
    for b in STREAMFLOW_BINS:
        bid = b["id"]
        for r in range(args.realizations):
            c = CACHE_DIR / _inflow_type(bid, r) / "predicted_inflows_mgd.csv"
            if not c.exists():
                missing_cache.append(c)
    n_expected = len(STREAMFLOW_BINS) * args.realizations
    n_cached = n_expected - len(missing_cache)

    if missing_cache:
        errors.append(
            f"predicted_inflows cache: {n_cached}/{n_expected} ready under {CACHE_DIR}\n"
            f"  Run: sbatch D1_decision_scaling/slurm/submit_prewarm_d1.sh"
        )
    else:
        sample = CACHE_DIR / _inflow_type(STREAMFLOW_BINS[0]["id"], 0) / "predicted_inflows_mgd.csv"
        header = sample.read_text().splitlines()[0] if sample.exists() else ""
        if "regression_disagg" not in header:
            errors.append(
                "Cache has gage_flow-only columns; pilot needs regression_disagg. "
                "Remove predicted_inflows_cache/ and rerun prewarm."
            )

    if errors:
        print("D1 fast path NOT ready:\n", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(
        f"D1 fast path ready: {n_expected} flow parquets, "
        f"{n_expected} predicted_inflows caches, PywrDRB-ML OK"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

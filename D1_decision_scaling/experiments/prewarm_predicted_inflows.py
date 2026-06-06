"""
D1 — Pre-warm predicted_inflows_mgd.csv for all streamflow bins × realizations.

First Pywr-DRB run per (bin, realization) spends ~15–25 min generating this file.
Cache is shared across all SLR/LB cells that use the same synthetic flow.

Usage
-----
    python prewarm_predicted_inflows.py
    python prewarm_predicted_inflows.py --bin-id Q04 --workers 4
    sbatch ../slurm/submit_prewarm_d1.sh
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared"))
sys.path.insert(0, str(Path(__file__).parent))

from config import REALIZATIONS_PER_CELL, STREAMFLOW_BINS, SIM_END, SIM_START
from pywrdrb_utils.run_model import run_single

FLOWS_DIR = Path(__file__).parent.parent / "generator" / "synthetic_flows"
CACHE_DIR = FLOWS_DIR / "predicted_inflows_cache"


def _inflow_type(bin_id: str, r: int) -> str:
    return f"d1_{bin_id}_r{r:03d}"


def prewarm_one(bin_id: str, r: int) -> str:
    cache_path = CACHE_DIR / _inflow_type(bin_id, r) / "predicted_inflows_mgd.csv"
    if cache_path.exists():
        return f"{bin_id} r{r:03d}: cached"

    parquet = FLOWS_DIR / bin_id / f"realization_{r:03d}.parquet"
    if not parquet.exists():
        return f"{bin_id} r{r:03d}: MISSING {parquet}"

    flow_df = pd.read_parquet(parquet)
    flow_df.index.name = "datetime"
    try:
        run_single(
            flow_df=flow_df,
            inflow_type=_inflow_type(bin_id, r),
            tfo_override=None,
            lb_cap_multiplier=1.0,
            enable_salinity=False,
            predicted_inflows_cache=CACHE_DIR,
            flow_prediction_mode="regression_disagg",
            cleanup=True,
        )
    except Exception:
        pass

    if cache_path.exists():
        return f"{bin_id} r{r:03d}: OK"
    return f"{bin_id} r{r:03d}: FAILED (no cache written)"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin-id", default=None)
    ap.add_argument("--realizations", type=int, default=REALIZATIONS_PER_CELL)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    logger = logging.getLogger(__name__)

    bins = STREAMFLOW_BINS
    if args.bin_id:
        bins = [b for b in bins if b["id"] == args.bin_id]

    tasks = [(b["id"], r) for b in bins for r in range(args.realizations)]
    logger.info("Pre-warming %d (bin, realization) pairs, %d workers", len(tasks), args.workers)
    logger.info("Cache: %s", CACHE_DIR)

    ok = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(prewarm_one, bid, r): (bid, r) for bid, r in tasks}
        for fut in as_completed(futs):
            msg = fut.result()
            logger.info(msg)
            if msg.endswith("OK") or msg.endswith("cached"):
                ok += 1

    logger.info("Done: %d / %d cached", ok, len(tasks))


if __name__ == "__main__":
    main()

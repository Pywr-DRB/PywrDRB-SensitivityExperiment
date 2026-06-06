"""
Re-aggregate D4 baseline RRV metrics from existing per-member HDF5 output files.

Reads pywrdrb output HDF5 files written by run_d4_baseline.py and recomputes
RRV metrics with the current metrics.py, then overwrites rrv_summary.parquet.
Use this when metrics.py changes (e.g. a bug fix) without needing to re-run the model.

Usage
-----
    python rrv_metrics/reaggregate_baseline.py \
        --results-dir D4_distributed_risk/results/baseline \
        --n-workers 8
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd

_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_SHARED    = _REPO_ROOT / "shared"
for _p in [str(_SHARED), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pywrdrb_utils.run_model import _read_hdf5_outputs
from D4_distributed_risk.lib.rrv_metrics.metrics import compute_all_party_rrv
from D4_distributed_risk.experiments.run_d4_baseline import LB_CAPACITY_MG

logger = logging.getLogger(__name__)


def _process_one(member_dir: Path, member_id: int) -> dict:
    """Read one member's HDF5 output and compute RRV metrics."""
    hdf5_files = list(member_dir.glob("*.hdf5"))
    if not hdf5_files:
        return {"realization_id": member_id, "mode": "rerun", "status": "missing"}

    hdf5_path = hdf5_files[0]
    try:
        outputs = _read_hdf5_outputs(hdf5_path)
        rrv = compute_all_party_rrv(outputs, lb_capacity_mg=LB_CAPACITY_MG)
        row = {"realization_id": member_id, "mode": "rerun", "status": "ok"}
        row.update(rrv)
        return row
    except Exception as exc:
        logger.error(f"Member {member_id} failed: {exc}")
        return {"realization_id": member_id, "mode": "rerun", "status": f"error: {exc}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=_THIS_FILE.parents[1] / "results" / "baseline",
    )
    parser.add_argument("--n-members", type=int, default=1000)
    parser.add_argument("--n-workers", type=int, default=1)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    member_dirs = [
        (args.results_dir / f"member_{mid:04d}", mid)
        for mid in range(args.n_members)
        if (args.results_dir / f"member_{mid:04d}").exists()
    ]
    logger.info(f"Found {len(member_dirs)} member directories in {args.results_dir}")

    rows = []
    if args.n_workers <= 1:
        for i, (mdir, mid) in enumerate(member_dirs):
            row = _process_one(mdir, mid)
            rows.append(row)
            if (i + 1) % 100 == 0:
                n_ok = sum(1 for r in rows if r.get("status") == "ok")
                logger.info(f"  {i+1}/{len(member_dirs)} done (ok={n_ok})")
    else:
        with ProcessPoolExecutor(max_workers=args.n_workers) as pool:
            futures = {
                pool.submit(_process_one, mdir, mid): mid
                for mdir, mid in member_dirs
            }
            n_done = 0
            for fut in as_completed(futures):
                rows.append(fut.result())
                n_done += 1
                if n_done % 100 == 0:
                    n_ok = sum(1 for r in rows if r.get("status") == "ok")
                    logger.info(f"  {n_done}/{len(member_dirs)} done (ok={n_ok})")

    df = pd.DataFrame(rows).sort_values("realization_id").reset_index(drop=True)
    n_ok  = (df["status"] == "ok").sum()
    n_miss = (df["status"] == "missing").sum()
    n_err  = df["status"].str.startswith("error").sum()
    logger.info(f"Done: {n_ok} ok, {n_miss} missing, {n_err} errors")
    logger.info(df[[c for c in df.columns if c not in ("realization_id","mode","status","overall_regime")]].describe().round(3).to_string())

    out_parquet = args.results_dir / "rrv_summary.parquet"
    out_csv     = args.results_dir / "rrv_summary.csv"
    df.to_parquet(out_parquet, index=False)
    df.to_csv(out_csv, index=False)
    logger.info(f"Wrote {out_parquet}")
    logger.info(f"Wrote {out_csv}")


if __name__ == "__main__":
    main()

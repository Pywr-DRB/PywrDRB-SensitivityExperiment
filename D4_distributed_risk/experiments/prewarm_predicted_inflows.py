"""
D4 — Pre-warm predicted_inflows cache for all Kirsch-Nowak synthetic realizations.

PredictedInflowPreprocessor takes ~20 min per realization on first run.
This script pre-generates the cache for all 50 realizations so that each
Sobol SLURM task starts immediately without waiting for cache generation.

Run once before submitting the Sobol array:
    python sensitivity/prewarm_predicted_inflows.py

Or via SLURM (recommended):
    sbatch slurm/submit_prewarm.sh

Output
------
    results/sobol/synthetic_flows/predicted_inflows_cache/
      syn_r000/predicted_inflows_mgd.csv
      syn_r001/predicted_inflows_mgd.csv
      ...
      syn_r049/predicted_inflows_mgd.csv
"""

from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SHARED = _REPO_ROOT / "shared"
for _p in [str(_SHARED), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pywrdrb_utils.run_model import run_single

logger = logging.getLogger(__name__)


def prewarm_one(r: int, syn_flows_dir: Path) -> str:
    """Generate predicted_inflows cache for one realization."""
    import pandas as pd
    cache_path = syn_flows_dir / "predicted_inflows_cache" / f"syn_r{r:03d}" / "predicted_inflows_mgd.csv"
    if cache_path.exists():
        return f"r{r:03d}: already cached"

    parquet = syn_flows_dir / f"realization_{r:03d}.parquet"
    flow_df = pd.read_parquet(parquet)
    flow_df.index.name = "datetime"

    inflow_type = f"syn_r{r:03d}"
    predicted_inflows_cache = syn_flows_dir / "predicted_inflows_cache"

    # Run with baseline params — model will crash after predicted_inflows generation
    # because this is a single realization run with no sensitivity params.
    # We only need to trigger the cache write, so we catch and ignore downstream errors.
    try:
        run_single(
            flow_df=flow_df,
            inflow_type=inflow_type,
            tfo_override=None,
            lb_cap_multiplier=1.0,
            sensitivity_params=None,
            predicted_inflows_cache=predicted_inflows_cache,
            cleanup=True,
        )
    except Exception as exc:
        # Cache is written before model run — even if model fails, cache exists.
        pass

    if cache_path.exists():
        return f"r{r:03d}: OK"
    else:
        return f"r{r:03d}: MISSING after run (unexpected)"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--syn-flows-dir",
        type=Path,
        default=_THIS.parents[1] / "results" / "sobol" / "synthetic_flows",
    )
    parser.add_argument("--n-realizations", type=int, default=50)
    parser.add_argument("--n-workers", type=int, default=1)
    parser.add_argument("--realization-id", type=int, default=None,
                        help="Run only one realization (for SLURM array use)")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.realization_id is not None:
        result = prewarm_one(args.realization_id, args.syn_flows_dir)
        logger.info(result)
        return

    r_ids = list(range(args.n_realizations))
    logger.info(f"Pre-warming predicted_inflows for {len(r_ids)} realizations, {args.n_workers} workers")

    if args.n_workers <= 1:
        for r in r_ids:
            result = prewarm_one(r, args.syn_flows_dir)
            logger.info(result)
    else:
        with ProcessPoolExecutor(max_workers=args.n_workers) as pool:
            futures = {pool.submit(prewarm_one, r, args.syn_flows_dir): r for r in r_ids}
            for fut in as_completed(futures):
                logger.info(fut.result())

    n_cached = sum(
        1 for r in r_ids
        if (args.syn_flows_dir / "predicted_inflows_cache" / f"syn_r{r:03d}" / "predicted_inflows_mgd.csv").exists()
    )
    logger.info(f"Done: {n_cached}/{len(r_ids)} predicted_inflows cached")


if __name__ == "__main__":
    main()

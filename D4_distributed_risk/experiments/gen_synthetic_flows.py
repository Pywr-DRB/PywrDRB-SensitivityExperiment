"""
D4 — Generate Kirsch-Nowak synthetic DRB flow realizations for Sobol sweep.

Thin wrapper around shared/pywrdrb_utils/kirsch_flows.py.

Sweep 1/2 (legacy): all 50 realizations at pct_change=0.0 (historical baseline).

Sweep 3 (default): 50 realizations distributed across 5 hydroclimatic levels
to create a structured SOW set that spans observed-range DRB variability:

    Level  pct_change   Realizations  Description
    ─────  ──────────   ────────────  ─────────────────────────────────────
      0      -0.20          10        Dry   — 20% reduction in mean annual flow
      1      -0.10          10        Moderately dry
      2       0.00          10        Historical baseline (stationary)
      3      +0.10          10        Moderately wet
      4      +0.20          10        Wet   — 20% increase in mean annual flow

Rationale: The ±20% range brackets observed DRB hydroclimatic variability
over the instrumental record.  Averaging Sobol indices over this distribution
rather than a single pct_change=0.0 set makes the sensitivity estimates
robust to hydroclimatic state, directly addressing the SOW-consistency concern
raised in committee review (Pat Reed, 2026-06-04).

The generation_log.csv records pct_change per realization so the stratum
can be recovered for post-hoc regime-stratified sensitivity analysis.

Usage
-----
    # Sweep 3 (stratified, default)
    python sensitivity/gen_synthetic_flows.py --outdir results/sobol_sweep3/synthetic_flows

    # Legacy uniform (sweep 1/2)
    python sensitivity/gen_synthetic_flows.py --uniform --outdir results/sobol/synthetic_flows

    # Custom levels
    python sensitivity/gen_synthetic_flows.py \\
        --pct-changes -0.20 -0.10 0.0 0.10 0.20 \\
        --per-level 10
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SHARED = _REPO_ROOT / "shared"
for _p in [str(_SHARED), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pywrdrb_utils.kirsch_flows import (
    SIM_YEARS,
    SYN_N_DAYS,
    calibrate,
    generate_realization,
    get_historical_inflows,
    load_fitted_models,
)

_LIB_SENS = _THIS.parent.parent / "lib" / "sensitivity"
if str(_LIB_SENS) not in sys.path:
    sys.path.insert(0, str(_LIB_SENS))
from config import SOBOL_ENSEMBLE_SUBSET

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default SOW stratification — sweep 3
# ---------------------------------------------------------------------------
DEFAULT_PCT_CHANGES: list[float] = [-0.20, -0.10, 0.0, 0.10, 0.20]
DEFAULT_PER_LEVEL:   int         = 10   # realizations per pct_change level


def generate_stratified_realizations(
    kirsch_gen,
    nowak_disagg,
    Q_hist: pd.DataFrame,
    pct_changes: list[float],
    per_level: int,
    outdir: Path,
    master_seed: int = 42,
    skip_existing: bool = True,
) -> pd.DataFrame:
    """
    Generate realizations distributed across hydroclimatic levels.

    Realization numbering is contiguous across levels:
        r=0..9   → pct_change=-0.20
        r=10..19 → pct_change=-0.10
        r=20..29 → pct_change= 0.00
        r=30..39 → pct_change=+0.10
        r=40..49 → pct_change=+0.20

    Parameters
    ----------
    pct_changes : list[float]
        Fractional mean-flow shifts (e.g. [-0.20, -0.10, 0.0, 0.10, 0.20]).
    per_level : int
        Number of realizations per level.
    master_seed : int
        Base seed; per-realization seed = master_seed + r * 1000.

    Returns
    -------
    pd.DataFrame
        Generation log with columns: realization, pct_change, status, path.
    """
    outdir.mkdir(parents=True, exist_ok=True)
    log_rows = []
    r_global = 0

    for pct in pct_changes:
        for i in range(per_level):
            out_path = outdir / f"realization_{r_global:03d}.parquet"
            if skip_existing and out_path.exists():
                log_rows.append({
                    "realization": r_global,
                    "pct_change":  pct,
                    "status":      "skipped",
                    "path":        str(out_path),
                })
                r_global += 1
                continue

            seed = master_seed + r_global * 1000
            df = generate_realization(
                kirsch_gen, nowak_disagg, Q_hist,
                seed=seed,
                pct_change=pct,
            )
            df.to_parquet(out_path)
            log_rows.append({
                "realization": r_global,
                "pct_change":  pct,
                "status":      "ok",
                "path":        str(out_path),
            })
            logger.info(
                "  r=%03d  pct_change=%+.2f  seed=%d  → %s",
                r_global, pct, seed, out_path.name,
            )
            r_global += 1

    return pd.DataFrame(log_rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--outdir", type=Path,
        default=_THIS.parents[1] / "results" / "sobol_sweep3" / "synthetic_flows",
        help="Output directory for realization parquets and fitted model pkls.",
    )
    ap.add_argument(
        "--uniform", action="store_true",
        help="Legacy mode: all realizations at pct_change=0.0 (sweep 1/2 behaviour).",
    )
    ap.add_argument(
        "--pct-changes", type=float, nargs="+",
        default=DEFAULT_PCT_CHANGES,
        help=f"Hydroclimatic levels to generate (default: {DEFAULT_PCT_CHANGES}).",
    )
    ap.add_argument(
        "--per-level", type=int, default=DEFAULT_PER_LEVEL,
        help=f"Realizations per pct_change level (default: {DEFAULT_PER_LEVEL}).",
    )
    ap.add_argument("--seed",   type=int, default=42)
    ap.add_argument("--refit",  action="store_true",
                    help="Force re-calibration of Kirsch-Nowak models.")
    ap.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    args.outdir.mkdir(parents=True, exist_ok=True)

    # --- Load or fit models (reuse sweep 1 pkl if available) ---
    # Check sweep 1 first so we don't re-fit unnecessarily
    sweep1_flows = _THIS.parents[1] / "results" / "sobol" / "synthetic_flows"
    kirsch_path = args.outdir / "kirsch_fitted.pkl"
    nowak_path  = args.outdir / "nowak_fitted.pkl"

    if not kirsch_path.exists() and (sweep1_flows / "kirsch_fitted.pkl").exists() and not args.refit:
        import shutil
        logger.info("Copying fitted models from sweep 1 ...")
        shutil.copy(sweep1_flows / "kirsch_fitted.pkl", kirsch_path)
        shutil.copy(sweep1_flows / "nowak_fitted.pkl",  nowak_path)

    logger.info("Loading historical catchment inflows ...")
    Q_hist = get_historical_inflows()
    logger.info("  %s – %s, %d nodes",
                Q_hist.index[0].date(), Q_hist.index[-1].date(), Q_hist.shape[1])

    if kirsch_path.exists() and nowak_path.exists() and not args.refit:
        logger.info("Loading fitted models from pkl ...")
        from pywrdrb_utils.kirsch_flows import load_fitted_models
        kirsch_gen, nowak_disagg = load_fitted_models(args.outdir)
    else:
        logger.info("Fitting Kirsch-Nowak ...")
        kirsch_gen, nowak_disagg = calibrate(Q_hist, args.outdir)

    # --- Generate realizations ---
    if args.uniform:
        # Legacy sweep 1/2 behaviour
        from pywrdrb_utils.kirsch_flows import generate_realizations_to_dir
        n = SOBOL_ENSEMBLE_SUBSET
        logger.info("Generating %d uniform realizations (pct_change=0.0) ...", n)
        log_df = generate_realizations_to_dir(
            kirsch_gen, nowak_disagg, Q_hist,
            n_realizations=n,
            outdir=args.outdir,
            master_seed=args.seed,
            pct_change=0.0,
        )
    else:
        n_total = len(args.pct_changes) * args.per_level
        logger.info(
            "Generating %d stratified realizations: %d levels × %d per level",
            n_total, len(args.pct_changes), args.per_level,
        )
        logger.info("  Levels: %s", args.pct_changes)
        log_df = generate_stratified_realizations(
            kirsch_gen, nowak_disagg, Q_hist,
            pct_changes=args.pct_changes,
            per_level=args.per_level,
            outdir=args.outdir,
            master_seed=args.seed,
        )

    log_path = args.outdir / "generation_log.csv"
    log_df.to_csv(log_path, index=False)
    logger.info("Generation log: %s", log_path)

    # Summary
    if "pct_change" in log_df.columns:
        summary = log_df.groupby("pct_change")["status"].value_counts().unstack(fill_value=0)
        logger.info("Realization summary by level:\n%s", summary.to_string())

    logger.info("Done.")
    logger.info("Next: re-run prewarm then submit sweep 3")
    logger.info("  sbatch D4_distributed_risk/slurm/submit_prewarm.sh")
    logger.info("  SOBOL_SCRIPT=D4_distributed_risk/slurm/submit_sobol_sweep3.sh "
                "bash D4_distributed_risk/slurm/batch_submit_sobol.sh")


if __name__ == "__main__":
    main()

"""
D1 — Generate synthetic DRB flows for each streamflow bin (Axis 1).

For each percentile bin in experiments/config.py:
  - Apply pct_change mean-shift to Kirsch generator
  - Write REALIZATIONS_PER_CELL parquets to generator/synthetic_flows/{bin_id}/

Prerequisite: fitted Kirsch/Nowak pkls (from D4 or local calibrate).

Usage
-----
    python kirsch_generate.py
    python kirsch_generate.py --bin-id Q04
    python kirsch_generate.py --realizations 1   # smoke
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_SHARED = _REPO / "shared"
for _p in [str(_SHARED), str(_REPO)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pywrdrb_utils.kirsch_flows import (
    calibrate,
    generate_realizations_to_dir,
    get_historical_inflows,
    load_fitted_models,
)

_D1 = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_D1 / "experiments"))
from config import REALIZATIONS_PER_CELL, STREAMFLOW_BINS

logger = logging.getLogger(__name__)

_GEN_DATA = _D1 / "generator"
FITTED_DIRS = [
    _REPO / "D4_distributed_risk" / "results" / "sobol" / "synthetic_flows",
    _GEN_DATA / "fitted_model",
]
DEFAULT_OUTDIR = _GEN_DATA / "synthetic_flows"


def _resolve_fitted_dir() -> Path:
    for d in FITTED_DIRS:
        if (d / "kirsch_fitted.pkl").exists() and (d / "nowak_fitted.pkl").exists():
            return d
    return FITTED_DIRS[-1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bin-id", default=None, help="Single bin (e.g. Q04)")
    ap.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    ap.add_argument("--realizations", type=int, default=REALIZATIONS_PER_CELL)
    ap.add_argument("--seed-offset", type=int, default=0)
    ap.add_argument("--refit", action="store_true")
    ap.add_argument("--log-level", default="INFO")
    args = ap.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level))

    Q_hist = get_historical_inflows()
    fitted_dir = _resolve_fitted_dir()

    if args.refit or not (fitted_dir / "kirsch_fitted.pkl").exists():
        logger.info("Calibrating to %s", fitted_dir)
        kirsch_gen, nowak_disagg = calibrate(Q_hist, fitted_dir)
    else:
        logger.info("Loading fitted models from %s", fitted_dir)
        kirsch_gen, nowak_disagg = load_fitted_models(fitted_dir)

    if args.bin_id:
        bins = [b for b in STREAMFLOW_BINS if b["id"] == args.bin_id]
        if not bins:
            raise ValueError(f"Unknown bin {args.bin_id}")
    else:
        bins = STREAMFLOW_BINS

    for bin_config in bins:
        bin_id = bin_config["id"]
        pct = bin_config["pct_change"]
        bindir = args.outdir / bin_id
        logger.info(
            "Bin %s (pct_change=%+.0f%%), %d realizations → %s",
            bin_id, pct * 100, args.realizations, bindir,
        )
        log_df = generate_realizations_to_dir(
            kirsch_gen, nowak_disagg, Q_hist,
            n_realizations=args.realizations,
            outdir=bindir,
            master_seed=hash(bin_id) % (2**31) + args.seed_offset,
            pct_change=pct,
        )
        log_df.to_csv(bindir / "generation_log.csv", index=False)

    logger.info("Generation complete. Next: run_failure_surface_sweep.py")


if __name__ == "__main__":
    main()

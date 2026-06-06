"""
D4 Distributed Risk Characterization (DRC) — Baseline ensemble run.

Two modes
---------
prerun : Load Amestoy et al. (2025) pre-run HDF5 directly via pywrdrb.Data.load_from_export().
         Fast pipeline validation (~minutes).
         CAVEAT: pre-run data uses pywrdrb April 2025 — no LB drought switching,
         no NJ coupling. Results labelled 'pipeline_validation', NOT used for publication.

rerun  : Re-run all N ensemble members with the updated pywrdrb (current dissertation
         venv). Publication-quality results. Requires pywrdrb inputs HDF5.
         Parallelised across --n-workers cores via multiprocessing.

Usage
-----
  # Pipeline validation (no SLURM needed):
  python run_d4_baseline.py --mode prerun \\
      --ensemble-path ~/data/amestoy_2026

  # Production run (submitted via submit_baseline.sh):
  python run_d4_baseline.py --mode rerun \\
      --ensemble-path ~/data/amestoy_2026 \\
      --outdir D4_distributed_risk/results/baseline \\
      --n-workers 100

  # Quick smoke test (3 members, rerun):
  python run_d4_baseline.py --mode rerun --n-members 3 \\
      --ensemble-path ~/data/amestoy_2026 \\
      --outdir /tmp/d4_smoke

Outputs
-------
  {outdir}/rrv_summary.parquet          — one row per member, all party RRV metrics
  {outdir}/rrv_summary.csv              — same, CSV copy
  {outdir}/regime_attribution.parquet   — regime label per member
  {outdir}/run_metadata.json            — mode, timestamp, git hash, pywrdrb version

References
----------
Amestoy, T.J. et al. (2025). Zenodo. DOI 10.5281/zenodo.15101164
Hashimoto, T., Stedinger, J.R., Loucks, D.P. (1982). WRR 18(1):14–20.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup — allow running from repo root or the file's own directory
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]          # dissertation/
_SHARED    = _REPO_ROOT / "shared"
for _p in [str(_SHARED), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from pywrdrb_utils.attribution import attribute_daily, regime_summary
from D4_distributed_risk.lib.rrv_metrics.metrics import compute_all_party_rrv

# ---------------------------------------------------------------------------
# Amestoy ensemble constants
# ---------------------------------------------------------------------------

# Path layout after unzipping pywrdrb_data.zip
PRERUN_HDF5_SUBPATH = (
    "pywrdrb_outputs"
    "/pywrdrb_results_export_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5"
)
INPUTS_HDF5_SUBPATH = (
    "pywrdrb_inputs/historic_ensembles"
    "/catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5"
)

N_ENSEMBLE_MEMBERS = 1_000

# results_sets to request from the pre-run export
PRERUN_RESULTS_SETS = [
    "major_flow",
    "res_storage",
    "ibt_diversions",
    "lower_basin_mrf_contributions",
    "res_level",
    "mrf_targets",      # dynamic Trenton/Montague targets per day
]

# Mapping from pywrdrb column names → run_model.py OUTPUT_VARS keys
# (for assembling the outputs dict that compute_all_party_rrv expects)
_MAJOR_FLOW_COLS = {
    "delTrenton":  "del_trenton_flow",
    "delMontague": "del_montague_flow",
}
_STORAGE_COLS = {
    "blueMarsh":          "blueMarsh_volume",
    "beltzvilleCombined": "beltzville_volume",
}
_DIVERSION_COLS = {
    "delivery_nj": "nj_delivery",
}
_LEVEL_COLS = {
    "lb":  "lb_drought_stage",
    "nyc": "nyc_drought_stage",
}

# LB combined capacity (blueMarsh + beltzvilleCombined usable storage in MG)
LB_CAPACITY_MG = 20_950.0

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pre-run mode: load from Amestoy HDF5 export
# ---------------------------------------------------------------------------

def _load_prerun_data(ensemble_path: Path, n_members: Optional[int] = None):
    """
    Load pre-run Amestoy data using pywrdrb.Data.load_from_export().

    Returns
    -------
    data : pywrdrb.Data
        Loaded data object. Attribute access: data.{results_set}[datatype][scenario_id]
    realizations : list[int]
        Sorted list of available realization IDs.
    datatype : str
        The inflow type label (e.g. 'obs_pub_nhmv10_BC_ObsScaled_ensemble').
    """
    import pywrdrb

    hdf5_path = ensemble_path / PRERUN_HDF5_SUBPATH
    if not hdf5_path.exists():
        raise FileNotFoundError(
            f"Pre-run HDF5 not found: {hdf5_path}\n"
            f"Did you unzip pywrdrb_data.zip into {ensemble_path}?"
        )

    logger.info(f"Loading pre-run HDF5: {hdf5_path}")

    realizations_filter = list(range(n_members)) if n_members else None

    data = pywrdrb.Data()
    data.load_from_export(
        str(hdf5_path),
        results_sets=PRERUN_RESULTS_SETS,
        realizations=realizations_filter,
    )

    # Discover which datatype and realizations were loaded (use major_flow as probe)
    if not hasattr(data, "major_flow") or not data.major_flow:
        raise RuntimeError(
            "No major_flow data loaded. Check HDF5 file structure and results_sets."
        )

    # data.major_flow = {datatype: {scenario_id: df}}
    # The Amestoy pre-run export contains both 'obs' (observational) and the
    # simulation output datatype. We want the simulation output datatype,
    # which has the most realizations (1000 members vs 1 for 'obs').
    all_datatypes = list(data.major_flow.keys())
    if len(all_datatypes) == 1:
        datatype = all_datatypes[0]
    else:
        # Pick the datatype with the most realizations (= simulation output)
        datatype = max(all_datatypes, key=lambda dt: len(data.major_flow[dt]))
        obs_dtype = [dt for dt in all_datatypes if dt == "obs"]
        if obs_dtype:
            sim_dtypes = [dt for dt in all_datatypes if dt != "obs"]
            if sim_dtypes:
                datatype = sim_dtypes[0]
        if len(all_datatypes) > 1:
            logger.info(
                f"Multiple datatypes in HDF5: {all_datatypes}. "
                f"Using simulation output: '{datatype}'"
            )

    realizations = sorted(data.major_flow[datatype].keys())
    logger.info(f"Loaded {len(realizations)} realizations  (datatype='{datatype}')")

    return data, realizations, datatype


def _extract_member_outputs_prerun(
    data,
    datatype: str,
    realization_id: int,
) -> dict[str, pd.Series]:
    """
    Extract output dict for one realization from pre-run pywrdrb.Data object.

    Returns a dict matching the OUTPUT_VARS schema expected by compute_all_party_rrv().
    Missing variables (e.g. IERQ — not in old pywrdrb) are omitted; metrics.py
    handles missing keys gracefully via pd.Series(dtype=float) fallback.
    """
    outputs: dict[str, pd.Series] = {}

    def _get_col(attr_name: str, col: str) -> Optional[pd.Series]:
        """Safely pull one column from data.{attr_name}[datatype][realization_id]."""
        try:
            result_set = getattr(data, attr_name, None)
            if result_set is None:
                return None
            df = result_set.get(datatype, {}).get(realization_id)
            if df is None or col not in df.columns:
                return None
            return df[col]
        except Exception:
            return None

    # major_flow
    for src_col, dst_key in _MAJOR_FLOW_COLS.items():
        series = _get_col("major_flow", src_col)
        if series is not None:
            outputs[dst_key] = series

    # res_storage
    for src_col, dst_key in _STORAGE_COLS.items():
        series = _get_col("res_storage", src_col)
        if series is not None:
            outputs[dst_key] = series

    # ibt_diversions
    for src_col, dst_key in _DIVERSION_COLS.items():
        series = _get_col("ibt_diversions", src_col)
        if series is not None:
            outputs[dst_key] = series

    # res_level (drought stage) — col names are just "lb" and "nyc"
    for src_col, dst_key in _LEVEL_COLS.items():
        series = _get_col("res_level", src_col)
        if series is not None:
            outputs[dst_key] = series

    # NOTE: ierq_bank_remaining is NOT available in the Amestoy pre-run
    # (IERQRelease_step1 was added to pywrdrb after April 2025).
    # nyc_metrics() will return NaN placeholders for IERQ metrics.

    return outputs


def run_prerun_baseline(
    ensemble_path: Path,
    outdir: Path,
    n_members: Optional[int] = None,
) -> pd.DataFrame:
    """
    Run D4 baseline in prerun mode: load Amestoy HDF5, compute RRV metrics.

    Returns
    -------
    pd.DataFrame  — one row per member, all party RRV metrics + regime label
    """
    warnings.warn(
        "prerun mode uses Amestoy pre-run data (April 2025 pywrdrb — "
        "no LB drought switching, no NJ coupling). "
        "Results are labelled 'pipeline_validation' and NOT for publication.",
        UserWarning,
        stacklevel=2,
    )

    data, realizations, datatype = _load_prerun_data(ensemble_path, n_members)

    results = []
    for i, realization_id in enumerate(realizations):
        if i % 100 == 0:
            logger.info(f"  Processing realization {realization_id} ({i+1}/{len(realizations)})")

        outputs = _extract_member_outputs_prerun(data, datatype, realization_id)
        rrv = compute_all_party_rrv(outputs, lb_capacity_mg=LB_CAPACITY_MG)

        # Regime attribution (requires IERQ + LB storage — may be partial in prerun)
        ierq = outputs.get("ierq_bank_remaining")
        lb_storage = (
            outputs.get("blueMarsh_volume", pd.Series(0.0))
            + outputs.get("beltzville_volume", pd.Series(0.0))
        )
        if ierq is not None:
            reg = regime_summary(ierq, lb_storage)
        else:
            reg = {
                "overall_regime": "unknown_no_ierq_data",
                "regime_day_fractions": {},
                "t_ierq_exhaustion": None,
                "t_lb_depletion": None,
            }

        row = {"realization_id": realization_id, "mode": "pipeline_validation"}
        row.update(rrv)
        row["overall_regime"] = reg["overall_regime"]
        results.append(row)

    df = pd.DataFrame(results)
    _save_results(df, outdir, mode="prerun")
    return df


# ---------------------------------------------------------------------------
# Rerun mode: re-run model with updated pywrdrb
# ---------------------------------------------------------------------------


def _run_one_member(
    member_id: int,
    inputs_hdf5: Path,
    outdir: Path,
    n_members_total: int = N_ENSEMBLE_MEMBERS,
) -> dict:
    """
    Run one Amestoy ensemble member through updated pywrdrb and return RRV metrics.

    Parameters
    ----------
    member_id : int
        Realization index (0-based).
    inputs_hdf5 : Path
        Path to the Amestoy inputs HDF5 (catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5).
    outdir : Path
        Output directory for per-member raw outputs.

    Returns
    -------
    dict — metrics row including member_id and overall_regime.
    """
    from pywrdrb_utils.amestoy_io import load_member_flows
    from pywrdrb_utils.run_model import run_single

    # Load this member's inflow from the Amestoy inputs HDF5.
    # Structure: /{node_name}/{str(member_id)} → shape (28854,) [MGD]
    # Date range: 1945-01-01 – 2023-12-31 (confirmed 2026-05-31).
    try:
        flow_df = load_member_flows(inputs_hdf5, member_id)

        # Unique inflow_type per member to avoid path collision under parallel runs
        inflow_type = f"obs_pub_nhmv10_BC_ObsScaled_m{member_id:04d}"

        # run_single() — no TFO or LB cap override for baseline (use model defaults).
        # Cache predicted_inflows_mgd.csv alongside the inputs HDF5 (one per member).
        _cache_dir = inputs_hdf5.parent / "predicted_inflows_cache"
        outputs = run_single(
            flow_df=flow_df,
            inflow_type=inflow_type,
            tfo_override=None,
            lb_cap_multiplier=1.0,
            predicted_inflows_cache=_cache_dir,
            workdir=outdir / f"member_{member_id:04d}",
            cleanup=True,
        )

        # Compute RRV metrics
        rrv = compute_all_party_rrv(outputs, lb_capacity_mg=LB_CAPACITY_MG)

        # Regime attribution
        ierq = outputs.get("ierq_bank_remaining")
        lb_storage = (
            outputs.get("blueMarsh_volume", pd.Series(0.0))
            + outputs.get("beltzville_volume", pd.Series(0.0))
        )
        if ierq is not None:
            reg = regime_summary(ierq, lb_storage)
        else:
            reg = {"overall_regime": "unknown", "regime_day_fractions": {}}

        row = {"realization_id": member_id, "mode": "rerun", "status": "ok"}
        row.update(rrv)
        row["overall_regime"] = reg["overall_regime"]
        return row

    except Exception as exc:
        import traceback
        tb_str = traceback.format_exc()
        logger.error(f"Member {member_id} failed: {type(exc).__name__}: {exc}\n{tb_str}")
        return {
            "realization_id": member_id,
            "mode": "rerun",
            "status": f"error: {type(exc).__name__}: {exc}",
            "overall_regime": "error",
        }


def run_rerun_baseline(
    ensemble_path: Path,
    outdir: Path,
    n_workers: int = 1,
    n_members: Optional[int] = None,
) -> pd.DataFrame:
    """
    Run D4 baseline in rerun mode: re-run with updated pywrdrb, all ensemble members.

    Parallelised across n_workers processes.

    Returns
    -------
    pd.DataFrame — one row per member, all party RRV metrics + regime label
    """
    inputs_hdf5 = ensemble_path / INPUTS_HDF5_SUBPATH
    if not inputs_hdf5.exists():
        raise FileNotFoundError(
            f"Inputs HDF5 not found: {inputs_hdf5}\n"
            f"Did you unzip pywrdrb_data.zip into {ensemble_path}?"
        )

    n_total = n_members if n_members else N_ENSEMBLE_MEMBERS
    member_ids = list(range(n_total))

    logger.info(f"Rerun mode: {n_total} members × updated pywrdrb, {n_workers} workers")

    results = []
    if n_workers <= 1:
        # Serial — useful for debugging
        for mid in member_ids:
            row = _run_one_member(mid, inputs_hdf5, outdir, n_total)
            results.append(row)
            if mid % 50 == 0:
                logger.info(f"  Completed member {mid}/{n_total}")
    else:
        with ProcessPoolExecutor(max_workers=n_workers) as pool:
            futures = {
                pool.submit(_run_one_member, mid, inputs_hdf5, outdir, n_total): mid
                for mid in member_ids
            }
            n_done = 0
            for fut in as_completed(futures):
                row = fut.result()
                results.append(row)
                n_done += 1
                if n_done % 50 == 0:
                    logger.info(f"  Completed {n_done}/{n_total} members")

    df = pd.DataFrame(results)
    _save_results(df, outdir, mode="rerun")
    return df


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def _save_results(df: pd.DataFrame, outdir: Path, mode: str) -> None:
    """Write summary parquet, CSV, and regime attribution parquet to outdir."""
    outdir.mkdir(parents=True, exist_ok=True)

    parquet_path = outdir / "rrv_summary.parquet"
    csv_path     = outdir / "rrv_summary.csv"
    regime_path  = outdir / "regime_attribution.parquet"

    df.to_parquet(parquet_path, index=False)
    df.to_csv(csv_path, index=False)

    regime_cols = [c for c in df.columns if c in ("realization_id", "overall_regime",
                                                     "mode", "status")]
    df[regime_cols].to_parquet(regime_path, index=False)

    logger.info(f"Saved {len(df)} rows → {outdir}")
    logger.info(f"  rrv_summary.parquet  ({parquet_path.stat().st_size // 1024} kB)")
    logger.info(f"  rrv_summary.csv")
    logger.info(f"  regime_attribution.parquet")

    # Print regime distribution
    if "overall_regime" in df.columns:
        counts = df["overall_regime"].value_counts()
        logger.info("Regime distribution:")
        for regime, n in counts.items():
            logger.info(f"  {regime:20s}: {n:5d}  ({100*n/len(df):.1f}%)")


def _write_metadata(outdir: Path, mode: str, args: argparse.Namespace) -> None:
    """Write run_metadata.json with provenance info."""
    try:
        git_hash = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT), stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        git_hash = "unknown"

    try:
        import pywrdrb
        pywrdrb_version = getattr(pywrdrb, "__version__", "unknown")
    except Exception:
        pywrdrb_version = "unknown"

    meta = {
        "mode":            mode,
        "timestamp_utc":   datetime.utcnow().isoformat() + "Z",
        "git_hash":        git_hash,
        "pywrdrb_version": pywrdrb_version,
        "ensemble_path":   str(args.ensemble_path),
        "n_members":       args.n_members,
        "n_workers":       getattr(args, "n_workers", 1),
        "prerun_caveat":   (
            "Pre-run data uses pywrdrb April 2025 "
            "(no LB drought switching, no NJ coupling). "
            "Pipeline validation only."
            if mode == "prerun" else None
        ),
    }
    outdir.mkdir(parents=True, exist_ok=True)
    meta_path = outdir / "run_metadata.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    logger.info(f"Metadata: {meta_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="D4 Distributed Risk Characterization (DRC) — Baseline ensemble run.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["prerun", "rerun"],
        default="rerun",
        help=(
            "prerun: load Amestoy pre-run HDF5 (fast, pipeline validation). "
            "rerun: re-run with updated pywrdrb (publication quality)."
        ),
    )
    parser.add_argument(
        "--ensemble-path",
        type=Path,
        default=Path.home() / "data" / "amestoy_2026",
        help="Root directory of extracted pywrdrb_data.zip (default: ~/data/amestoy_2026)",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=_THIS_FILE.parent.parent / "results" / "baseline",
        help="Output directory for results (default: D4_distributed_risk/results/baseline/)",
    )
    parser.add_argument(
        "--n-workers",
        type=int,
        default=1,
        help="Number of parallel workers for rerun mode (default: 1; SLURM sets via $SLURM_CPUS_PER_TASK)",
    )
    parser.add_argument(
        "--n-members",
        type=int,
        default=None,
        help="Limit number of ensemble members (default: all 1000). Useful for smoke tests.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    logger.info("=" * 60)
    logger.info("D4 Distributed Risk Characterization (DRC) — Baseline Run")
    logger.info(f"  mode:          {args.mode}")
    logger.info(f"  ensemble_path: {args.ensemble_path}")
    logger.info(f"  outdir:        {args.outdir}")
    logger.info(f"  n_members:     {args.n_members or 'all (1000)'}")
    if args.mode == "rerun":
        logger.info(f"  n_workers:     {args.n_workers}")
    logger.info("=" * 60)

    _write_metadata(args.outdir, args.mode, args)

    if args.mode == "prerun":
        df = run_prerun_baseline(
            ensemble_path=args.ensemble_path,
            outdir=args.outdir,
            n_members=args.n_members,
        )
    else:
        df = run_rerun_baseline(
            ensemble_path=args.ensemble_path,
            outdir=args.outdir,
            n_workers=args.n_workers,
            n_members=args.n_members,
        )

    logger.info("Done.")
    logger.info(f"Results: {args.outdir}/rrv_summary.parquet")

    # Print quick summary stats
    numeric_cols = df.select_dtypes(include=np.number).columns
    if len(numeric_cols):
        logger.info("\nQuick summary (mean across members):")
        means = df[numeric_cols].mean()
        for col, val in means.items():
            if col != "realization_id":
                logger.info(f"  {col:35s}: {val:.4f}")


if __name__ == "__main__":
    main()

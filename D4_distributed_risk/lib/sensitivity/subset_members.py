"""
SUPERSEDED (2026-06-01): The Sobol sensitivity sweep now uses Kirsch-Nowak
synthetic realizations instead of a subset of the Amestoy ensemble.
See gen_synthetic_flows.py.  This file is retained for reference only.

D4 — Select 50-member representative subset for Sobol sensitivity sweep.

Selects SOBOL_ENSEMBLE_SUBSET (50) members from the 1000-member Amestoy ensemble
by matching the distribution moments of the full ensemble on key metrics.

Method: Steinschneider & Brown (2013) stratified selection — divide the full
ensemble CDF into SOBOL_ENSEMBLE_SUBSET quantile bins and select the member
closest to each bin's median.  Applied to DE reliability (Trenton flow) as the
primary stratification metric, with secondary metrics used to break ties.

Usage
-----
    # Run after the baseline ensemble run completes (rrv_summary.parquet required):
    python sensitivity/subset_members.py \\
        --baseline-parquet D4_distributed_risk/results/baseline/rrv_summary.parquet \\
        --outdir D4_distributed_risk/results/sobol \\
        --n-subset 50

Output
------
    {outdir}/subset_members.txt  — whitespace-separated list of member IDs
    {outdir}/subset_selection.csv — table: member_id, stratum, primary_metric, selection_reason

References
----------
Steinschneider, S. & Brown, C. (2013). A semiparametric multivariate,
  multisite weather generator with low-frequency variability for use in
  climate risk assessments. Water Resources Research, 49(11), 7205–7220.
  DOI 10.1002/wrcr.20528
Amestoy, T.J. et al. (2025). Zenodo. DOI 10.5281/zenodo.15101164
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_SHARED    = _REPO_ROOT / "shared"
for _p in [str(_SHARED), str(_REPO_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Stratification config
# ---------------------------------------------------------------------------

# Primary metric for CDF stratification — DE reliability is the D4 headline metric
# and captures integrated Trenton flow performance across the full ensemble.
PRIMARY_METRIC = "de_reliability"

# Secondary metrics used to rank within ties (or report for validation)
SECONDARY_METRICS = [
    "ny_reliability",
    "pa_depletion_days",
    "nyc_ierq_exhaustion_days",
    "nj_lb_restriction_days",
]


# ---------------------------------------------------------------------------
# Core selection function
# ---------------------------------------------------------------------------

def select_subset(
    rrv_df: pd.DataFrame,
    n_subset: int = 50,
    primary_metric: str = PRIMARY_METRIC,
    secondary_metrics: list = None,
    member_id_col: str = "realization_id",
    rng_seed: int = 42,
) -> pd.DataFrame:
    """
    Select n_subset representative members from a full ensemble RRV summary.

    Algorithm
    ---------
    1. Compute CDF of ``primary_metric`` across all members.
    2. Divide into ``n_subset`` quantile strata of equal probability mass.
    3. In each stratum, select the member whose primary_metric value is
       closest to the stratum median.
    4. In case of exact tie on primary_metric, break ties using the first
       available secondary metric.

    Parameters
    ----------
    rrv_df : pd.DataFrame
        Baseline RRV summary — one row per ensemble member.
        Must contain ``member_id_col`` and ``primary_metric``.
    n_subset : int
        Target subset size (default: 50).
    primary_metric : str
        Column to stratify on.
    secondary_metrics : list or None
        Tie-breaking columns.  Defaults to SECONDARY_METRICS.
    member_id_col : str
        Column that identifies the ensemble member (default: 'realization_id').
    rng_seed : int
        Random seed for any tie-breaking randomness.

    Returns
    -------
    pd.DataFrame
        Subset selection table with columns:
        member_id, stratum, primary_metric_value, distance_to_stratum_median,
        selection_reason
    """
    if secondary_metrics is None:
        secondary_metrics = SECONDARY_METRICS

    rng = np.random.default_rng(rng_seed)

    # --- Drop rows with missing primary metric ---
    valid = rrv_df.dropna(subset=[primary_metric]).copy()
    n_total = len(valid)
    if n_total < n_subset:
        raise ValueError(
            f"Ensemble has only {n_total} valid rows for '{primary_metric}'; "
            f"cannot select {n_subset}."
        )

    logger.info(
        f"Selecting {n_subset}/{n_total} members by stratified CDF "
        f"(primary: {primary_metric})"
    )

    # Sort by primary metric — assign stratum index
    valid = valid.sort_values(primary_metric).reset_index(drop=True)
    valid["_rank"] = np.arange(n_total)

    # Stratum boundaries: split [0, n_total) into n_subset equal bins
    stratum_edges = np.linspace(0, n_total, n_subset + 1)
    stratum_medians = 0.5 * (stratum_edges[:-1] + stratum_edges[1:])

    selected_rows = []
    for stratum_idx, median_rank in enumerate(stratum_medians):
        lo = int(stratum_edges[stratum_idx])
        hi = int(stratum_edges[stratum_idx + 1])

        stratum_df = valid.iloc[lo:hi].copy()
        stratum_df["_dist"] = np.abs(stratum_df["_rank"] - median_rank)

        # Find minimum distance
        min_dist = stratum_df["_dist"].min()
        candidates = stratum_df[stratum_df["_dist"] == min_dist]

        if len(candidates) == 1:
            chosen = candidates.iloc[0]
            reason = "closest_to_stratum_median"
        else:
            # Tie-break: use first available secondary metric
            reason = "tie_broken"
            chosen = None
            for sec_metric in secondary_metrics:
                if sec_metric in candidates.columns and not candidates[sec_metric].isna().all():
                    # Among ties, pick the one closest to the secondary metric mean
                    sec_mean = valid[sec_metric].mean()
                    sec_dist = np.abs(candidates[sec_metric] - sec_mean)
                    chosen = candidates.loc[sec_dist.idxmin()]
                    reason = f"tie_broken_by_{sec_metric}"
                    break
            if chosen is None:
                # Last resort: random
                chosen = candidates.sample(1, random_state=int(rng.integers(1e6))).iloc[0]
                reason = "tie_broken_random"

        selected_rows.append({
            "member_id":              int(chosen[member_id_col]),
            "stratum":                stratum_idx,
            "primary_metric_value":   float(chosen[primary_metric]),
            "distance_to_median":     float(chosen["_dist"]),
            "selection_reason":       reason,
        })

    selection_df = pd.DataFrame(selected_rows)

    # --- Validation: log how well the subset matches the full ensemble ---
    selected_ids  = selection_df["member_id"].tolist()
    subset_vals   = valid.loc[valid[member_id_col].isin(selected_ids), primary_metric]
    full_vals     = valid[primary_metric]

    logger.info(
        f"Full ensemble  — mean: {full_vals.mean():.4f}, "
        f"std: {full_vals.std():.4f}, "
        f"[{full_vals.min():.4f}, {full_vals.max():.4f}]"
    )
    logger.info(
        f"Subset {n_subset}      — mean: {subset_vals.mean():.4f}, "
        f"std: {subset_vals.std():.4f}, "
        f"[{subset_vals.min():.4f}, {subset_vals.max():.4f}]"
    )

    return selection_df


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--baseline-parquet",
        type=Path,
        default=_THIS_FILE.parents[1] / "results" / "baseline" / "rrv_summary.parquet",
        help=(
            "Path to baseline rrv_summary.parquet (from run_d4_baseline.py --mode rerun). "
            "Default: D4_distributed_risk/results/baseline/rrv_summary.parquet"
        ),
    )
    parser.add_argument(
        "--n-subset",
        type=int,
        default=50,
        help="Number of representative members to select (default: 50).",
    )
    parser.add_argument(
        "--primary-metric",
        default=PRIMARY_METRIC,
        help=f"Metric to stratify on (default: {PRIMARY_METRIC}).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=_THIS_FILE.parents[1] / "results" / "sobol",
        help="Output directory (default: D4_distributed_risk/results/sobol/).",
    )
    parser.add_argument(
        "--member-id-col",
        default="realization_id",
        help="Column name for member ID in the parquet (default: realization_id).",
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

    # --- Load baseline results ---
    if not args.baseline_parquet.exists():
        raise FileNotFoundError(
            f"Baseline parquet not found: {args.baseline_parquet}\n"
            f"Run first: python rrv_metrics/run_d4_baseline.py --mode rerun"
        )
    logger.info(f"Loading baseline results: {args.baseline_parquet}")
    rrv_df = pd.read_parquet(args.baseline_parquet)
    logger.info(f"  Loaded {len(rrv_df)} members, {len(rrv_df.columns)} columns")

    # --- Check required columns ---
    if args.primary_metric not in rrv_df.columns:
        available = [c for c in rrv_df.columns if c not in ("realization_id", "mode", "status")]
        raise ValueError(
            f"Primary metric '{args.primary_metric}' not in parquet columns.\n"
            f"Available numeric columns: {available}"
        )
    if args.member_id_col not in rrv_df.columns:
        raise ValueError(
            f"Member ID column '{args.member_id_col}' not in parquet. "
            f"Columns: {list(rrv_df.columns)}"
        )

    # Filter to successful runs only (skip 'pipeline_validation' prerun rows)
    if "mode" in rrv_df.columns:
        valid_modes = rrv_df["mode"].isin(["rerun"])
        if valid_modes.sum() == 0:
            logger.warning(
                "No 'rerun' mode rows found — falling back to all rows. "
                "For publication, use the rerun baseline."
            )
        else:
            rrv_df = rrv_df[valid_modes]
            logger.info(f"  Filtered to rerun mode: {len(rrv_df)} members")

    # --- Select subset ---
    selection_df = select_subset(
        rrv_df=rrv_df,
        n_subset=args.n_subset,
        primary_metric=args.primary_metric,
        member_id_col=args.member_id_col,
    )

    # --- Write outputs ---
    args.outdir.mkdir(parents=True, exist_ok=True)

    # subset_members.txt — whitespace-separated member IDs (one per line)
    members_txt = args.outdir / "subset_members.txt"
    members_list = sorted(selection_df["member_id"].tolist())
    members_txt.write_text("\n".join(str(m) for m in members_list) + "\n")
    logger.info(f"Wrote {len(members_list)} member IDs → {members_txt}")

    # subset_selection.csv — full selection table for documentation
    selection_csv = args.outdir / "subset_selection.csv"
    selection_df.to_csv(selection_csv, index=False)
    logger.info(f"Wrote selection table → {selection_csv}")

    # Print first few
    logger.info(f"\nSelected member IDs (first 10): {members_list[:10]}")
    logger.info(f"\nNext step: submit Sobol sweep")
    logger.info(
        f"  python sensitivity/sobol_design.py --outdir D4_distributed_risk/results/sobol"
    )
    logger.info(f"  sbatch slurm/submit_sobol.sh")


if __name__ == "__main__":
    main()

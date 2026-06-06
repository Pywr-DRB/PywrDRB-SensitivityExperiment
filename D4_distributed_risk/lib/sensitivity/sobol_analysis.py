"""
D4 Sobol Sensitivity Analysis — Saltelli index computation.

Reads the 14,336 per-sample task CSVs produced by run_sobol_sweep.py,
averages metrics over the 50 synthetic realizations per sample, and computes
first-order (S1), total-order (ST), and second-order (S2) Sobol indices for
each output metric using SALib.

Usage
-----
    cd ~/dissertation
    source venv/bin/activate
    python D4_distributed_risk/sensitivity/sobol_analysis.py \\
        --task-dir  D4_distributed_risk/results/sobol/task_outputs \\
        --design    D4_distributed_risk/results/sobol/sobol_design.json \\
        --outdir    D4_distributed_risk/results/sobol

Outputs
-------
    {outdir}/sobol_indices.parquet   — long-format: (metric, parameter) × (S1, ST, S1_conf, ST_conf)
    {outdir}/sobol_indices.csv       — same, CSV copy
    {outdir}/sobol_S2.parquet        — second-order indices: (metric, param_i, param_j) × (S2, S2_conf)
    {outdir}/sobol_mean_metrics.parquet — per-sample mean metric values (14336 × n_metrics)
    {outdir}/sobol_analysis_report.txt  — human-readable summary table

Design
------
Saltelli (2010) estimators:  N=1024 base samples, k=6 parameters.
Total samples = N × (2k+2) = 14,336.  Second-order indices are estimated.
SALib ≥ 1.5 required.

Reference
---------
Saltelli, A. et al. (2010). Variance based sensitivity analysis of model
  output. Computer Physics Communications, 181(2), 259–270.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Target metrics — subset with meaningful variance (see validate_sobol.py)
# nyc_min_ierq_balance_mg excluded: always 0 across all runs (zero variance)
# ---------------------------------------------------------------------------
TARGET_METRICS: list[str] = [
    "de_reliability",
    "de_resiliency",
    "de_vulnerability",
    "de_shortfall_days",
    "de_max_deficit_mgd",
    "nyc_ierq_exhaustion_days",
    "nyc_ierq_exhaustion_reliability",
    "pa_depletion_days",
    "pa_depletion_reliability",
    "pa_min_storage_frac",
    "pa_depletion_resiliency",
    "nj_lb_restriction_days",
    "nj_shortfall_days",
    "nj_delivery_reliability",
    "nj_mean_delivery_mgd",
    "ny_reliability",
    "ny_resiliency",
    "ny_vulnerability",
    "ny_shortfall_days",
]

PARAM_COLS: list[str] = [
    "alpha_betz_warning",
    "alpha_bm_warning",
    "m_lb",
    "tau_recovery",
    "q_nj_warning",
    "ierq_max_bg",
]


# ---------------------------------------------------------------------------
# Step 1: Load and aggregate task outputs
# ---------------------------------------------------------------------------

def load_task_outputs(task_dir: Path, n_samples: int) -> pd.DataFrame:
    """
    Load all per-sample CSVs and average metrics over the 50 realizations.

    Returns
    -------
    pd.DataFrame
        Shape (n_samples, n_metrics + n_params).  Rows indexed 0..n_samples-1
        (= sample_id order).  Samples with all-error realizations get NaN metrics.
    """
    logger.info(f"Loading task outputs from {task_dir} …")
    csvs = sorted(task_dir.glob("task_*.csv"))
    if len(csvs) == 0:
        raise FileNotFoundError(f"No task_*.csv files found in {task_dir}")
    logger.info(f"  Found {len(csvs)} CSV files")

    records = []
    missing_ids = []

    for sample_id in range(n_samples):
        path = task_dir / f"task_{sample_id:05d}.csv"
        if not path.exists():
            missing_ids.append(sample_id)
            row = {"sample_id": sample_id}
            row.update({m: np.nan for m in TARGET_METRICS})
            row.update({p: np.nan for p in PARAM_COLS})
            records.append(row)
            continue

        df = pd.read_csv(path)
        ok  = df[df["status"] == "ok"]
        row = {"sample_id": sample_id}

        # Parameter values are constant across realizations — take first row
        for col in PARAM_COLS:
            if col in df.columns:
                row[col] = float(df[col].iloc[0])

        # Metrics: mean over ok realizations; NaN if none succeeded
        for metric in TARGET_METRICS:
            if metric in ok.columns and len(ok) > 0:
                row[metric] = float(ok[metric].mean())
            else:
                row[metric] = np.nan

        records.append(row)

    if missing_ids:
        logger.warning(f"  {len(missing_ids)} missing task files — NaN inserted: {missing_ids[:10]}{'...' if len(missing_ids)>10 else ''}")

    df_all = pd.DataFrame(records).set_index("sample_id").sort_index()
    n_nan  = df_all[TARGET_METRICS].isna().any(axis=1).sum()
    logger.info(f"  {n_samples - n_nan}/{n_samples} samples fully ok  ({n_nan} with any NaN)")
    return df_all


# ---------------------------------------------------------------------------
# Step 2: Sobol analysis
# ---------------------------------------------------------------------------

def run_sobol_analysis(
    problem: dict,
    mean_metrics: pd.DataFrame,
    calc_second_order: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Run SALib Sobol analysis for each target metric.

    Returns
    -------
    si_df : pd.DataFrame
        Long-format first/total order indices.
        Columns: metric, parameter, S1, ST, S1_conf, ST_conf
    s2_df : pd.DataFrame
        Second-order indices.
        Columns: metric, param_i, param_j, S2, S2_conf
    """
    try:
        from SALib.analyze import sobol as sobol_analyze
    except ImportError:
        raise ImportError("SALib ≥1.5 required:  pip install SALib")

    param_names = problem["names"]
    si_rows  = []
    s2_rows  = []
    skipped  = []

    for metric in TARGET_METRICS:
        Y = mean_metrics[metric].values.astype(float)

        # Skip metrics with near-zero variance (SALib produces unstable indices)
        var = np.nanvar(Y)
        if var < 1e-12:
            logger.warning(f"  Skipping {metric}: variance={var:.2e} (near-zero)")
            skipped.append(metric)
            continue

        n_nan = int(np.isnan(Y).sum())
        if n_nan > 0:
            logger.warning(f"  {metric}: {n_nan} NaN values — filling with mean")
            Y = np.where(np.isnan(Y), np.nanmean(Y), Y)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            Si = sobol_analyze.analyze(
                problem, Y,
                calc_second_order=calc_second_order,
                print_to_console=False,
            )

        for i, param in enumerate(param_names):
            si_rows.append({
                "metric":    metric,
                "parameter": param,
                "S1":        float(Si["S1"][i]),
                "S1_conf":   float(Si["S1_conf"][i]),
                "ST":        float(Si["ST"][i]),
                "ST_conf":   float(Si["ST_conf"][i]),
            })

        if calc_second_order and "S2" in Si:
            for i, p1 in enumerate(param_names):
                for j, p2 in enumerate(param_names):
                    if j > i:
                        s2_rows.append({
                            "metric":   metric,
                            "param_i":  p1,
                            "param_j":  p2,
                            "S2":       float(Si["S2"][i, j]),
                            "S2_conf":  float(Si["S2_conf"][i, j]),
                        })

        logger.debug(f"  {metric}: done  (var={var:.4f})")

    if skipped:
        logger.warning(f"Skipped {len(skipped)} degenerate metrics: {skipped}")

    si_df = pd.DataFrame(si_rows)
    s2_df = pd.DataFrame(s2_rows) if s2_rows else pd.DataFrame(
        columns=["metric", "param_i", "param_j", "S2", "S2_conf"])

    return si_df, s2_df


# ---------------------------------------------------------------------------
# Step 3: Report
# ---------------------------------------------------------------------------

def write_report(si_df: pd.DataFrame, mean_metrics: pd.DataFrame, path: Path):
    """Write a human-readable summary of key Sobol indices."""
    lines = [
        "D4 Sobol Sensitivity Analysis — Summary Report",
        "=" * 60,
        f"N_samples: {len(mean_metrics)}",
        f"Parameters: {list(si_df['parameter'].unique())}",
        f"Metrics analyzed: {list(si_df['metric'].unique())}",
        "",
        "Total-order (ST) indices — each metric's most influential parameters",
        "-" * 60,
    ]

    for metric in TARGET_METRICS:
        sub = si_df[si_df["metric"] == metric].sort_values("ST", ascending=False)
        if sub.empty:
            lines.append(f"\n{metric}: SKIPPED (degenerate)")
            continue
        lines.append(f"\n{metric}:")
        for _, row in sub.iterrows():
            bar = "█" * int(max(0, row["ST"]) * 30)
            lines.append(
                f"  {row['parameter']:<22}  ST={row['ST']:+.4f} ±{row['ST_conf']:.4f}  "
                f"S1={row['S1']:+.4f} ±{row['S1_conf']:.4f}  {bar}"
            )

    lines += [
        "",
        "Metric variance summary",
        "-" * 60,
    ]
    for metric in TARGET_METRICS:
        vals = mean_metrics[metric].dropna()
        if len(vals) == 0:
            lines.append(f"  {metric:<35}  ALL NaN")
        else:
            lines.append(
                f"  {metric:<35}  "
                f"mean={vals.mean():>10.4f}  std={vals.std():>9.4f}  "
                f"var={vals.var():>12.4f}"
            )

    report = "\n".join(lines)
    path.write_text(report)
    logger.info(f"Report written → {path}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--task-dir",
        type=Path,
        default=Path("D4_distributed_risk/results/sobol/task_outputs"),
        help="Directory containing task_*.csv files.",
    )
    parser.add_argument(
        "--design",
        type=Path,
        default=Path("D4_distributed_risk/results/sobol/sobol_design.json"),
        help="SALib problem definition JSON (sobol_design.json).",
    )
    parser.add_argument(
        "--outdir",
        type=Path,
        default=Path("D4_distributed_risk/results/sobol"),
        help="Output directory for parquet/CSV/report.",
    )
    parser.add_argument(
        "--no-s2", action="store_true",
        help="Skip second-order index computation (faster).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING"],
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)-8s %(message)s",
        datefmt="%H:%M:%S",
    )

    # Load problem definition
    with open(args.design) as f:
        problem = json.load(f)

    n_params  = problem["num_vars"]
    # Total Saltelli samples = N × (2k + 2); infer N from file count
    # Use the number of task files as the authoritative count
    n_csvs = len(list(args.task_dir.glob("task_*.csv")))
    n_samples = n_csvs
    logger.info(f"SALib problem: {n_params} parameters, {n_samples} samples")
    logger.info(f"  N_base = {n_samples // (2*n_params + 2)}  "
                f"(= total / (2k+2) = {n_samples} / {2*n_params+2})")

    # Step 1: Load
    mean_metrics = load_task_outputs(args.task_dir, n_samples)
    args.outdir.mkdir(parents=True, exist_ok=True)
    mean_parquet = args.outdir / "sobol_mean_metrics.parquet"
    mean_metrics.to_parquet(mean_parquet)
    logger.info(f"Mean metrics written → {mean_parquet}  shape={mean_metrics.shape}")

    # Step 2: Sobol indices
    logger.info("Computing Sobol indices …")
    si_df, s2_df = run_sobol_analysis(
        problem, mean_metrics,
        calc_second_order=not args.no_s2,
    )

    # Step 3: Write outputs
    si_parquet = args.outdir / "sobol_indices.parquet"
    si_csv     = args.outdir / "sobol_indices.csv"
    si_df.to_parquet(si_parquet, index=False)
    si_df.to_csv(si_csv, index=False)
    logger.info(f"S1/ST indices → {si_parquet}  ({len(si_df)} rows)")

    if not s2_df.empty:
        s2_parquet = args.outdir / "sobol_S2.parquet"
        s2_df.to_parquet(s2_parquet, index=False)
        logger.info(f"S2 indices    → {s2_parquet}  ({len(s2_df)} rows)")

    report = write_report(si_df, mean_metrics, args.outdir / "sobol_analysis_report.txt")
    print("\n" + report)

    logger.info("Done.")


if __name__ == "__main__":
    main()

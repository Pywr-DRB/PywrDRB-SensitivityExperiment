"""
D4 — Sobol sensitivity analysis convergence and stability diagnostics.

Produces four diagnostic outputs for publication appendix:

  1. Bootstrap confidence intervals on S1 and ST per metric per parameter
  2. Convergence curve: S1/ST vs. increasing sample size
  3. Realization sensitivity: how much do indices shift across realization subsets?
  4. Top-parameter rank stability: are the top-2 parameters stable across subsets?

Usage
-----
    cd ~/dissertation
    module load python/3.11.5 && source venv/bin/activate
    python D4_distributed_risk/sensitivity/sobol_diagnostics.py \\
        --sweep sobol_sweep3 \\
        --outdir D4_distributed_risk/results/sobol_sweep3/diagnostics

References
----------
Saltelli et al. (2010) variance-based sensitivity analysis.
Herman & Usher (2017) SALib.
Iwanaga, Usher & Herman (2022) SESMO.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

_THIS = Path(__file__).resolve()
_REPO = _THIS.parents[2]
sys.path.insert(0, str(_REPO / "shared"))
sys.path.insert(0, str(_REPO))

try:
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import sobol as sobol_sample
except ImportError:
    raise ImportError("SALib not installed — pip install SALib>=1.5")

logger = logging.getLogger(__name__)

# Metrics to diagnose (focus on the five primary party metrics)
FOCUS_METRICS = [
    "de_reliability",
    "nyc_ierq_exhaustion_reliability",
    "pa_depletion_reliability",
    "nj_delivery_reliability",
    "ny_reliability",
]

METRIC_LABELS = {
    "de_reliability":                  "DE reliability",
    "nyc_ierq_exhaustion_reliability": "NYC IERQ reliability",
    "pa_depletion_reliability":        "PA depletion reliability",
    "nj_delivery_reliability":         "NJ delivery reliability",
    "ny_reliability":                  "NY reliability",
}

PARAM_SHORT = {
    "alpha_betz_warning": "α_BW",
    "alpha_bm_warning":   "α_BMW",
    "m_lb":               "m_LB",
    "ierq_max_bg":        "I_max",
    "erq_cap_mg":         "C_ERQ",
    "q_nj_warning":       "Q_NJ_W",
    "tau_recovery":       "τ_R",
}


def load_sweep(sweep_dir: Path) -> tuple[pd.DataFrame, dict, dict]:
    """Load Sobol mean metrics, design JSON, and samples CSV."""
    import json
    mean_metrics = pd.read_parquet(sweep_dir / "sobol_mean_metrics.parquet")
    with open(sweep_dir / "sobol_design.json") as f:
        problem = json.load(f)
    return mean_metrics, problem


def _analyze_subset(Y: np.ndarray, problem: dict, n_bootstrap: int = 100) -> dict:
    """Run Sobol analysis on Y and return S1/ST with bootstrap CIs."""
    result = sobol_analyze.analyze(
        problem, Y,
        calc_second_order=True,
        conf_level=0.95,
        print_to_console=False,
        seed=42,
    )
    return {
        "S1":      result["S1"],
        "S1_conf": result["S1_conf"],
        "ST":      result["ST"],
        "ST_conf": result["ST_conf"],
    }


# ---------------------------------------------------------------------------
# Diagnostic 1 — Bootstrap confidence intervals
# ---------------------------------------------------------------------------

def diag1_confidence_intervals(
    df: pd.DataFrame,
    problem: dict,
    outdir: Path,
    n_bootstrap: int = 500,
) -> pd.DataFrame:
    """Plot S1 and ST with 95% confidence intervals for each focus metric."""
    params = problem["names"]
    short  = [PARAM_SHORT.get(p, p) for p in params]
    n_p    = len(params)
    rows   = []

    fig, axes = plt.subplots(
        len(FOCUS_METRICS), 2,
        figsize=(12, 3 * len(FOCUS_METRICS)),
        sharex=True,
    )
    fig.suptitle(
        "Diagnostic 1 — Sobol Indices with 95% Bootstrap Confidence Intervals\n"
        "Error bars = ±conf (SALib Jansen estimator, 95% CI)",
        fontsize=10,
    )

    for row_i, metric in enumerate(FOCUS_METRICS):
        if metric not in df.columns:
            continue
        Y = df[metric].values
        res = _analyze_subset(Y, problem, n_bootstrap)

        for col_i, (idx_key, conf_key, title) in enumerate([
            ("S1", "S1_conf", "First-order S1"),
            ("ST", "ST_conf", "Total-order ST"),
        ]):
            ax = axes[row_i, col_i]
            vals  = res[idx_key]
            confs = res[conf_key]
            x     = np.arange(n_p)

            ax.bar(x, vals, color="#4878d0", alpha=0.75, width=0.6)
            ax.errorbar(x, vals, yerr=confs, fmt="none",
                        color="black", capsize=4, lw=1.2)
            ax.axhline(0, color="gray", lw=0.7)
            ax.set_xticks(x)
            if row_i == len(FOCUS_METRICS) - 1:
                ax.set_xticklabels(short, rotation=30, ha="right", fontsize=8)
            else:
                ax.set_xticklabels([])
            ax.set_ylabel(METRIC_LABELS.get(metric, metric), fontsize=8)
            if row_i == 0:
                ax.set_title(title, fontsize=9)
            ax.set_ylim(-0.1, max(1.0, (vals + confs).max() + 0.05))
            ax.grid(axis="y", alpha=0.25)
            ax.tick_params(labelsize=7)

        for i, p in enumerate(params):
            rows.append({
                "metric": metric, "parameter": p,
                "S1": res["S1"][i], "S1_conf": res["S1_conf"][i],
                "ST": res["ST"][i], "ST_conf": res["ST_conf"][i],
            })

    plt.tight_layout()
    fig.savefig(outdir / "diag1_confidence_intervals.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved diag1_confidence_intervals.png")

    result_df = pd.DataFrame(rows)
    result_df.to_csv(outdir / "diag1_indices_with_ci.csv", index=False)
    return result_df


# ---------------------------------------------------------------------------
# Diagnostic 2 — Convergence curve
# ---------------------------------------------------------------------------

def diag2_convergence(
    df: pd.DataFrame,
    problem: dict,
    outdir: Path,
    n_steps: int = 10,
) -> pd.DataFrame:
    """
    Plot S1/ST vs. increasing sample size (using successive fractions of df).

    At each step, use the first k rows of df (k = total/n_steps, 2*total/n_steps, ...).
    Check that SALib's Saltelli constraint is satisfied: n must be a multiple of (2k+2).
    """
    params = problem["names"]
    short  = [PARAM_SHORT.get(p, p) for p in params]
    n_total = len(df)
    k = len(params)
    block = n_total // n_steps

    rows = []
    sizes = []
    s1_by_size = {p: [] for p in params}
    st_by_size = {p: [] for p in params}

    fig, axes = plt.subplots(
        len(FOCUS_METRICS), 1,
        figsize=(10, 3 * len(FOCUS_METRICS)),
        sharex=True,
    )
    fig.suptitle(
        "Diagnostic 2 — Sobol Index Convergence with Sample Size\n"
        "Shaded = ±conf at each step",
        fontsize=10,
    )

    colors = plt.cm.tab10(np.linspace(0, 1, len(params)))

    for metric, ax in zip(FOCUS_METRICS, axes):
        if metric not in df.columns:
            continue
        sizes_m  = []
        s1_lines = {p: [] for p in params}
        s1_conf  = {p: [] for p in params}
        st_lines = {p: [] for p in params}
        st_conf  = {p: [] for p in params}

        for step in range(1, n_steps + 1):
            n_use = step * block
            sub   = df.iloc[:n_use]
            Y     = sub[metric].values
            try:
                res = _analyze_subset(Y, problem)
                for i, p in enumerate(params):
                    s1_lines[p].append(res["S1"][i])
                    s1_conf[p].append(res["S1_conf"][i])
                    st_lines[p].append(res["ST"][i])
                    st_conf[p].append(res["ST_conf"][i])
                sizes_m.append(n_use)
            except Exception:
                pass

        for i, (p, c) in enumerate(zip(params, colors)):
            if not sizes_m:
                continue
            s1_arr = np.array(s1_lines[p])
            st_arr = np.array(st_lines[p])
            cf_arr = np.array(st_conf[p])
            ax.plot(sizes_m, st_arr, color=c, lw=1.5, label=PARAM_SHORT.get(p, p))
            ax.fill_between(sizes_m,
                            st_arr - cf_arr, st_arr + cf_arr,
                            color=c, alpha=0.12)

        ax.set_ylabel(f"ST\n{METRIC_LABELS.get(metric, metric)}", fontsize=8)
        ax.axhline(0, color="gray", lw=0.6)
        ax.grid(alpha=0.2)
        ax.tick_params(labelsize=7)

    axes[0].legend(fontsize=7, loc="upper right", ncol=3)
    axes[-1].set_xlabel("Number of Sobol samples", fontsize=9)
    plt.tight_layout()
    fig.savefig(outdir / "diag2_convergence.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved diag2_convergence.png")
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Diagnostic 3 — Realization sensitivity
# ---------------------------------------------------------------------------

def diag3_realization_sensitivity(
    task_dir: Path,
    problem: dict,
    generation_log: Path,
    outdir: Path,
    n_subsets: int = 10,
    subset_size: int = 25,
) -> pd.DataFrame:
    """
    Check how sensitive Sobol indices are to which 25 of the 50 realizations
    are included.  Loads individual task CSVs and averages over random subsets.

    Requires task_outputs/ directory with task_XXXXX.csv files.
    """
    params = problem["names"]
    task_files = sorted(task_dir.glob("task_*.csv"))
    if len(task_files) < 100:
        logger.warning("Too few task files (%d) — skipping diag3", len(task_files))
        return pd.DataFrame()

    # Load generation log to get pct_change per realization
    log = pd.read_csv(generation_log) if generation_log.exists() else None
    real_ids = list(range(50))

    rng = np.random.default_rng(42)
    rows = []

    for metric in FOCUS_METRICS:
        subset_s1 = []
        subset_st = []
        for _ in range(n_subsets):
            chosen = rng.choice(real_ids, size=subset_size, replace=False)
            Y_list = []
            for tf in task_files[:len(problem["names"]) * 200]:  # sample of tasks
                try:
                    df_t = pd.read_csv(tf)
                    sub  = df_t[df_t["realization_id"].isin(chosen)]
                    if metric in sub.columns and len(sub) > 0:
                        Y_list.append(sub[metric].mean())
                except Exception:
                    pass
            if len(Y_list) < 100:
                continue
            Y = np.array(Y_list)
            try:
                res = _analyze_subset(Y, problem)
                subset_s1.append(res["S1"])
                subset_st.append(res["ST"])
            except Exception:
                pass

        if subset_s1:
            s1_arr = np.array(subset_s1)
            st_arr = np.array(subset_st)
            for i, p in enumerate(params):
                rows.append({
                    "metric": metric, "parameter": p,
                    "S1_mean": s1_arr[:, i].mean(), "S1_std": s1_arr[:, i].std(),
                    "ST_mean": st_arr[:, i].mean(), "ST_std": st_arr[:, i].std(),
                })

    result_df = pd.DataFrame(rows)
    if not result_df.empty:
        result_df.to_csv(outdir / "diag3_realization_sensitivity.csv", index=False)
        logger.info("Saved diag3_realization_sensitivity.csv")
    return result_df


# ---------------------------------------------------------------------------
# Diagnostic 4 — Top-parameter rank stability
# ---------------------------------------------------------------------------

def diag4_rank_stability(
    df: pd.DataFrame,
    problem: dict,
    outdir: Path,
    n_bootstrap: int = 200,
    n_top: int = 2,
) -> pd.DataFrame:
    """
    Bootstrap the full dataset to check whether the top-n parameters
    by ST are stable across bootstrap resamples.

    Reports: fraction of bootstrap resamples where each parameter
    appears in the top-n for each metric.
    """
    params = problem["names"]
    short  = [PARAM_SHORT.get(p, p) for p in params]
    rng    = np.random.default_rng(42)
    rows   = []

    fig, axes = plt.subplots(
        1, len(FOCUS_METRICS),
        figsize=(4 * len(FOCUS_METRICS), 5),
    )
    fig.suptitle(
        f"Diagnostic 4 — Top-{n_top} Parameter Rank Stability\n"
        f"Fraction of {n_bootstrap} bootstrap resamples where parameter ranks in top {n_top} by ST",
        fontsize=10,
    )

    for ax, metric in zip(axes, FOCUS_METRICS):
        if metric not in df.columns:
            continue
        Y_full = df[metric].values
        n      = len(Y_full)
        top_counts = np.zeros(len(params))

        for _ in range(n_bootstrap):
            idx = rng.integers(0, n, size=n)
            Y_b = Y_full[idx]
            try:
                res   = _analyze_subset(Y_b, problem)
                ranks = np.argsort(-res["ST"])  # descending
                for r in range(n_top):
                    top_counts[ranks[r]] += 1
            except Exception:
                pass

        fracs = top_counts / n_bootstrap
        x = np.arange(len(params))
        ax.bar(x, fracs, color="#e05c2e", alpha=0.8, width=0.7)
        ax.axhline(0.5, color="black", lw=0.8, ls="--", alpha=0.6,
                   label="50% threshold")
        ax.set_xticks(x)
        ax.set_xticklabels(short, rotation=45, ha="right", fontsize=8)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel(f"Fraction in top {n_top}", fontsize=8)
        ax.set_title(METRIC_LABELS.get(metric, metric), fontsize=8)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(labelsize=7)

        for i, p in enumerate(params):
            rows.append({
                "metric": metric, "parameter": p,
                f"frac_top{n_top}": fracs[i],
            })

    plt.tight_layout()
    fig.savefig(outdir / "diag4_rank_stability.png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved diag4_rank_stability.png")

    result_df = pd.DataFrame(rows)
    result_df.to_csv(outdir / f"diag4_rank_stability_top{n_top}.csv", index=False)
    return result_df


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sweep",  default="sobol_sweep3",
                    help="Sweep results subdirectory under D4_distributed_risk/results/")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="Output directory (default: results/<sweep>/diagnostics/)")
    ap.add_argument("--log-level", default="INFO",
                    choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = ap.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level),
                        format="%(asctime)s %(levelname)-8s %(message)s")

    sweep_dir = _REPO / "D4_distributed_risk" / "results" / args.sweep
    outdir    = args.outdir or sweep_dir / "diagnostics"
    outdir.mkdir(parents=True, exist_ok=True)

    logger.info("Loading sweep: %s", sweep_dir)
    df, problem = load_sweep(sweep_dir)
    logger.info("  %d samples × %d params", len(df), len(problem["names"]))

    logger.info("[1] Confidence intervals ...")
    diag1_confidence_intervals(df, problem, outdir)

    logger.info("[2] Convergence curves ...")
    diag2_convergence(df, problem, outdir)

    logger.info("[4] Rank stability ...")
    diag4_rank_stability(df, problem, outdir)

    # Diag 3 requires individual task CSVs — run separately if needed
    task_dir = sweep_dir / "task_outputs"
    gen_log  = sweep_dir / "synthetic_flows" / "generation_log.csv"
    if task_dir.exists() and len(list(task_dir.glob("task_*.csv"))) > 500:
        logger.info("[3] Realization sensitivity ...")
        diag3_realization_sensitivity(task_dir, problem, gen_log, outdir)
    else:
        logger.info("[3] Skipping realization sensitivity — insufficient task files")

    logger.info("All diagnostics saved to: %s", outdir)


if __name__ == "__main__":
    main()

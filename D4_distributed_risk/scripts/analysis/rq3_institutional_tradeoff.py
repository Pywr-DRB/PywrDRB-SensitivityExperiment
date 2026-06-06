"""
RQ3 — Institutional risk redistribution (Options A, B, C).

Replaces PRIM scenario discovery with peer-reviewable analyses on the Sobol ensemble:

  A. Multi-party tradeoff matrix — win-win / redistribution / lose-lose occupancy
     with bootstrap CIs over synthetic realizations per Saltelli sample.

  B. Regime-stratified policy response — metric response vs institutional parameters,
     faceted by failure regime (``overall_regime`` from baseline when available,
     else a documented proxy from sample-mean exhaustion/depletion metrics).

  C. Sobol second-order (S2) interaction analysis — parameter pairs that drive
     asymmetric party outcomes (from ``sobol_analysis.py`` outputs).

Usage
-----
    cd ~/dissertation
    source venv/bin/activate
    python D4_distributed_risk/analysis/rq3_institutional_tradeoff.py \\
        --task-dir   D4_distributed_risk/results/sobol/task_outputs \\
        --sobol-dir  D4_distributed_risk/results/sobol \\
        --baseline   D4_distributed_risk/results/baseline/rrv_summary.csv \\
        --outdir     D4_distributed_risk/results/rq3

Prerequisites
-------------
- Sobol sweep task CSVs (14,336 × 50 realizations)
- ``sobol_design.json``, ``sobol_indices.parquet``, ``sobol_S2.parquet`` (run sobol_analysis.py)
- Baseline ``rrv_summary`` with ``overall_regime`` column (re-run / reaggregate if missing)

See ``committee/D1_D4_experimental_plans.md`` Table D4-4 Step 5.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Party → primary reliability column (higher = better for that party)
# ---------------------------------------------------------------------------

PARTY_RELIABILITY: dict[str, str] = {
    "DE":  "de_reliability",
    "NYC": "nyc_ierq_exhaustion_reliability",
    "PA":  "pa_depletion_reliability",
    "NJ":  "nj_delivery_reliability",
    "NY":  "ny_reliability",
}

TRADEOFF_CLASSES = ("win_win", "redistribution", "lose_lose", "mixed_neutral")

# Parameters for Option B response surfaces
POLICY_PARAMS = (
    "alpha_betz_warning",
    "alpha_bm_warning",
    "m_lb",
    "tau_recovery",
    "q_nj_warning",
    "ierq_max_bg",
    "erq_cap_mg",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_baseline_params() -> dict[str, float]:
    """Baseline parameter values from sensitivity config."""
    from D4_distributed_risk.lib.sensitivity.config import PARAMETERS

    return {k: float(v["baseline"]) for k, v in PARAMETERS.items()}


def find_baseline_sample_id(
    mean_metrics: pd.DataFrame,
    rtol: float = 1e-4,
    atol: float = 1e-6,
) -> int:
    """
    Return sample_id whose parameters match config baselines.

    Falls back to the row closest in L2 norm if no exact match (Saltelli grid).
    """
    baselines = _load_baseline_params()
    param_cols = [c for c in baselines if c in mean_metrics.columns]
    if not param_cols:
        raise ValueError("No parameter columns in mean_metrics")

    diff = mean_metrics[param_cols].sub(pd.Series(baselines), axis=1).abs()
    exact = (diff <= atol + rtol * diff.abs()).all(axis=1)
    if exact.any():
        return int(mean_metrics.index[exact][0])

    dist = (diff ** 2).sum(axis=1)
    sid = int(dist.idxmin())
    logger.warning(
        "No exact baseline parameter vector in Sobol design — "
        "using closest sample_id=%s (L2=%.4g)",
        sid,
        float(dist.loc[sid]),
    )
    return sid


def classify_realization_tradeoff(
    deltas: dict[str, float],
    epsilon: float = 1e-3,
) -> str:
    """
    Classify one realization's multi-party reliability changes vs baseline.

    win_win         : no party worsens beyond ε, at least one improves beyond ε
    lose_lose       : all parties worsen beyond ε
    redistribution  : some improve and some worsen beyond ε
    mixed_neutral   : all changes within ±ε
    """
    improved = []
    worsened = []
    for _party, d in deltas.items():
        if d > epsilon:
            improved.append(True)
        elif d < -epsilon:
            worsened.append(True)

    n_imp = len(improved)
    n_worse = len(worsened)
    n_parties = len(deltas)

    if n_worse == 0 and n_imp > 0:
        return "win_win"
    if n_worse == n_parties:
        return "lose_lose"
    if n_imp > 0 and n_worse > 0:
        return "redistribution"
    return "mixed_neutral"


def bootstrap_class_fractions(
    classes: np.ndarray,
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, tuple[float, float, float]]:
    """Bootstrap 2.5/50/97.5 percentiles of class fractions."""
    rng = np.random.default_rng(seed)
    n = len(classes)
    if n == 0:
        return {c: (np.nan, np.nan, np.nan) for c in TRADEOFF_CLASSES}

    fracs = {c: [] for c in TRADEOFF_CLASSES}
    for _ in range(n_boot):
        draw = rng.choice(classes, size=n, replace=True)
        for c in TRADEOFF_CLASSES:
            fracs[c].append((draw == c).mean())

    out = {}
    for c in TRADEOFF_CLASSES:
        arr = np.array(fracs[c])
        out[c] = (float(np.percentile(arr, 2.5)), float(np.median(arr)), float(np.percentile(arr, 97.5)))
    return out


# ---------------------------------------------------------------------------
# Option A — tradeoff matrix
# ---------------------------------------------------------------------------

def run_option_a(
    task_dir: Path,
    mean_metrics: pd.DataFrame,
    baseline_sample_id: int,
    epsilon: float = 1e-3,
    n_boot: int = 1000,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Returns
    -------
    sample_summary : one row per Saltelli sample (class fractions + dominant class)
    delta_matrix   : long format (sample_id, party, delta_reliability)
    corr_matrix    : correlation of party deltas across samples (pooled realizations)
    """
    ref_path = task_dir / f"task_{baseline_sample_id:05d}.csv"
    if not ref_path.exists():
        raise FileNotFoundError(f"Baseline reference task missing: {ref_path}")

    ref_df = pd.read_csv(ref_path)
    ref_ok = ref_df[ref_df["status"] == "ok"].set_index("realization_id")

    rel_cols = list(PARTY_RELIABILITY.values())
    sample_rows = []
    delta_rows = []

    for sample_id in mean_metrics.index:
        path = task_dir / f"task_{sample_id:05d}.csv"
        if not path.exists():
            continue

        df = pd.read_csv(path)
        ok = df[df["status"] == "ok"]
        classes = []

        for _, row in ok.iterrows():
            rid = int(row["realization_id"])
            if rid not in ref_ok.index:
                continue
            ref_row = ref_ok.loc[rid]
            deltas = {}
            for party, col in PARTY_RELIABILITY.items():
                if col not in row or col not in ref_row:
                    continue
                dv = float(row[col]) - float(ref_row[col])
                deltas[party] = dv
                delta_rows.append({
                    "sample_id": sample_id,
                    "realization_id": rid,
                    "party": party,
                    "delta_reliability": dv,
                })
            if len(deltas) == len(PARTY_RELIABILITY):
                classes.append(classify_realization_tradeoff(deltas, epsilon=epsilon))

        if not classes:
            continue

        arr = np.array(classes)
        fracs = {c: float((arr == c).mean()) for c in TRADEOFF_CLASSES}
        boot = bootstrap_class_fractions(arr, n_boot=n_boot)
        dominant = max(fracs, key=fracs.get)

        row_out = {"sample_id": sample_id, "dominant_class": dominant, "n_realizations": len(classes)}
        for c in TRADEOFF_CLASSES:
            row_out[f"frac_{c}"] = fracs[c]
            lo, med, hi = boot[c]
            row_out[f"frac_{c}_ci_lo"] = lo
            row_out[f"frac_{c}_ci_hi"] = hi
        sample_rows.append(row_out)

    sample_summary = pd.DataFrame(sample_rows)
    delta_long = pd.DataFrame(delta_rows)

    # 5×5 correlation of mean delta per sample (across samples, not realizations)
    if delta_long.empty:
        corr_matrix = pd.DataFrame()
    else:
        wide = (
            delta_long.groupby(["sample_id", "party"])["delta_reliability"]
            .mean()
            .unstack("party")
        )
        corr_matrix = wide.corr()

    return sample_summary, delta_long, corr_matrix


def occupancy_by_parameter_tertile(
    sample_summary: pd.DataFrame,
    mean_metrics: pd.DataFrame,
    param: str,
) -> pd.DataFrame:
    """Fraction win-win / redistribution by tertile of one Sobol parameter."""
    if param not in mean_metrics.columns:
        return pd.DataFrame()

    merged = sample_summary.merge(
        mean_metrics[[param]].reset_index().rename(columns={"index": "sample_id"}),
        on="sample_id",
        how="inner",
    )
    merged["tertile"] = pd.qcut(merged[param], 3, labels=["low", "mid", "high"], duplicates="drop")
    rows = []
    for tertile, grp in merged.groupby("tertile", observed=True):
        n = len(grp)
        rows.append({
            "parameter": param,
            "tertile": str(tertile),
            "n_samples": n,
            "frac_win_win": grp["frac_win_win"].mean(),
            "frac_redistribution": grp["frac_redistribution"].mean(),
            "frac_lose_lose": grp["frac_lose_lose"].mean(),
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Option B — regime-stratified response
# ---------------------------------------------------------------------------

def infer_regime_proxy(row: pd.Series) -> str:
    """
    Proxy regime label from sample-mean metrics when ``overall_regime`` is absent.

    NYC-limited : low NYC IERQ exhaustion reliability, PA not severely depleted
    LB-limited  : low PA depletion reliability
    Otherwise   : normal
    """
    nyc = float(row.get("nyc_ierq_exhaustion_reliability", np.nan))
    pa = float(row.get("pa_depletion_reliability", np.nan))
    if np.isnan(nyc) or np.isnan(pa):
        return "unknown"
    if nyc < 0.25 and pa >= 0.35:
        return "NYC-limited"
    if pa < 0.35:
        return "LB-limited"
    return "normal"


def run_option_b(
    mean_metrics: pd.DataFrame,
    baseline_regimes: Optional[pd.Series] = None,
    response_metric: str = "de_reliability",
    params: tuple[str, ...] = POLICY_PARAMS,
) -> pd.DataFrame:
    """
    Binned mean response_metric vs each policy parameter, faceted by regime.

    If ``baseline_regimes`` is provided (index = sample_id or member_id), merges
    on sample_id when lengths align; otherwise uses ``infer_regime_proxy``.
    """
    df = mean_metrics.copy()
    if baseline_regimes is not None and len(baseline_regimes) == len(df):
        df["regime"] = baseline_regimes.values
    else:
        df["regime"] = df.apply(infer_regime_proxy, axis=1)

    rows = []
    for regime, g_reg in df.groupby("regime"):
        for param in params:
            if param not in g_reg.columns:
                continue
            try:
                g_reg = g_reg.copy()
                g_reg["bin"] = pd.qcut(g_reg[param], 5, duplicates="drop")
            except ValueError:
                continue
            for bin_label, g_bin in g_reg.groupby("bin", observed=True):
                rows.append({
                    "regime": regime,
                    "parameter": param,
                    "bin": str(bin_label),
                    "param_mid": float(g_bin[param].median()),
                    "n_samples": len(g_bin),
                    "mean_response": float(g_bin[response_metric].mean()),
                    "std_response": float(g_bin[response_metric].std()),
                    "response_metric": response_metric,
                })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Option C — S2 asymmetric interactions
# ---------------------------------------------------------------------------

def run_option_c(
    s2_path: Path,
    si_path: Path,
    top_n: int = 10,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Summarize top S2 interactions per party-relevant metric.

    Returns (top_s2_long, party_asymmetry) where party_asymmetry flags pairs
    with high S2 on one party's metric but low on another's.
    """
    if not s2_path.exists():
        logger.warning("S2 parquet not found — run sobol_analysis.py without --no-s2")
        return pd.DataFrame(), pd.DataFrame()

    s2 = pd.read_parquet(s2_path)
    si = pd.read_parquet(si_path)

    metric_to_party = {}
    for party, col in PARTY_RELIABILITY.items():
        metric_to_party[col] = party

    top_rows = []
    for metric in s2["metric"].unique():
        sub = s2[s2["metric"] == metric].sort_values("S2", ascending=False).head(top_n)
        party = metric_to_party.get(metric, "other")
        for _, row in sub.iterrows():
            top_rows.append({
                "metric": metric,
                "party": party,
                "param_i": row["param_i"],
                "param_j": row["param_j"],
                "S2": row["S2"],
                "S2_conf": row.get("S2_conf", np.nan),
            })
    top_s2 = pd.DataFrame(top_rows)

    # Asymmetry: compare ST on DE vs NJ for same parameter
    asym_rows = []
    if not si.empty:
        for param in si["parameter"].unique():
            de_st = si[(si["parameter"] == param) & (si["metric"] == "de_reliability")]["ST"]
            nj_st = si[(si["parameter"] == param) & (si["metric"] == "nj_delivery_reliability")]["ST"]
            if len(de_st) and len(nj_st):
                asym_rows.append({
                    "parameter": param,
                    "ST_de": float(de_st.iloc[0]),
                    "ST_nj": float(nj_st.iloc[0]),
                    "ST_ratio_de_over_nj": float(de_st.iloc[0] / (nj_st.iloc[0] + 1e-12)),
                })
    party_asymmetry = pd.DataFrame(asym_rows)

    return top_s2, party_asymmetry


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def write_rq3_report(
    outdir: Path,
    sample_summary: pd.DataFrame,
    occupancy: pd.DataFrame,
    option_b: pd.DataFrame,
    top_s2: pd.DataFrame,
    baseline_sample_id: int,
    epsilon: float,
) -> None:
    lines = [
        "D4 RQ3 — Institutional Risk Redistribution",
        "=" * 60,
        f"Baseline reference sample_id: {baseline_sample_id}",
        f"Tradeoff epsilon (reliability): {epsilon}",
        "",
        "Option A — global class occupancy (across all Saltelli samples)",
        "-" * 60,
    ]
    if not sample_summary.empty:
        for c in TRADEOFF_CLASSES:
            col = f"frac_{c}"
            if col in sample_summary.columns:
                lines.append(f"  {c:18s}  mean={sample_summary[col].mean():.3f}  "
                             f"median={sample_summary[col].median():.3f}")
        lines.append(f"  Samples analyzed: {len(sample_summary)}")
    else:
        lines.append("  (no data)")

    lines += ["", "Option A — occupancy by parameter tertile (first 3 params)", "-" * 60]
    if not occupancy.empty:
        lines.append(occupancy.head(15).to_string(index=False))
    else:
        lines.append("  (no data)")

    lines += ["", "Option B — regime-stratified bins (DE reliability)", "-" * 60]
    if not option_b.empty:
        preview = option_b[option_b["response_metric"] == "de_reliability"].head(20)
        lines.append(preview.to_string(index=False))
    else:
        lines.append("  (no data)")

    lines += ["", "Option C — top S2 interactions (first 15 rows)", "-" * 60]
    if not top_s2.empty:
        lines.append(top_s2.head(15).to_string(index=False))
    else:
        lines.append("  (no S2 file — run sobol_analysis.py)")

    text = "\n".join(lines)
    (outdir / "rq3_analysis_report.txt").write_text(text)
    logger.info("Report → %s", outdir / "rq3_analysis_report.txt")


def load_mean_metrics(sobol_dir: Path, task_dir: Path) -> pd.DataFrame:
    """Prefer cached sobol_mean_metrics.parquet; else aggregate task CSVs."""
    cached = sobol_dir / "sobol_mean_metrics.parquet"
    if cached.exists():
        return pd.read_parquet(cached)

    from D4_distributed_risk.lib.sensitivity.sobol_analysis import load_task_outputs

    n_samples = len(list(task_dir.glob("task_*.csv")))
    return load_task_outputs(task_dir, n_samples)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--task-dir", type=Path, default=Path("D4_distributed_risk/results/sobol/task_outputs"))
    parser.add_argument("--sobol-dir", type=Path, default=Path("D4_distributed_risk/results/sobol"))
    parser.add_argument("--baseline", type=Path, default=Path("D4_distributed_risk/results/baseline/rrv_summary.csv"))
    parser.add_argument("--outdir", type=Path, default=Path("D4_distributed_risk/results/rq3"))
    parser.add_argument("--epsilon", type=float, default=1e-3, help="Min |Δreliability| for improve/worsen.")
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING"])
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format="%(levelname)s %(message)s")

    args.outdir.mkdir(parents=True, exist_ok=True)
    mean_metrics = load_mean_metrics(args.sobol_dir, args.task_dir)
    baseline_sid = find_baseline_sample_id(mean_metrics)

    sample_summary, delta_long, corr_matrix = run_option_a(
        args.task_dir, mean_metrics, baseline_sid, epsilon=args.epsilon, n_boot=args.n_boot,
    )
    sample_summary.to_csv(args.outdir / "tradeoff_sample_summary.csv", index=False)
    delta_long.to_csv(args.outdir / "tradeoff_delta_long.csv", index=False)
    if not corr_matrix.empty:
        corr_matrix.to_csv(args.outdir / "tradeoff_delta_corr_5x5.csv")

    occupancy_parts = []
    for param in ("alpha_betz_warning", "alpha_bm_warning", "m_lb", "ierq_max_bg", "erq_cap_mg"):
        occ = occupancy_by_parameter_tertile(sample_summary, mean_metrics, param)
        if not occ.empty:
            occupancy_parts.append(occ)
    occupancy = pd.concat(occupancy_parts, ignore_index=True) if occupancy_parts else pd.DataFrame()
    occupancy.to_csv(args.outdir / "tradeoff_occupancy_by_param.csv", index=False)

    baseline_regimes = None
    if args.baseline.exists():
        bl = pd.read_csv(args.baseline)
        if "overall_regime" in bl.columns and "realization_id" in bl.columns:
            # Amestoy members — not 1:1 with synthetic r; use distribution only for docs
            logger.info("Baseline has overall_regime (%d members) — Option B uses proxy unless sweep adds regime", len(bl))
        elif "overall_regime" in bl.columns:
            baseline_regimes = bl["overall_regime"]

    option_b = run_option_b(mean_metrics, baseline_regimes=baseline_regimes)
    option_b.to_csv(args.outdir / "regime_stratified_response.csv", index=False)

    top_s2, party_asym = run_option_c(
        args.sobol_dir / "sobol_S2.parquet",
        args.sobol_dir / "sobol_indices.parquet",
    )
    top_s2.to_csv(args.outdir / "sobol_s2_top_interactions.csv", index=False)
    party_asym.to_csv(args.outdir / "sobol_party_asymmetry_ST.csv", index=False)

    write_rq3_report(
        args.outdir, sample_summary, occupancy, option_b, top_s2,
        baseline_sid, args.epsilon,
    )
    logger.info("RQ3 outputs written to %s", args.outdir)


if __name__ == "__main__":
    main()

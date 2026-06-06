"""
Shared helpers for D4 publication figures (regime traces, Sobol fallbacks).
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from _paths import D4, PATHS, PARTY_RELIABILITY, OBLIGATION_WEIGHTS

LB_CAPACITY_MG = 20_950.0
BETZ_CAP_MG = 13_500.0
BM_CAP_MG = 7_450.0
IERQ_MAX_MG = 6_090.0
IERQ_EXHAUSTION_MG = 500.0
LB_CONSERVATION_FRAC = (
    BETZ_CAP_MG * 0.737 + BM_CAP_MG * 0.689
) / (BETZ_CAP_MG + BM_CAP_MG)

REGIME_NAMES = {0: "normal", 1: "NYC-limited", 2: "LB-limited", 3: "co-limited"}


def resolve_sobol_dir() -> Path:
    """Prefer sweep3 when analysis outputs exist; otherwise use completed sweep 1."""
    sweep3 = D4 / "results" / "sobol_sweep3"
    sweep1 = D4 / "results" / "sobol"
    for sweep in (sweep3, sweep1):
        if (sweep / "sobol_mean_metrics.parquet").exists():
            return sweep
    return sweep3


def sobol_paths() -> dict[str, Path]:
    root = resolve_sobol_dir()
    return {
        "root": root,
        "sobol_mean_metrics": root / "sobol_mean_metrics.parquet",
        "sobol_indices": root / "sobol_indices.parquet",
        "sobol_S2": root / "sobol_S2.parquet",
        "sobol_design": root / "sobol_design.json",
        "generation_log": root / "synthetic_flows" / "generation_log.csv",
    }


def add_asymmetry_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Add obligation-weighted asymmetry from party reliability columns."""
    out = df.copy()
    parties = list(OBLIGATION_WEIGHTS.keys())
    rel_cols = [PARTY_RELIABILITY[p] for p in parties]
    if not all(c in out.columns for c in rel_cols):
        return out

    w = np.array([OBLIGATION_WEIGHTS[p] for p in parties])
    r = out[rel_cols].to_numpy(dtype=float)
    r_bar = (r * w).sum(axis=1, keepdims=True)
    out["asym_reliability_obligation"] = np.nansum(
        w * np.abs(r - r_bar), axis=1
    )
    out["party_vulnerability_gap"] = np.nanmax(r, axis=1) - np.nanmin(r, axis=1)
    return out


def compute_sobol_for_metric(
    problem: dict,
    y: np.ndarray,
    metric_name: str,
    calc_second_order: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run SALib Sobol for one metric; return long-format S1/ST and S2 frames."""
    from SALib.analyze import sobol as sobol_analyze

    y = y.astype(float)
    if np.nanvar(y) < 1e-12:
        return pd.DataFrame(), pd.DataFrame()

    y = np.where(np.isnan(y), np.nanmean(y), y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        si = sobol_analyze.analyze(
            problem, y,
            calc_second_order=calc_second_order,
            conf_level=0.95,
            print_to_console=False,
            seed=42,
        )

    params = problem["names"]
    si_rows = []
    for i, p in enumerate(params):
        si_rows.append({
            "metric": metric_name,
            "parameter": p,
            "S1": float(si["S1"][i]),
            "ST": float(si["ST"][i]),
            "S1_conf": float(si["S1_conf"][i]),
            "ST_conf": float(si["ST_conf"][i]),
        })
    si_df = pd.DataFrame(si_rows)

    s2_rows = []
    if calc_second_order and "S2" in si:
        for i in range(len(params)):
            for j in range(i + 1, len(params)):
                s2_rows.append({
                    "metric": metric_name,
                    "param_i": params[i],
                    "param_j": params[j],
                    "S2": float(si["S2"][i, j]),
                    "S2_conf": float(si["S2_conf"][i, j]),
                })
    return si_df, pd.DataFrame(s2_rows)


def ensure_asymmetry_indices(
    idx: pd.DataFrame,
    s2: pd.DataFrame,
    mean_df: pd.DataFrame,
    metrics: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append Sobol indices for asymmetry metrics if missing from parquet."""
    metrics = metrics or ["asym_reliability_obligation", "party_vulnerability_gap"]
    mean_df = add_asymmetry_columns(mean_df)

    sp = sobol_paths()
    with open(sp["sobol_design"]) as f:
        problem = json.load(f)

    idx = idx.copy()
    s2 = s2.copy() if s2 is not None else pd.DataFrame()

    for metric in metrics:
        if metric not in mean_df.columns:
            continue
        if metric in idx.get("metric", pd.Series(dtype=str)).values:
            continue
        si_df, s2_df = compute_sobol_for_metric(problem, mean_df[metric].values, metric)
        if not si_df.empty:
            idx = pd.concat([idx, si_df], ignore_index=True)
        if not s2_df.empty:
            s2 = pd.concat([s2, s2_df], ignore_index=True)
    return idx, s2


def load_member_regime_trace(member_id: int, baseline_dir: Path | None = None) -> dict:
    """
    Load daily IERQ balance, LB storage fraction, and regime labels for one member.
    """
    import h5py
    from D4_distributed_risk.lib.rrv_metrics.metrics import reconstruct_ierq_balance

    base = baseline_dir or PATHS["rrv_summary"].parent
    mdir = base / f"member_{member_id:04d}"
    hdf = next(mdir.glob("*.hdf5"))

    with h5py.File(hdf, "r") as f:
        ierq_release = f["nyc_mrf_trenton_step1"][:].ravel()
        betz = f["reservoir_beltzvilleCombined"][:].ravel()
        bm = f["reservoir_blueMarsh"][:].ravel()

    dates = pd.date_range("1945-01-01", periods=len(ierq_release), freq="D")
    release = pd.Series(ierq_release, index=dates)
    ierq_balance = reconstruct_ierq_balance(release, bank_max_mg=IERQ_MAX_MG)

    betz_s = pd.Series(betz, index=dates).clip(upper=BETZ_CAP_MG)
    bm_s = pd.Series(bm, index=dates).clip(upper=BM_CAP_MG)
    lb_storage = (betz_s + bm_s).clip(lower=0.0, upper=LB_CAPACITY_MG)
    lb_frac = lb_storage / LB_CAPACITY_MG

    ierq_ex = (ierq_balance <= IERQ_EXHAUSTION_MG).astype(int)
    lb_dep = (lb_storage <= LB_CAPACITY_MG * LB_CONSERVATION_FRAC).astype(int)
    labels = pd.Series(0, index=dates, dtype=int)
    labels[(ierq_ex == 1) & (lb_dep == 0)] = 1
    labels[(ierq_ex == 0) & (lb_dep == 1)] = 2
    labels[(ierq_ex == 1) & (lb_dep == 1)] = 3

    return {
        "member_id": member_id,
        "dates": dates,
        "ierq_balance": ierq_balance,
        "ierq_frac": ierq_balance / IERQ_MAX_MG,
        "lb_frac": lb_frac,
        "labels": labels,
        "ierq_min_frac": float((ierq_balance / IERQ_MAX_MG).min()),
        "lb_min_frac": float(lb_frac.min()),
    }


def select_regime_archetypes(df: pd.DataFrame, n_background: int = 80) -> dict:
    """Pick highlighted members and a background sample for regime trace atlas."""
    rng = np.random.default_rng(42)
    all_ids = df["realization_id"].astype(int).values

    nyc_id = int(df.loc[df["regime_frac_nyc_limited"].idxmax(), "realization_id"])
    lb_id = int(df.loc[df["regime_frac_lb_limited"].idxmax(), "realization_id"])
    switch_id = int(df.loc[df["regime_n_transitions"].idxmax(), "realization_id"])
    co_id = int(df.loc[(df["regime_frac_co_limited"] - 0.60).abs().idxmin(), "realization_id"])

    # Near phase boundary: high transitions but not the max-switching outlier
    boundary_pool = df.nlargest(20, "regime_n_transitions")
    boundary_id = int(boundary_pool.iloc[3]["realization_id"])

    highlights = {
        "NYC-limited (diversion)": nyc_id,
        "LB-limited (storage)": lb_id,
        "Co-limited": co_id,
        "Near-boundary / switching": switch_id,
        "High-transition boundary": boundary_id,
    }

    highlight_ids = set(highlights.values())
    bg_pool = [i for i in all_ids if i not in highlight_ids]
    bg_ids = rng.choice(bg_pool, size=min(n_background, len(bg_pool)), replace=False)
    return {"highlights": highlights, "background": sorted(int(i) for i in bg_ids)}

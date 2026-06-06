"""
Per-party RRV metrics for D4 — Distributed Risk Characterization (DRC).

Implements Hashimoto et al. (1982) Reliability–Resiliency–Vulnerability (RRV)
for each of the five 1954 Decree parties, given Pywr-DRB simulation outputs.

Party → metric mapping
----------------------
DE  (Delaware)        : Trenton flow reliability, resiliency, vulnerability
NYC (New York City)   : IERQ exhaustion days, diversion reliability
PA  (Pennsylvania)    : LB conservation pool depletion days, min storage fraction
NJ  (New Jersey)      : NJ delivery restriction days (below 70/65 MGD cap during LB drought)
NY  (New York State)  : Montague flow reliability, resiliency

Source
------
Hashimoto, T., Stedinger, J.R., Loucks, D.P. (1982). Reliability, Resiliency, and
Vulnerability Criteria for Water Resource System Performance Evaluation.
Water Resources Research, 18(1), 14–20.

1954 Decree party obligations: decree_party_node_mapping.md
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

# ---------------------------------------------------------------------------
# Thresholds — confirmed from pywrdrb source + Water Code / Decree
# ---------------------------------------------------------------------------

# Trenton/Montague MRF baseline values — from pywrdrb constants.csv
# (model computes dynamic target = baseline × drought_factor(level, month))
# Under Level 1a (normal) the factor is ~1.0 so these equal the daily target.
# For D4 analysis, prefer comparing against the model's own mrf_target_delTrenton
# time series (results_set="mrf_targets") rather than this fixed constant.
TRENTON_MRF_BASELINE_MGD: float = 1_938.95    # mrf_baseline_delTrenton (constants.csv)
MONTAGUE_MRF_BASELINE_MGD: float = 1_131.05   # mrf_baseline_delMontague (constants.csv)

# D1 SLR-elevated TFO — placeholder until DRBC 2025-6 confirmed
# This constant is only relevant for D1 scenario analysis; set per-cell in run_failure_surface_sweep.py
TRENTON_TFO_MGD: float = TRENTON_MRF_BASELINE_MGD   # use baseline as default
MONTAGUE_TFO_MGD: float = MONTAGUE_MRF_BASELINE_MGD

IERQ_EXHAUSTION_MG: float = 500.0      # from attribution.py — consistent; near-zero threshold
NJ_NORMAL_CAP_MGD: float = 100.0       # §2.5.6.B.1
NJ_WARNING_CAP_MGD: float = 70.0       # §2.5.6.C.1
NJ_DROUGHT_CAP_MGD: float = 65.0       # §2.5.6.D.1

# LB reservoir DRBC usable capacities (from ffmp.py docstring):
#   Beltzville:  13 500 MG  (73.7% warning threshold = 9 949.5 MG)
#   Blue Marsh:   7 450 MG  (68.9% warning threshold = 5 132.1 MG)
#   Combined:    20 950 MG  (combined warning pool  = 15 081.6 MG → 72.0%)
LB_BELTZVILLE_CAPACITY_MG: float  = 13_500.0
LB_BLUEMARSH_CAPACITY_MG: float   =  7_450.0
LB_BELTZVILLE_WARNING_FRAC: float =  0.737   # §2.5.6.C Water Code
LB_BLUEMARSH_WARNING_FRAC: float  =  0.689   # §2.5.6.C Water Code
# Combined warning pool as fraction of total — used when treating LB as one system
LB_CONSERVATION_FRAC: float = (
    LB_BELTZVILLE_CAPACITY_MG * LB_BELTZVILLE_WARNING_FRAC
    + LB_BLUEMARSH_CAPACITY_MG * LB_BLUEMARSH_WARNING_FRAC
) / (LB_BELTZVILLE_CAPACITY_MG + LB_BLUEMARSH_CAPACITY_MG)  # ≈ 0.720


# IERQ trenton bank maximum (MG) — matches max_bank_volumes["trenton"] in banks.py
IERQ_TRENTON_MAX_MG: float = 6_090.0

# ERQ constants — 1954 Decree Art. III-B-1(c)-(d)
ERQ_SEASONAL_DAYS: int    = 120       # "designed to release the entire quantity in 120 days"
ERQ_CAP_MG: float         = 70_000.0  # "shall in no event exceed 70 billion gallons"
ERQ_SEASON_START: tuple   = (6, 15)   # "commencing with the fifteenth day of June"
ERQ_SEASON_END: tuple     = (3, 15)   # "not later than the following March 15"

# ---------------------------------------------------------------------------
# IERQ balance reconstruction
# ---------------------------------------------------------------------------

def reconstruct_ierq_balance(
    ierq_release_series: pd.Series,
    bank_max_mg: float = IERQ_TRENTON_MAX_MG,
) -> pd.Series:
    """
    Reconstruct IERQ bank balance from recorded daily release amounts.

    IERQRelease_step1 records the daily release (MG drawn down), not the balance.
    The balance before each day's release is recovered by cumulative subtraction,
    with reset to bank_max on May 31 (matching banks.py after() logic).

    Returns a Series aligned with ierq_release_series.index.
    Returns an empty float Series if input is empty.
    """
    if len(ierq_release_series) == 0:
        return pd.Series(dtype=float)

    balance = pd.Series(index=ierq_release_series.index, dtype=float)
    current = bank_max_mg
    for date, release in ierq_release_series.items():
        balance[date] = current
        current = max(0.0, current - release)
        if hasattr(date, "month") and date.month == 5 and date.day == 31:
            current = bank_max_mg
    return balance


# ---------------------------------------------------------------------------
# RRV core functions
# ---------------------------------------------------------------------------

def _reliability(series: pd.Series, threshold: float, above: bool = True) -> float:
    """Fraction of days meeting the threshold."""
    meets = (series >= threshold) if above else (series <= threshold)
    return float(meets.mean())


def _resiliency(series: pd.Series, threshold: float, above: bool = True) -> float:
    """
    Probability of recovering to satisfactory state in the next timestep
    given current unsatisfactory state.  Defined as: P(s_t satisfactory | s_{t-1} unsatisfactory).

    Note: uses .values for the shift operation to avoid pandas DatetimeIndex alignment
    issues where unsatisfactory[:-1] and meets[1:] have different index ranges.
    """
    meets = (series >= threshold) if above else (series <= threshold)
    unsat_arr = (~meets).values
    if not unsat_arr.any():
        return 1.0  # never failed
    meets_arr = meets.values
    # Transition: unsatisfactory at t → satisfactory at t+1
    transitions = unsat_arr[:-1] & meets_arr[1:]
    n_unsat = unsat_arr[:-1].sum()
    if n_unsat == 0:
        return 1.0
    return float(transitions.sum() / n_unsat)


def _vulnerability(series: pd.Series, threshold: float, above: bool = True) -> float:
    """
    Expected magnitude of worst failure event (single largest deficit per episode).
    Normalized by threshold so result is a fraction.
    """
    deficit = (threshold - series) if above else (series - threshold)
    deficit = deficit.clip(lower=0.0)
    if deficit.max() == 0:
        return 0.0
    return float(deficit.max() / threshold)


# ---------------------------------------------------------------------------
# Party-specific metric functions
# ---------------------------------------------------------------------------

def de_metrics(trenton_flow: pd.Series, tfo_mgd: float = TRENTON_TFO_MGD) -> dict:
    """Delaware: Trenton flow reliability, resiliency, vulnerability."""
    return {
        "de_reliability":  _reliability(trenton_flow,  tfo_mgd),
        "de_resiliency":   _resiliency(trenton_flow,   tfo_mgd),
        "de_vulnerability": _vulnerability(trenton_flow, tfo_mgd),
        "de_shortfall_days": int((trenton_flow < tfo_mgd).sum()),
        "de_max_deficit_mgd": float(max(0.0, (tfo_mgd - trenton_flow).max())),
    }


def nyc_metrics(
    ierq_balance: pd.Series,
    exhaustion_threshold_mg: float = IERQ_EXHAUSTION_MG,
) -> dict:
    """NYC: IERQ exhaustion days and exhaustion reliability."""
    exhausted = ierq_balance <= exhaustion_threshold_mg
    n = len(ierq_balance)
    return {
        "nyc_ierq_exhaustion_days": int(exhausted.sum()),
        "nyc_ierq_exhaustion_reliability": float(1.0 - exhausted.mean()),
        "nyc_min_ierq_balance_mg": float(ierq_balance.min()),
    }


def pa_metrics(
    lb_storage: pd.Series,
    lb_capacity_mg: float,
    conservation_frac: float = LB_CONSERVATION_FRAC,
    alpha_betz: Optional[float] = None,
    alpha_bm: Optional[float] = None,
) -> dict:
    """PA: LB conservation pool depletion days and minimum storage fraction.

    When alpha_betz and alpha_bm are provided (Sobol sensitivity runs), the
    depletion threshold is recomputed from the injected warning fractions so
    the metric threshold matches the model's switching threshold exactly.
    """
    if alpha_betz is not None and alpha_bm is not None:
        lb_threshold = (
            alpha_betz * LB_BELTZVILLE_CAPACITY_MG
            + alpha_bm  * LB_BLUEMARSH_CAPACITY_MG
        )
    else:
        lb_threshold = lb_capacity_mg * conservation_frac
    # Clip to [0, lb_capacity_mg] — raw HDF5 recorder includes storage below the
    # DRBC usable floor (inactive pool) and above capacity (flood pool), so the
    # raw values are not bounded by the usable capacity range used in the model.
    lb_storage_usable = lb_storage.clip(lower=0.0, upper=lb_capacity_mg)
    below = lb_storage_usable < lb_threshold
    return {
        "pa_depletion_days":        int(below.sum()),
        "pa_depletion_reliability": float(1.0 - below.mean()),
        "pa_min_storage_frac":      float(lb_storage_usable.min() / lb_capacity_mg),
        "pa_depletion_resiliency":  _resiliency(lb_storage_usable, lb_threshold),
    }


def nj_metrics(
    nj_delivery: pd.Series,
    lb_drought_stage: pd.Series,
    normal_cap_mgd: float = NJ_NORMAL_CAP_MGD,
    warning_cap_mgd: float = NJ_WARNING_CAP_MGD,
    drought_cap_mgd: float = NJ_DROUGHT_CAP_MGD,
) -> dict:
    """
    NJ: delivery restriction days.

    Counts days where effective NJ cap (based on LB drought stage) is below the
    normal 100 MGD cap — i.e., days when LB drought is actively restricting NJ.

    Also counts days where actual delivery falls below the applicable stage cap.
    """
    # Applicable cap per day based on LB drought stage.
    # Reindex lb_drought_stage to match nj_delivery's index (handles empty Series
    # from pre-run data where LB switching wasn't recorded, or index mismatches).
    cap_per_day = pd.Series(normal_cap_mgd, index=nj_delivery.index)
    if len(lb_drought_stage) > 0:
        stage_aligned = lb_drought_stage.reindex(nj_delivery.index, fill_value=0)
        cap_per_day[stage_aligned == 1] = warning_cap_mgd
        cap_per_day[stage_aligned == 2] = drought_cap_mgd

    lb_restriction_days = int((cap_per_day < normal_cap_mgd).sum())
    shortfall_days = int((nj_delivery < cap_per_day).sum())

    return {
        "nj_lb_restriction_days":   lb_restriction_days,
        "nj_shortfall_days":        shortfall_days,
        "nj_delivery_reliability":  _reliability(nj_delivery, normal_cap_mgd),
        "nj_mean_delivery_mgd":     float(nj_delivery.mean()),
    }


def ny_metrics(
    montague_flow: pd.Series,
    montague_tfo_mgd: float = MONTAGUE_TFO_MGD,
) -> dict:
    """NY: Montague flow reliability and resiliency."""
    return {
        "ny_reliability":  _reliability(montague_flow,  montague_tfo_mgd),
        "ny_resiliency":   _resiliency(montague_flow,   montague_tfo_mgd),
        "ny_vulnerability": _vulnerability(montague_flow, montague_tfo_mgd),
        "ny_shortfall_days": int((montague_flow < montague_tfo_mgd).sum()),
    }


def erq_metrics(
    erq_release: pd.Series,
    erq_cap_mg: float = ERQ_CAP_MG,
    seasonal_days: int = ERQ_SEASONAL_DAYS,
) -> dict:
    """
    DE downstream benefit from NYC's annual ERQ cooperative release obligation.

    1954 Decree Art. III-B-1(c)-(d):
        "The City shall release ... a quantity of water equal to 83 per cent
        of the amount by which the estimated consumption during such year is
        less than the City's estimate of the continuous safe yield ...
        Commencing with the fifteenth day of June each year, the excess releases
        shall continue ... not later than the following March 15.
        The excess quantity ... shall in no event exceed 70 billion gallons."

    Parameters
    ----------
    erq_release : pd.Series
        Daily ERQ release from all NYC reservoirs combined (MGD).
        Recorder: OUTPUT_VARS["erq_release_nyc"] = "erq_release_nyc".
        Zero outside the June 15 – March 15 seasonal period.
    erq_cap_mg : float
        Annual ERQ cap (70,000 MG baseline).  Sobol parameter erq_cap_mg
        varies this; injected into ERQRelease via sensitivity_params.
    seasonal_days : int
        Decree target release schedule: 120 days.

    Returns
    -------
    dict with keys:
        erq_annual_release_mg : float
            Mean annual ERQ release (MG/year), averaged over decree years
            (June 1 – May 31).  Equals erq_cap_mg when bank is fully exhausted
            every season; less in drought years when reservoirs can't supply.
        erq_seasonal_exhaustion_rate : float
            Fraction of seasonal periods where the annual ERQ was fully
            released (bank exhausted).  1.0 = NYC met its full obligation
            every year; <1.0 = some years fell short.
        erq_days_released : int
            Total days with positive ERQ release across the simulation.
    """
    if len(erq_release) == 0 or erq_release.isna().all():
        return {
            "erq_annual_release_mg":          np.nan,
            "erq_seasonal_exhaustion_rate":   np.nan,
            "erq_days_released":              np.nan,
        }

    # Days with any ERQ release
    erq_days = int((erq_release > 0.01).sum())

    # Annual ERQ: sum by decree year (June 1 – May 31)
    # resample("YS-JUN") starts each period on June 1
    # Each daily value is MGD; since timestep = 1 day, sum = MG
    annual_mg = erq_release.resample("YS-JUN").sum()

    erq_annual_mean = float(annual_mg.mean()) if len(annual_mg) > 0 else np.nan

    # Seasonal exhaustion: fraction of years where ≥95% of cap was released
    # (95% threshold accounts for final-day rounding in ERQRelease.value())
    exhaustion_threshold = 0.95 * erq_cap_mg
    n_seasons  = len(annual_mg)
    n_exhausted = int((annual_mg >= exhaustion_threshold).sum())
    exhaustion_rate = float(n_exhausted / n_seasons) if n_seasons > 0 else np.nan

    return {
        "erq_annual_release_mg":        erq_annual_mean,
        "erq_seasonal_exhaustion_rate": exhaustion_rate,
        "erq_days_released":            erq_days,
    }


# ---------------------------------------------------------------------------
# Full five-party RRV for one simulation member
# ---------------------------------------------------------------------------

def compute_all_party_rrv(
    outputs: dict[str, pd.Series],
    lb_capacity_mg: float = 20_950.0,
    tfo_mgd: float = TRENTON_TFO_MGD,
    montague_tfo_mgd: float = MONTAGUE_TFO_MGD,
    alpha_betz: Optional[float] = None,
    alpha_bm: Optional[float] = None,
    erq_cap_mg: Optional[float] = None,
) -> dict:
    """
    Compute all five-party RRV metrics from a single Pywr-DRB simulation output dict.

    Parameters
    ----------
    outputs : dict[str, pd.Series]
        Keys matching OUTPUT_VARS in shared/pywrdrb_utils/run_model.py.
    lb_capacity_mg : float
        Total LB usable storage (Beltzville + Blue Marsh combined).
    tfo_mgd : float
        Trenton Flow Objective (MGD) for this scenario.
    montague_tfo_mgd : float
        Montague flow objective (MGD).
    alpha_betz : float or None
        Injected Beltzville warning fraction (Sobol sensitivity runs only).
        When provided together with alpha_bm, pa_metrics uses the injected
        threshold so model switching and metric counting are consistent.
    alpha_bm : float or None
        Injected Blue Marsh warning fraction (Sobol sensitivity runs only).
    erq_cap_mg : float or None
        Injected ERQ annual cap (MG) for Sobol sweep 2 runs.
        When None, uses the Decree default (70,000 MG).

    Returns
    -------
    dict
        Flat dict of all per-party metrics, ready to become one row in results DataFrame.
    """
    # Clip each reservoir to its DRBC usable capacity before summing.
    # Raw HDF5 values include flood-control storage above the usable pool
    # (notably Blue Marsh reaches 34,018 MG vs 7,450 MG DRBC usable).
    lb_betz = outputs.get("beltzville_volume", pd.Series(dtype=float)).clip(upper=LB_BELTZVILLE_CAPACITY_MG)
    lb_bm   = outputs.get("blueMarsh_volume",   pd.Series(dtype=float)).clip(upper=LB_BLUEMARSH_CAPACITY_MG)
    lb_storage = lb_betz + lb_bm

    # IERQRelease_step1 records daily release (not balance); reconstruct balance.
    ierq_release = outputs.get("ierq_bank_remaining", pd.Series(dtype=float))
    ierq_balance = reconstruct_ierq_balance(ierq_release)

    metrics = {}
    metrics.update(de_metrics(outputs.get("del_trenton_flow", pd.Series(dtype=float)), tfo_mgd))
    metrics.update(nyc_metrics(ierq_balance))
    metrics.update(pa_metrics(lb_storage, lb_capacity_mg, alpha_betz=alpha_betz, alpha_bm=alpha_bm))
    metrics.update(nj_metrics(
        outputs.get("nj_delivery",     pd.Series(dtype=float)),
        outputs.get("lb_drought_stage", pd.Series(dtype=float)),
    ))
    metrics.update(ny_metrics(
        outputs.get("del_montague_flow", pd.Series(dtype=float)),
        montague_tfo_mgd,
    ))
    # ERQ — DE downstream benefit from NYC's cooperative Decree obligation.
    # erq_release_nyc is only present in runs using pywrdrb with ERQRelease wired
    # (post-2026-06-02).  Returns NaN gracefully for pre-ERQ runs.
    erq_kw = {} if erq_cap_mg is None else {"erq_cap_mg": erq_cap_mg}
    metrics.update(erq_metrics(
        outputs.get("erq_release_nyc", pd.Series(dtype=float)),
        **erq_kw,
    ))

    # Regime attribution — daily labels and aggregated statistics
    metrics.update(regime_metrics(ierq_balance, lb_storage, lb_capacity_mg))

    # Regime-conditioned RRV — compute only on days within each regime
    # Build daily labels from the same ierq/lb series
    lb_threshold = lb_capacity_mg * LB_CONSERVATION_FRAC
    ierq_ex = (ierq_balance <= IERQ_EXHAUSTION_MG).astype(int)
    lb_dep  = (lb_storage.clip(upper=lb_capacity_mg) <= lb_threshold).astype(int)
    regime_labels = pd.Series(0, index=ierq_balance.index, dtype=int)
    regime_labels[(ierq_ex == 1) & (lb_dep == 0)] = 1
    regime_labels[(ierq_ex == 0) & (lb_dep == 1)] = 2
    regime_labels[(ierq_ex == 1) & (lb_dep == 1)] = 3
    metrics.update(regime_conditioned_rrv(outputs, regime_labels, lb_capacity_mg,
                                          tfo_mgd, montague_tfo_mgd))

    # Asymmetry metrics — three weight schemes, reliability focus
    metrics.update(asymmetry_metrics(metrics))

    return metrics


# ---------------------------------------------------------------------------
# Obligation weights — three defensible weight schemes
# ---------------------------------------------------------------------------
#
# Weight scheme rationale (all normalised to sum=1):
#
# EQUAL: five parties treated as co-equal stakeholders.  Most conservative;
#   hardest for reviewers to attack.  Use as primary.
#
# OBLIGATION_PROPORTIONAL: weights reflect the size of each party's legally
#   mandated obligation under the 1954 Decree / FFMP:
#   DE  0.28  Trenton TFO 1,750 MGD is the primary basin-wide obligation
#   NYC 0.25  IERQ 6.09 BG/yr + ERQ; largest single augmentation obligation
#   PA  0.20  LB conservation pool support; dual-mandate storage constraint
#   NJ  0.15  Diversion cap exposure; 100→70→65 MGD step-downs during drought
#   NY  0.12  Montague TFO 1,535 MGD; upstream flow obligation
#   Source: 1954 Decree Art. III–VII; FFMP §2.c.i; Water Code §2.5.6
#   NOTE: These are Marilyn's best-estimate weights pending committee sign-off.
#         Conduct weight sensitivity before publication.
#
# EXPOSURE_PROPORTIONAL: weights reflect each party's fractional exposure to
#   shortfall — i.e., how much of their metric variance is explained by
#   institutional parameters in the Sobol analysis.  Populated after sweep 3.
#   Default: equal until empirical weights are available.
#
# ---------------------------------------------------------------------------

WEIGHTS_EQUAL: dict[str, float] = {
    "DE": 0.20, "NYC": 0.20, "PA": 0.20, "NJ": 0.20, "NY": 0.20,
}

WEIGHTS_OBLIGATION: dict[str, float] = {
    "DE":  0.28,
    "NYC": 0.25,
    "PA":  0.20,
    "NJ":  0.15,
    "NY":  0.12,
}

# Placeholder — replace with empirical ST fractions after sweep 3
WEIGHTS_EXPOSURE: dict[str, float] = WEIGHTS_EQUAL

# Default used in compute_all_party_rrv — equal weights for reproducibility
OBLIGATION_WEIGHTS: dict[str, float] = WEIGHTS_EQUAL

REGIME_LABELS: dict[int, str] = {
    0: "normal",
    1: "NYC-limited",
    2: "LB-limited",
    3: "co-limited",
}

# Minimum days a regime must be active to compute regime-conditioned RRV.
# Below this threshold, RRV estimates are statistically unreliable.
REGIME_MIN_DAYS: int = 30

# Map party codes to their primary reliability metric key
_PARTY_RELIABILITY_KEYS: dict[str, str] = {
    "DE":  "de_reliability",
    "NYC": "nyc_ierq_exhaustion_reliability",
    "PA":  "pa_depletion_reliability",
    "NJ":  "nj_delivery_reliability",
    "NY":  "ny_reliability",
}
_PARTY_RESILIENCE_KEYS: dict[str, str] = {
    "DE":  "de_resiliency",
    "NYC": "nyc_ierq_exhaustion_reliability",   # no separate resiliency; use reliability
    "PA":  "pa_depletion_resiliency",
    "NJ":  "nj_delivery_reliability",           # no separate resiliency
    "NY":  "ny_resiliency",
}
_PARTY_VULNERABILITY_KEYS: dict[str, str] = {
    "DE":  "de_vulnerability",
    "NYC": "nyc_min_ierq_balance_mg",           # inverted: lower = worse
    "PA":  "pa_min_storage_frac",               # inverted: lower = worse
    "NJ":  "nj_lb_restriction_days",            # higher = worse
    "NY":  "ny_vulnerability",
}


# ---------------------------------------------------------------------------
# Regime metrics — comprehensive
# ---------------------------------------------------------------------------

def regime_metrics(
    ierq_balance: pd.Series,
    lb_storage: pd.Series,
    lb_capacity_mg: float = 20_950.0,
    ierq_threshold_mg: float = IERQ_EXHAUSTION_MG,
    lb_conservation_frac: float = LB_CONSERVATION_FRAC,
    min_days: int = REGIME_MIN_DAYS,
) -> dict:
    """
    Compute daily regime labels and aggregate regime statistics.

    Regime labels
    -------------
    0 = normal       (neither IERQ exhausted nor LB depleted)
    1 = NYC-limited  (IERQ exhausted, LB above conservation pool)
    2 = LB-limited   (LB depleted, IERQ still has balance)
    3 = co-limited   (both simultaneously)

    Returns
    -------
    dict with:
      n_days_regime_{normal,nyc,lb,co}   — count of days in each regime
      regime_frac_{normal,nyc,lb,co}     — fraction of simulation days
      regime_first                        — label of first non-normal regime (0=none)
      regime_n_transitions                — number of regime changes
      regime_n_episodes_{nyc,lb,co}       — discrete episodes per regime
      regime_mean_persist_{nyc,lb,co}     — mean consecutive days per episode
      regime_max_persist_{nyc,lb,co}      — longest single episode (days)
      regime_nyc_before_lb                — 1 if NYC-limited precedes LB-limited
    """
    empty = {
        "n_days_regime_normal": np.nan, "n_days_regime_nyc": np.nan,
        "n_days_regime_lb": np.nan,     "n_days_regime_co": np.nan,
        "regime_frac_normal": np.nan,   "regime_frac_nyc_limited": np.nan,
        "regime_frac_lb_limited": np.nan, "regime_frac_co_limited": np.nan,
        "regime_first": np.nan,          "regime_n_transitions": np.nan,
        "regime_n_episodes_nyc": np.nan, "regime_n_episodes_lb": np.nan,
        "regime_n_episodes_co": np.nan,
        "regime_mean_persist_nyc": np.nan, "regime_mean_persist_lb": np.nan,
        "regime_mean_persist_co": np.nan,
        "regime_max_persist_nyc": np.nan,  "regime_max_persist_lb": np.nan,
        "regime_max_persist_co": np.nan,
        "regime_nyc_before_lb": np.nan,
    }
    if len(ierq_balance) == 0 or len(lb_storage) == 0:
        return empty

    lb_threshold = lb_capacity_mg * lb_conservation_frac
    ierq_ex = (ierq_balance <= ierq_threshold_mg).astype(int)
    lb_dep  = (lb_storage.clip(upper=lb_capacity_mg) <= lb_threshold).astype(int)

    labels = pd.Series(0, index=ierq_balance.index, dtype=int)
    labels[(ierq_ex == 1) & (lb_dep == 0)] = 1   # NYC-limited
    labels[(ierq_ex == 0) & (lb_dep == 1)] = 2   # LB-limited
    labels[(ierq_ex == 1) & (lb_dep == 1)] = 3   # co-limited

    n = len(labels)
    n_normal = int((labels == 0).sum())
    n_nyc    = int((labels == 1).sum())
    n_lb     = int((labels == 2).sum())
    n_co     = int((labels == 3).sum())

    out = {
        "n_days_regime_normal": n_normal,
        "n_days_regime_nyc":    n_nyc,
        "n_days_regime_lb":     n_lb,
        "n_days_regime_co":     n_co,
        "regime_frac_normal":       float(n_normal / n),
        "regime_frac_nyc_limited":  float(n_nyc / n),
        "regime_frac_lb_limited":   float(n_lb / n),
        "regime_frac_co_limited":   float(n_co / n),
    }

    # Sanity check: fractions should sum to 1
    assert abs(sum([out["regime_frac_normal"], out["regime_frac_nyc_limited"],
                    out["regime_frac_lb_limited"], out["regime_frac_co_limited"]]) - 1.0) < 1e-6, \
        "Regime fractions do not sum to 1"

    # First non-normal regime
    non_normal = labels[labels > 0]
    out["regime_first"] = int(non_normal.iloc[0]) if len(non_normal) > 0 else 0

    # Number of regime transitions (label changes)
    out["regime_n_transitions"] = int((labels.values[1:] != labels.values[:-1]).sum())

    # Episode statistics per regime
    for reg_val, reg_name in [(1, "nyc"), (2, "lb"), (3, "co")]:
        ep = _episode_stats(labels == reg_val)
        out[f"regime_n_episodes_{reg_name}"]   = ep["n_episodes"]
        out[f"regime_mean_persist_{reg_name}"] = ep["mean_length"]
        out[f"regime_max_persist_{reg_name}"]  = ep["max_length"]

    # Sequencing: did NYC-limited precede LB-limited?
    t_nyc = _first_occurrence(labels, 1)
    t_lb  = _first_occurrence(labels, 2)
    if t_nyc is None and t_lb is None:
        out["regime_nyc_before_lb"] = np.nan
    elif t_nyc is None:
        out["regime_nyc_before_lb"] = 0
    elif t_lb is None:
        out["regime_nyc_before_lb"] = 1
    else:
        out["regime_nyc_before_lb"] = int(t_nyc < t_lb)

    return out


def regime_conditioned_rrv(
    outputs: dict[str, pd.Series],
    labels: pd.Series,
    lb_capacity_mg: float = 20_950.0,
    tfo_mgd: float = TRENTON_TFO_MGD,
    montague_tfo_mgd: float = MONTAGUE_TFO_MGD,
    min_days: int = REGIME_MIN_DAYS,
) -> dict:
    """
    Compute regime-conditioned DE and NYC RRV — i.e., RRV computed only on
    days where each regime is active.

    Only computed when n_days >= min_days; otherwise returns NaN.
    This prevents statistically unreliable estimates from sparse regimes.

    Returns flat dict with keys like:
        rcrrv_nyc_de_reliability   — DE reliability conditioned on NYC-limited days
        rcrrv_lb_pa_depletion_reliability  — PA reliability conditioned on LB-limited days
    """
    out = {}
    trenton = outputs.get("del_trenton_flow", pd.Series(dtype=float))
    montague = outputs.get("del_montague_flow", pd.Series(dtype=float))

    for regime_val, regime_name in [(1, "nyc"), (2, "lb"), (3, "co")]:
        mask = (labels == regime_val)
        n_days = int(mask.sum())
        out[f"rcrrv_{regime_name}_n_days"] = n_days

        if n_days < min_days:
            # Not enough days — NaN for all conditioned metrics
            out[f"rcrrv_{regime_name}_de_reliability"]  = np.nan
            out[f"rcrrv_{regime_name}_ny_reliability"]  = np.nan
            continue

        # DE reliability conditioned on this regime
        if len(trenton) > 0:
            sub = trenton[mask.values[:len(trenton)]] if len(mask) >= len(trenton) \
                  else trenton[mask[:len(trenton)]]
            out[f"rcrrv_{regime_name}_de_reliability"] = float(
                _reliability(sub, tfo_mgd)) if len(sub) > 0 else np.nan
        else:
            out[f"rcrrv_{regime_name}_de_reliability"] = np.nan

        # NY reliability conditioned on this regime
        if len(montague) > 0:
            sub = montague[mask.values[:len(montague)]] if len(mask) >= len(montague) \
                  else montague[mask[:len(montague)]]
            out[f"rcrrv_{regime_name}_ny_reliability"] = float(
                _reliability(sub, montague_tfo_mgd)) if len(sub) > 0 else np.nan
        else:
            out[f"rcrrv_{regime_name}_ny_reliability"] = np.nan

    return out


def _first_occurrence(series: pd.Series, value) -> Optional[int]:
    """Integer position of first occurrence of value, or None."""
    idx = np.where(series == value)[0]
    return int(idx[0]) if len(idx) > 0 else None


def _episode_stats(bool_series: pd.Series) -> dict:
    """Count episodes and compute mean/max length of contiguous True runs."""
    arr = bool_series.values.astype(bool)
    if not arr.any():
        return {"n_episodes": 0, "mean_length": 0.0, "max_length": 0}
    padded = np.concatenate([[False], arr, [False]])
    diffs  = np.diff(padded.astype(int))
    lengths = np.where(diffs == -1)[0] - np.where(diffs == 1)[0]
    return {
        "n_episodes":  int(len(lengths)),
        "mean_length": float(lengths.mean()),
        "max_length":  int(lengths.max()),
    }


# ---------------------------------------------------------------------------
# Asymmetry metrics — three weight schemes, three RRV dimensions
# ---------------------------------------------------------------------------

def _asymmetry_A(vals: np.ndarray, w: np.ndarray) -> float:
    """
    Obligation-weighted mean absolute deviation from weighted mean.
    A = Σ_p w_p |M_p - M̄_w|   where M̄_w = Σ_p w_p M_p
    Returns 0 when all parties have identical metric values.
    """
    r_bar = float(np.dot(w, vals))
    return float(np.dot(w, np.abs(vals - r_bar)))


def _gini(vals: np.ndarray) -> float:
    """Gini coefficient of an array of values (0 = perfect equality)."""
    s = np.sort(vals)
    n = len(s)
    if s.sum() == 0:
        return 0.0
    return float((2 * np.dot(np.arange(1, n + 1), s) - (n + 1) * s.sum()) / (n * s.sum()))


def asymmetry_metrics(rrv_dict: dict) -> dict:
    """
    Compute obligation-weighted risk asymmetry for reliability, resilience,
    and vulnerability across five parties.

    Three weight schemes are computed for sensitivity:
      _equal        — 0.20 each (most defensible to reviewers)
      _obligation   — obligation-proportional (DE 0.28, NYC 0.25, PA 0.20, NJ 0.15, NY 0.12)
      _unweighted   — simple mean absolute deviation (no weights)

    Formula:  A_m = Σ_p w_p |M_p − M̄_w|
    where M̄_w = Σ_p w_p M_p  (obligation-weighted mean)

    Returns
    -------
    dict with keys:
      asym_reliability_{equal,obligation,unweighted}
      asym_gini_reliability
      asym_max_min_gap
      worst_party, best_party, r_bar_equal, r_bar_obligation
    """
    # --- Reliability values ---
    r_vals = {}
    for party, key in _PARTY_RELIABILITY_KEYS.items():
        v = rrv_dict.get(key, np.nan)
        r_vals[party] = float(v) if v is not None and not np.isnan(v) else np.nan

    parties = list(WEIGHTS_EQUAL.keys())
    r_arr = np.array([r_vals[p] for p in parties])
    w_eq  = np.array([WEIGHTS_EQUAL[p]      for p in parties])
    w_ob  = np.array([WEIGHTS_OBLIGATION[p] for p in parties])

    out = {}

    if np.any(np.isnan(r_arr)):
        for suffix in ["equal", "obligation", "unweighted"]:
            out[f"asym_reliability_{suffix}"] = np.nan
        out.update({
            "asym_gini_reliability": np.nan,
            "asym_max_min_gap": np.nan,
            "worst_party": "unknown",
            "best_party": "unknown",
            "r_bar_equal": np.nan,
            "r_bar_obligation": np.nan,
        })
        return out

    # Three reliability asymmetry versions
    out["asym_reliability_equal"]       = _asymmetry_A(r_arr, w_eq)
    out["asym_reliability_obligation"]  = _asymmetry_A(r_arr, w_ob)
    out["asym_reliability_unweighted"]  = float(np.mean(np.abs(r_arr - r_arr.mean())))
    out["asym_gini_reliability"]        = _gini(r_arr)
    out["asym_max_min_gap"]             = float(r_arr.max() - r_arr.min())
    out["worst_party"]                  = parties[int(np.argmin(r_arr))]
    out["best_party"]                   = parties[int(np.argmax(r_arr))]
    out["r_bar_equal"]                  = float(np.dot(w_eq, r_arr))
    out["r_bar_obligation"]             = float(np.dot(w_ob, r_arr))

    # Per-party deviation from obligation-weighted mean (for decomposition)
    r_bar_ob = out["r_bar_obligation"]
    for party, r in r_vals.items():
        w_p = WEIGHTS_OBLIGATION[party]
        out[f"asym_contrib_{party.lower()}"] = float(w_p * abs(r - r_bar_ob))

    return out

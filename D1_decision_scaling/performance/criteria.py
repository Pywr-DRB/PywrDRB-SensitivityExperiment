"""
D1 Step 2 — Performance criteria for Trenton flow objective failure.

A scenario cell fails when ANY of the three criteria is crossed.
Attribution distinguishes NYC-limited vs LB-limited failure mode.

Criteria (following Turner 2014, adapted for 5-party DRB governance):
  1. Trenton reliability    — shortfall frequency exceeds threshold
  2. Shortfall severity     — deficit magnitude × duration exceeds threshold
  3. LB storage depletion   — LB storage drops below conservation pool

Attribution:
  - NYC-limited: IERQ bank exhausted while LB storage still above conservation pool
  - LB-limited:  LB storage below conservation pool while IERQ bank > 0

Thresholds are configurable — defaults are placeholders pending committee input.

TODO (ask Scott):
    - Confirm reliability threshold (e.g. <95% days meeting TFO)
    - Confirm severity threshold definition (cumulative deficit? peak deficit?)
    - Confirm LB conservation pool fraction (DRBC Water Code §2.5.3)
    - Confirm IERQ exhaustion definition (bank balance < threshold or 0)
"""

import numpy as np
import pandas as pd

# =============================================================================
# THRESHOLDS — update with Scott's guidance
# =============================================================================

RELIABILITY_THRESHOLD = 0.95       # fraction of days meeting TFO (cell fails if < this)
SEVERITY_THRESHOLD_MG = 10_000     # cumulative shortfall in MG per season (placeholder)
LB_CONSERVATION_POOL_FRAC = 0.30   # fraction of LB capacity (placeholder — check Water Code §2.5.3)
IERQ_EXHAUSTION_THRESHOLD_MG = 500 # IERQ bank balance considered "exhausted" (placeholder)


# =============================================================================
# CRITERIA FUNCTIONS
# =============================================================================

def evaluate_trenton_reliability(trenton_flow: pd.Series, tfo_level: float) -> dict:
    """
    Criterion 1: fraction of days meeting TFO.

    Parameters
    ----------
    trenton_flow : pd.Series
        Daily Trenton gage flow (MGD), datetime index
    tfo_level : float
        Trenton Flow Objective (MGD) — varies with SLR scenario

    Returns
    -------
    dict with keys: reliability (float), fails (bool), shortfall_days (int)
    """
    meets = trenton_flow >= tfo_level
    reliability = meets.mean()
    return {
        "reliability": reliability,
        "fails": reliability < RELIABILITY_THRESHOLD,
        "shortfall_days": (~meets).sum(),
        "total_days": len(trenton_flow),
    }


def evaluate_shortfall_severity(trenton_flow: pd.Series, tfo_level: float) -> dict:
    """
    Criterion 2: cumulative shortfall severity.

    Parameters
    ----------
    trenton_flow : pd.Series
        Daily Trenton gage flow (MGD)
    tfo_level : float
        Trenton Flow Objective (MGD)

    Returns
    -------
    dict with keys: cumulative_deficit_mg (float), peak_daily_deficit_mgd (float), fails (bool)
    """
    deficit = np.maximum(tfo_level - trenton_flow, 0)
    cumulative = deficit.sum()
    return {
        "cumulative_deficit_mg": cumulative,
        "peak_daily_deficit_mgd": deficit.max(),
        "fails": cumulative > SEVERITY_THRESHOLD_MG,
    }


def evaluate_lb_storage(lb_storage: pd.Series, lb_capacity_mg: float) -> dict:
    """
    Criterion 3: LB storage depletion below conservation pool.

    Parameters
    ----------
    lb_storage : pd.Series
        Daily combined LB storage (Blue Marsh + Beltzville), MG, datetime index
    lb_capacity_mg : float
        Total LB capacity (MG) — used to compute fractional storage

    Returns
    -------
    dict with keys: min_fraction (float), days_below_conservation (int), fails (bool)
    """
    fraction = lb_storage / lb_capacity_mg
    below = fraction < LB_CONSERVATION_POOL_FRAC
    return {
        "min_storage_fraction": fraction.min(),
        "days_below_conservation": below.sum(),
        "fails": below.any(),
    }


# =============================================================================
# ATTRIBUTION
# =============================================================================

def attribute_failure_mode(
    ierq_balance: pd.Series,
    lb_storage: pd.Series,
    lb_capacity_mg: float,
) -> str:
    """
    Attribute failure to NYC-limited or LB-limited regime.

    NYC-limited: IERQ bank exhausted (balance ≤ threshold) while LB still above conservation pool.
    LB-limited:  LB storage below conservation pool while IERQ balance > threshold.
    Mixed:       Both constraints binding simultaneously.
    None:        Neither constraint fully binding (no failure or data issue).

    Parameters
    ----------
    ierq_balance : pd.Series
        Daily IERQ Trenton bank balance (MG)
    lb_storage : pd.Series
        Daily combined LB storage (MG)
    lb_capacity_mg : float
        Total LB capacity (MG)

    Returns
    -------
    str: "NYC-limited", "LB-limited", "mixed", or "none"
    """
    ierq_exhausted = ierq_balance <= IERQ_EXHAUSTION_THRESHOLD_MG
    lb_depleted = (lb_storage / lb_capacity_mg) < LB_CONSERVATION_POOL_FRAC

    both = (ierq_exhausted & lb_depleted).any()
    nyc_only = (ierq_exhausted & ~lb_depleted).any()
    lb_only = (~ierq_exhausted & lb_depleted).any()

    if both and (nyc_only or lb_only):
        return "mixed"
    if both:
        return "mixed"
    if nyc_only:
        return "NYC-limited"
    if lb_only:
        return "LB-limited"
    return "none"


# =============================================================================
# CELL EVALUATION — evaluate all criteria for one scenario cell
# =============================================================================

def evaluate_cell(
    trenton_flow: pd.Series,
    tfo_level: float,
    lb_storage: pd.Series,
    lb_capacity_mg: float,
    ierq_balance: pd.Series,
) -> dict:
    """
    Evaluate all three criteria for a single scenario cell.
    Returns pass/fail, per-criterion results, and failure attribution.

    Parameters
    ----------
    trenton_flow : pd.Series
        Daily Trenton gage flow (MGD)
    tfo_level : float
        TFO level for this SLR scenario (MGD)
    lb_storage : pd.Series
        Daily LB combined storage (MG)
    lb_capacity_mg : float
        Total LB storage capacity (MG)
    ierq_balance : pd.Series
        Daily IERQ Trenton bank balance (MG)

    Returns
    -------
    dict: {cell_fails, failure_mode, reliability, severity, lb_storage_result}
    """
    rel = evaluate_trenton_reliability(trenton_flow, tfo_level)
    sev = evaluate_shortfall_severity(trenton_flow, tfo_level)
    lb = evaluate_lb_storage(lb_storage, lb_capacity_mg)

    cell_fails = rel["fails"] or sev["fails"] or lb["fails"]
    failure_mode = attribute_failure_mode(ierq_balance, lb_storage, lb_capacity_mg) \
                   if cell_fails else "none"

    return {
        "cell_fails": cell_fails,
        "failure_mode": failure_mode,
        "reliability": rel,
        "severity": sev,
        "lb_storage": lb,
    }

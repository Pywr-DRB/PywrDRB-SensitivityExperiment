"""
Regime attribution — NYC-limited vs LB-limited vs co-limited.

Used by both D4 (per-ensemble-member attribution) and D1 (per-scenario-cell attribution).

The attribution answers: when the joint system fails to meet Trenton Flow Objectives,
which subsystem is the binding constraint — NYC IERQ exhaustion or LB storage depletion?

Definitions
-----------
NYC-limited  : IERQ bank balance first hits zero while LB combined storage is still above
               the conservation pool threshold.  NYC cannot release more regardless of LB state.
LB-limited   : LB combined storage first drops below conservation pool while IERQ bank still
               has remaining balance.  LB cannot contribute regardless of NYC state.
Co-limited   : Both constraints bind simultaneously (within LAG_DAYS of each other).
No failure   : Neither constraint binds during the simulation period.

Constants
---------
IERQ_EXHAUSTION_MG   : IERQ bank balance (MG) considered effectively zero.
LB_CONSERVATION_FRAC : Combined LB (Blue Marsh + Beltzville) fraction defining conservation pool.
LB_TOTAL_CAPACITY_MG : Total DRBC usable storage — Beltzville 13,500 MG + Blue Marsh 7,450 MG.
LAG_DAYS             : Window (days) within which simultaneous binding = co-limited.

Sources
-------
IERQ ceiling 6.09 BG/yr — Art. VII; FFMP §2.c.i (Trenton bank specifically)
LB conservation pool — Water Code §2.5.6.C; Beltzville 73.7%, Blue Marsh 68.9%
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Constants — edit here when confirmed from primary sources
# ---------------------------------------------------------------------------

IERQ_EXHAUSTION_MG: float = 500.0      # MG — bank considered exhausted below this

# LB reservoir DRBC usable capacities — confirmed from pywrdrb/parameters/ffmp.py docstring
LB_BELTZVILLE_CAPACITY_MG: float  = 13_500.0
LB_BLUEMARSH_CAPACITY_MG: float   =  7_450.0
LB_TOTAL_CAPACITY_MG: float       = LB_BELTZVILLE_CAPACITY_MG + LB_BLUEMARSH_CAPACITY_MG  # 20 950 MG

# LB warning thresholds — Water Code §2.5.6.C; from pywrdrb/parameters/ffmp.py
# Beltzville warning: 73.7% of 13 500 = 9 949.5 MG
# Blue Marsh warning: 68.9% of  7 450 = 5 132.1 MG
# Combined warning pool: 15 081.6 MG → 72.0% of total
_BETZ_WARNING_FRAC: float = 0.737
_BM_WARNING_FRAC:   float = 0.689
LB_CONSERVATION_FRAC: float = (
    LB_BELTZVILLE_CAPACITY_MG * _BETZ_WARNING_FRAC
    + LB_BLUEMARSH_CAPACITY_MG * _BM_WARNING_FRAC
) / LB_TOTAL_CAPACITY_MG   # ≈ 0.720

LAG_DAYS: int = 7                       # days — co-limited window


# ---------------------------------------------------------------------------
# Core attribution functions
# ---------------------------------------------------------------------------

def attribute_regime(
    ierq_balance: pd.Series,
    lb_storage: pd.Series,
    lb_capacity_mg: float = LB_TOTAL_CAPACITY_MG,
    ierq_threshold_mg: float = IERQ_EXHAUSTION_MG,
    lb_conservation_frac: float = LB_CONSERVATION_FRAC,
    lag_days: int = LAG_DAYS,
) -> str:
    """
    Attribute a simulation period to a failure regime.

    Parameters
    ----------
    ierq_balance : pd.Series
        Daily IERQ Trenton bank balance (MG).  From ``banks.py`` IERQRelease_step1 output.
    lb_storage : pd.Series
        Daily combined LB storage (Blue Marsh + Beltzville), MG.
    lb_capacity_mg : float
        Total DRBC usable LB storage capacity (MG).
    ierq_threshold_mg : float
        Balance below which IERQ is considered exhausted.
    lb_conservation_frac : float
        Fractional threshold below which LB is considered at conservation pool.
    lag_days : int
        Window (days) within which simultaneous binding is classified as co-limited.

    Returns
    -------
    str : "NYC-limited" | "LB-limited" | "co-limited" | "no-failure"
    """
    lb_threshold_mg = lb_capacity_mg * lb_conservation_frac

    ierq_exhausted = ierq_balance <= ierq_threshold_mg
    lb_depleted = lb_storage <= lb_threshold_mg

    t_ierq = _first_true_index(ierq_exhausted)
    t_lb   = _first_true_index(lb_depleted)

    if t_ierq is None and t_lb is None:
        return "no-failure"
    if t_ierq is None:
        return "LB-limited"
    if t_lb is None:
        return "NYC-limited"
    if abs(t_ierq - t_lb) <= lag_days:
        return "co-limited"
    if t_ierq < t_lb:
        return "NYC-limited"
    return "LB-limited"


def attribute_daily(
    ierq_balance: pd.Series,
    lb_storage: pd.Series,
    lb_capacity_mg: float = LB_TOTAL_CAPACITY_MG,
    ierq_threshold_mg: float = IERQ_EXHAUSTION_MG,
    lb_conservation_frac: float = LB_CONSERVATION_FRAC,
) -> pd.Series:
    """
    Per-day regime label (vectorised).

    Returns a Series with values: 0=normal, 1=NYC-limited, 2=LB-limited, 3=co-limited.
    Useful for computing the fraction of days in each regime across a simulation period.
    """
    lb_threshold_mg = lb_capacity_mg * lb_conservation_frac
    ierq_exhausted = (ierq_balance <= ierq_threshold_mg).astype(int)  # 1 when exhausted
    lb_depleted    = (lb_storage   <= lb_threshold_mg).astype(int)    # 1 when depleted

    regime = pd.Series(0, index=ierq_balance.index, name="regime")
    regime[( ierq_exhausted == 1) & (lb_depleted == 0)] = 1  # NYC-limited
    regime[( ierq_exhausted == 0) & (lb_depleted == 1)] = 2  # LB-limited
    regime[( ierq_exhausted == 1) & (lb_depleted == 1)] = 3  # co-limited
    return regime


def regime_summary(
    ierq_balance: pd.Series,
    lb_storage: pd.Series,
    lb_capacity_mg: float = LB_TOTAL_CAPACITY_MG,
    ierq_threshold_mg: float = IERQ_EXHAUSTION_MG,
    lb_conservation_frac: float = LB_CONSERVATION_FRAC,
    lag_days: int = LAG_DAYS,
) -> dict:
    """
    Full attribution summary for one simulation member.

    Returns dict with:
    - overall_regime: str — dominant failure mode (by first occurrence)
    - regime_day_fractions: dict — fraction of days in each regime
    - t_ierq_exhaustion: int or None — timestep of first IERQ exhaustion
    - t_lb_depletion: int or None — timestep of first LB depletion
    """
    lb_threshold_mg = lb_capacity_mg * lb_conservation_frac
    ierq_exhausted = ierq_balance <= ierq_threshold_mg
    lb_depleted    = lb_storage   <= lb_threshold_mg

    t_ierq = _first_true_index(ierq_exhausted)
    t_lb   = _first_true_index(lb_depleted)

    overall = attribute_regime(
        ierq_balance, lb_storage,
        lb_capacity_mg, ierq_threshold_mg, lb_conservation_frac, lag_days,
    )

    daily = attribute_daily(
        ierq_balance, lb_storage, lb_capacity_mg, ierq_threshold_mg, lb_conservation_frac,
    )
    n = len(daily)
    fractions = {
        "normal":      (daily == 0).sum() / n,
        "NYC-limited": (daily == 1).sum() / n,
        "LB-limited":  (daily == 2).sum() / n,
        "co-limited":  (daily == 3).sum() / n,
    }

    return {
        "overall_regime":       overall,
        "regime_day_fractions": fractions,
        "t_ierq_exhaustion":    t_ierq,
        "t_lb_depletion":       t_lb,
    }


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _first_true_index(bool_series: pd.Series) -> Optional[int]:
    """Return integer position of first True value, or None."""
    idx = np.where(bool_series)[0]
    return int(idx[0]) if len(idx) > 0 else None

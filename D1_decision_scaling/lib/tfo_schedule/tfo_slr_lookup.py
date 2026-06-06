"""
D1 — DRBC Dec 2025 Trenton Flow Objective vs SLR lookup.

Reads committed schedule from tfo_slr_table.csv (DRBC Evaluation of Sea Level Rise
and Salinity in the Delaware River, Dec 2025).

Usage
-----
    from D1_decision_scaling.tfo_schedule.tfo_slr_lookup import get_tfo_for_slr_m

    tfo = get_tfo_for_slr_m(slr_m=0.5)
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

_TABLE_PATH = Path(__file__).parent / "tfo_slr_table.csv"


def load_tfo_table() -> pd.DataFrame:
    """Load full SLR → TFO table."""
    if not _TABLE_PATH.exists():
        raise FileNotFoundError(f"Missing TFO table: {_TABLE_PATH}")
    return pd.read_csv(_TABLE_PATH)


def get_tfo_for_slr_m(slr_m: float, interpolate: bool = True) -> float:
    """
    Return Trenton Flow Objective (MGD) for a given SLR level (meters).

    Parameters
    ----------
    slr_m : float
        Sea level rise in meters above baseline.
    interpolate : bool
        Linear interpolation between tabulated levels if True.

    Returns
    -------
    float
        Trenton Flow Objective in MGD.
    """
    table = load_tfo_table()
    slr_vals = table["slr_m"].values.astype(float)
    tfo_vals = table["tfo_mgd"].values.astype(float)
    slr_min, slr_max = slr_vals.min(), slr_vals.max()
    if slr_m < slr_min or slr_m > slr_max:
        raise ValueError(
            f"SLR {slr_m} m outside table range [{slr_min}, {slr_max}] m."
        )
    if interpolate:
        return float(np.interp(slr_m, slr_vals, tfo_vals))
    idx = int(np.argmin(np.abs(slr_vals - slr_m)))
    return float(tfo_vals[idx])


def get_tfo_for_slr_ft(slr_ft: float, interpolate: bool = True) -> float:
    """Return TFO (MGD) for SLR in feet."""
    table = load_tfo_table()
    slr_vals = table["slr_ft"].values.astype(float)
    tfo_vals = table["tfo_mgd"].values.astype(float)
    if interpolate:
        return float(np.interp(slr_ft, slr_vals, tfo_vals))
    idx = int(np.argmin(np.abs(slr_vals - slr_ft)))
    return float(tfo_vals[idx])


def get_tfo_table() -> pd.DataFrame:
    """Return display-friendly lookup table."""
    df = load_tfo_table()
    return df[["slr_id", "slr_m", "slr_ft", "tfo_cfs", "tfo_mgd", "status"]]


if __name__ == "__main__":
    print("DRBC Dec 2025 TFO vs SLR Lookup Table\n")
    print(get_tfo_table().to_string(index=False))
    print()
    for slr_m in [0.0, 0.3, 0.5, 0.8, 1.2, 1.6]:
        print(f"  SLR = {slr_m:.1f} m → TFO = {get_tfo_for_slr_m(slr_m):.2f} MGD")

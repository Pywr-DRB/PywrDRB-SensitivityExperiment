"""
SLR → salt-front bias shift for Mode A salinity coupling.

Historical SalinityLSTM has no sea-level input. DRBC (Dec 2025) hydrodynamic
scenarios provide ΔRM_upstream: additional upstream migration of the salt front
at the same Trenton/Schuylkill flows under higher SLR.

Effective salt front for criterion evaluation:
    sf_mu_effective = sf_mu_lstm + delta_rm_upstream(slr_id)

Replace provisional values in slr_salt_front_shift.csv when DRBC tables are digitized.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

_SHIFT_TABLE = Path(__file__).parent / "slr_salt_front_shift.csv"
_cache: dict[str, dict] | None = None


def _load_table() -> dict[str, dict]:
    global _cache
    if _cache is not None:
        return _cache
    if not _SHIFT_TABLE.exists():
        raise FileNotFoundError(
            f"Salinity shift table not found: {_SHIFT_TABLE}\n"
            "Create slr_salt_front_shift.csv alongside tfo_slr_table.csv."
        )
    df = pd.read_csv(_SHIFT_TABLE)
    _cache = {
        str(row["slr_id"]): {
            "slr_m": float(row["slr_m"]),
            "delta_rm_upstream": float(row["delta_rm_upstream"]),
            "rm_protect_camden": float(row["rm_protect_camden"]),
            "status": str(row.get("status", "provisional")),
        }
        for _, row in df.iterrows()
    }
    return _cache


def delta_rm_upstream(slr_id: str) -> float:
    """Upstream bias shift (river miles) applied to LSTM salt-front predictions."""
    table = _load_table()
    if slr_id not in table:
        raise KeyError(f"Unknown slr_id {slr_id!r}; expected one of {sorted(table)}")
    return table[slr_id]["delta_rm_upstream"]


def rm_protect_camden(slr_id: str) -> float:
    """Camden intake protection threshold (river miles); default 98 for all SLR levels."""
    table = _load_table()
    if slr_id not in table:
        raise KeyError(f"Unknown slr_id {slr_id!r}; expected one of {sorted(table)}")
    return table[slr_id]["rm_protect_camden"]

"""
D1 Decision Scaling — experiment grid configuration.

Single source of truth for the 3-axis scenario space.
All downstream scripts import from here — change the grid here, everything else adjusts.

Scenario grid
-------------
Axis 1: Streamflow percentile (7 bins)   — Kirsch-Nowak generator
Axis 2: SLR level (6 levels)             — DRBC Dec 2025 TFO schedule
Axis 3: LB cap multiplier (3 levels)     — institutional LB contribution cap

Total cells: 7 × 6 × 3 = 126
Total runs:  126 × REALIZATIONS_PER_CELL (default 30) = 3,780

See committee/D1_D4_experimental_plans.md Table D1-2 and D1-3.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from typing import Iterator

import pandas as pd

# ---------------------------------------------------------------------------
# CONFIG NAME — determines output directory; change when you change the grid
# ---------------------------------------------------------------------------
CONFIG_NAME: str = "d1_v1_7x6x3_r30"
# Pattern: d1_v{version}_{nflow}x{nslr}x{nlb}_r{realizations}

_TFO_TABLE_PATH = Path(__file__).parent.parent / "lib" / "tfo_schedule" / "tfo_slr_table.csv"

# ---------------------------------------------------------------------------
# Axis 1 — Streamflow percentile bins
# ---------------------------------------------------------------------------
STREAMFLOW_BINS: list[dict] = [
    {"id": "Q01", "label": "Very dry",   "pct_change": -0.30, "percentile": 5},
    {"id": "Q02", "label": "Dry",        "pct_change": -0.20, "percentile": 15},
    {"id": "Q03", "label": "Mod dry",    "pct_change": -0.10, "percentile": 30},
    {"id": "Q04", "label": "Normal",     "pct_change":  0.00, "percentile": 50},
    {"id": "Q05", "label": "Mod wet",    "pct_change":  0.10, "percentile": 70},
    {"id": "Q06", "label": "Wet",        "pct_change":  0.15, "percentile": 85},
    {"id": "Q07", "label": "Very wet",   "pct_change":  0.20, "percentile": 95},
]

# ---------------------------------------------------------------------------
# Axis 2 — SLR levels from DRBC Dec 2025 table (tfo_slr_table.csv)
# ---------------------------------------------------------------------------


def _load_slr_levels() -> list[dict]:
    """Load SLR → TFO schedule from committed CSV."""
    if not _TFO_TABLE_PATH.exists():
        raise FileNotFoundError(
            f"TFO schedule not found: {_TFO_TABLE_PATH}\n"
            "Run tfo_schedule/digitize_tfo_table.py or create tfo_slr_table.csv."
        )
    df = pd.read_csv(_TFO_TABLE_PATH)
    levels = []
    for _, row in df.iterrows():
        levels.append({
            "id":      str(row["slr_id"]),
            "slr_m":   float(row["slr_m"]),
            "slr_ft":  float(row["slr_ft"]),
            "tfo_mgd": float(row["tfo_mgd"]),
            "tfo_cfs": float(row["tfo_cfs"]),
            "status":  str(row.get("status", "provisional")),
        })
    return levels


SLR_LEVELS: list[dict] = _load_slr_levels()

# ---------------------------------------------------------------------------
# Axis 3 — LB institutional cap multiplier
# ---------------------------------------------------------------------------
LB_CAP_LEVELS: list[dict] = [
    {"id": "LB0", "multiplier": 0.75, "label": "Reduced (75% of current)"},
    {"id": "LB1", "multiplier": 1.00, "label": "Baseline (current FFMP)"},
    {"id": "LB2", "multiplier": 1.25, "label": "Increased (125% of current)"},
]

# ---------------------------------------------------------------------------
# Realizations per cell
# ---------------------------------------------------------------------------
REALIZATIONS_PER_CELL: int = 30

# Simulation period — match D4 / Amestoy (79 years, 28854 days)
SIM_YEARS: int = 79
SIM_START: str = "1945-01-01"
SIM_END:   str = "2023-12-31"

# ---------------------------------------------------------------------------
# Derived grid properties
# ---------------------------------------------------------------------------
N_FLOW_BINS: int = len(STREAMFLOW_BINS)
N_SLR_LEVELS: int = len(SLR_LEVELS)
N_LB_LEVELS: int = len(LB_CAP_LEVELS)
N_CELLS: int = N_FLOW_BINS * N_SLR_LEVELS * N_LB_LEVELS
TOTAL_RUNS: int = N_CELLS * REALIZATIONS_PER_CELL


def iter_cells() -> Iterator[dict]:
    """
    Yield one dict per scenario cell: {cell_id, flow_bin, slr_level, lb_level}.

    Usage
    -----
    for cell in iter_cells():
        run_pywrdrb_for_cell(cell)
    """
    for q, s, lb in product(STREAMFLOW_BINS, SLR_LEVELS, LB_CAP_LEVELS):
        yield {
            "cell_id":        f"{q['id']}_{s['id']}_{lb['id']}",
            "flow_bin":       q,
            "slr_level":      s,
            "lb_level":       lb,
            "tfo_mgd":        s["tfo_mgd"],
            "pct_change":     q["pct_change"],
            "lb_multiplier":  lb["multiplier"],
        }


def cell_index_table() -> pd.DataFrame:
    """Return a DataFrame of all cells — useful for SLURM array indexing."""
    rows = list(iter_cells())
    return pd.DataFrame(rows).reset_index(drop=True)


def pilot_lb1_indices() -> list[int]:
    """0-based indices of cells with LB1 (baseline cap) — 42 cells."""
    return [
        i for i, cell in enumerate(iter_cells())
        if cell["lb_level"]["id"] == "LB1"
    ]


if __name__ == "__main__":
    print(f"CONFIG: {CONFIG_NAME}")
    print(f"Grid:   {N_FLOW_BINS} × {N_SLR_LEVELS} × {N_LB_LEVELS} = {N_CELLS} cells")
    print(f"Runs:   {N_CELLS} × {REALIZATIONS_PER_CELL} = {TOTAL_RUNS} total Pywr-DRB runs")
    print(f"Pilot LB1 indices: {len(pilot_lb1_indices())} cells")
    df = cell_index_table()
    print(df[["cell_id", "tfo_mgd", "lb_multiplier"]].head(10).to_string(index=True))
    print(f"... ({len(df)} rows total)")

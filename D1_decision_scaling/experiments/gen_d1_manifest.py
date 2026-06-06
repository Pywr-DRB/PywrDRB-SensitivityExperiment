"""
D1 — Auto-generate experiment manifest from live config and criteria.

Usage
-----
    python experiments/gen_d1_manifest.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

_D1 = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_D1 / "experiments"))
sys.path.insert(0, str(_D1 / "lib" / "performance"))
sys.path.insert(0, str(_D1.parent / "shared"))

from config import (
    CONFIG_NAME,
    STREAMFLOW_BINS,
    SLR_LEVELS,
    LB_CAP_LEVELS,
    REALIZATIONS_PER_CELL,
    N_CELLS,
    TOTAL_RUNS,
)
from criteria import (
    RELIABILITY_THRESHOLD,
    SEVERITY_THRESHOLD_MG,
    LB_CONSERVATION_POOL_FRAC,
    IERQ_EXHAUSTION_THRESHOLD_MG,
)


def main():
    outdir = _D1 / "results" / "manifest"
    outdir.mkdir(parents=True, exist_ok=True)

    grid = {
        "config_name": CONFIG_NAME,
        "n_cells": N_CELLS,
        "realizations_per_cell": REALIZATIONS_PER_CELL,
        "total_runs": TOTAL_RUNS,
        "streamflow_bins": STREAMFLOW_BINS,
        "slr_levels": SLR_LEVELS,
        "lb_cap_levels": LB_CAP_LEVELS,
    }
    with open(outdir / "grid.json", "w") as f:
        json.dump(grid, f, indent=2)

    thresholds = pd.DataFrame([
        {"name": "RELIABILITY_THRESHOLD", "value": RELIABILITY_THRESHOLD, "status": "provisional"},
        {"name": "SEVERITY_THRESHOLD_MG", "value": SEVERITY_THRESHOLD_MG, "status": "provisional"},
        {"name": "LB_CONSERVATION_POOL_FRAC", "value": LB_CONSERVATION_POOL_FRAC, "status": "provisional"},
        {"name": "IERQ_EXHAUSTION_THRESHOLD_MG", "value": IERQ_EXHAUSTION_THRESHOLD_MG, "status": "provisional"},
    ])
    thresholds.to_csv(outdir / "thresholds.csv", index=False)

    tfo = pd.read_csv(_D1 / "lib" / "tfo_schedule" / "tfo_slr_table.csv")
    tfo.to_csv(outdir / "tfo_schedule.csv", index=False)

    cmip6 = _D1 / "lib" / "scenario_extraction" / "cmip6_cell_weights_montague.csv"
    if cmip6.exists():
        pd.read_csv(cmip6).groupby("streamflow_bin_id")["bin_weight"].first().reset_index().to_csv(
            outdir / "cmip6_bin_weights_montague.csv", index=False
        )

    print(f"Manifest written → {outdir}")


if __name__ == "__main__":
    main()

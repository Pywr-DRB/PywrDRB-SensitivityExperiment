"""
D1 — Smoke test: one cell (Q04_S0_LB1), one realization.

Generates Q04 flows if missing, runs Pywr-DRB, prints criteria + regime.

Usage
-----
    python smoke_test.py
    python smoke_test.py --skip-generate
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "shared"))
sys.path.insert(0, str(Path(__file__).parent))

from config import iter_cells, REALIZATIONS_PER_CELL

from run_failure_surface_sweep import run_cell, FLOWS_DIR


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-generate", action="store_true")
    ap.add_argument(
        "--no-salinity",
        action="store_true",
        help="Skip SalinityLSTM (no PywrDRB-ML plugin required)",
    )
    args = ap.parse_args()

    target_id = "Q04_S0_LB1"
    cell = next(c for c in iter_cells() if c["cell_id"] == target_id)

    q04_dir = FLOWS_DIR / "Q04"
    if not (q04_dir / "realization_000.parquet").exists() and not args.skip_generate:
        print("Generating Q04 realization_000 ...")
        gen_script = _REPO / "D1_decision_scaling" / "generator" / "kirsch_generate.py"
        subprocess.check_call([
            sys.executable, str(gen_script),
            "--bin-id", "Q04", "--realizations", "1",
        ])

    enable_salinity = not args.no_salinity
    print(f"Running smoke cell: {target_id} (salinity={enable_salinity})")
    result = run_cell(cell, n_realizations=1, enable_salinity=enable_salinity)
    print(f"  cell_fails: {result['cell_fails']}")
    print(f"  failure_fraction: {result['failure_fraction']}")
    print(f"  salinity_failure_fraction: {result.get('salinity_failure_fraction')}")
    print(f"  dominant_regime: {result['dominant_regime']}")
    print(f"  tfo_mgd: {result['tfo_mgd']}")
    print("Smoke test complete.")


if __name__ == "__main__":
    main()

"""
D4 — Generate Sobol sensitivity analysis sample table.

Writes a CSV of parameter combinations using SALib Saltelli sampling.
This CSV is the input to run_sobol_sweep.py (SLURM array).

Usage
-----
    python sobol_design.py [--outdir results/sobol]

Output
------
    results/sobol/sobol_samples.csv  — shape (TOTAL_RUNS, K) — one row per model run
    results/sobol/sobol_design.json  — SALib problem definition (for analysis step)

Run ONCE before submitting SLURM array.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from SALib.sample import sobol as saltelli   # SALib ≥1.5: salib.sample.sobol
except ImportError:
    try:
        from SALib.sample import saltelli        # SALib <1.5 fallback
    except ImportError:
        raise ImportError("SALib not installed.  pip install SALib>=1.5")

from config import PARAM_NAMES, PARAM_BOUNDS, K, N_SOBOL_BASE, TOTAL_RUNS, PARAMETERS


def build_problem() -> dict:
    """Return SALib problem definition dict."""
    return {
        "num_vars": K,
        "names":    PARAM_NAMES,
        "bounds":   PARAM_BOUNDS,
    }


def generate_samples(outdir: Path) -> pd.DataFrame:
    """
    Generate Saltelli samples and write to CSV.

    Returns DataFrame of shape (TOTAL_RUNS, K).
    """
    outdir.mkdir(parents=True, exist_ok=True)
    problem = build_problem()

    print(f"Generating Saltelli samples: N={N_SOBOL_BASE}, k={K}, total={TOTAL_RUNS}")
    # calc_second_order=True gives N*(2K+2) rows = TOTAL_RUNS; required for Si_T estimation.
    param_values = saltelli.sample(problem, N_SOBOL_BASE, calc_second_order=True)
    assert param_values.shape == (TOTAL_RUNS, K), (
        f"Unexpected shape {param_values.shape}; expected ({TOTAL_RUNS}, {K})"
    )

    df = pd.DataFrame(param_values, columns=PARAM_NAMES)
    df.index.name = "sample_id"

    samples_path = outdir / "sobol_samples.csv"
    df.to_csv(samples_path)
    print(f"  Wrote {samples_path}  ({len(df)} rows)")

    design_path = outdir / "sobol_design.json"
    with open(design_path, "w") as f:
        json.dump(problem, f, indent=2)
    print(f"  Wrote {design_path}")

    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", default="results/sobol", help="Output directory")
    args = ap.parse_args()

    generate_samples(Path(args.outdir))
    print(f"\nNext step: submit SLURM array with {TOTAL_RUNS} tasks")
    print("  sbatch slurm/submit_sobol.sh")

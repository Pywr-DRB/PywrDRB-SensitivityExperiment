"""
D1 — Aggregate per-realization JSON metrics into failure_surface_summary.parquet.

Usage
-----
    python aggregate_results.py
    python aggregate_results.py --results-dir results/failure_surface/d1_v1_7x6x3_r30
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from config import CONFIG_NAME


def aggregate(results_dir: Path) -> pd.DataFrame:
    """Build one summary row per cell from realization_*_metrics.json files."""
    rows = []
    for cell_dir in sorted(results_dir.glob("cell_*")):
        if not cell_dir.is_dir():
            continue
        cell_id = cell_dir.name.replace("cell_", "", 1)
        realizations = sorted(cell_dir.glob("realization_*_metrics.json"))
        if not realizations:
            continue

        metrics = []
        for p in realizations:
            with open(p) as f:
                metrics.append(json.load(f))

        fails = sum(1 for m in metrics if m.get("cell_fails"))
        n = len(metrics)
        regimes = [m.get("regime", "none") for m in metrics]
        dominant = max(set(regimes), key=regimes.count) if regimes else "none"

        rel_vals = [
            m.get("reliability", {}).get("reliability")
            for m in metrics
            if isinstance(m.get("reliability"), dict)
        ]
        sal_fails = sum(
            1 for m in metrics
            if isinstance(m.get("salinity"), dict) and m["salinity"].get("fails")
        )
        sal_max = [
            m["salinity"].get("max_rm_effective")
            for m in metrics
            if isinstance(m.get("salinity"), dict)
            and m["salinity"].get("max_rm_effective") is not None
        ]

        parts = cell_id.split("_")
        rows.append({
            "cell_id": cell_id,
            "flow_bin_id": parts[0] if parts else cell_id,
            "slr_id": parts[1] if len(parts) > 1 else None,
            "lb_level_id": parts[2] if len(parts) > 2 else None,
            "cell_fails": fails > 0,
            "failure_fraction": fails / n if n else 0.0,
            "salinity_failure_fraction": sal_fails / n if n else 0.0,
            "mean_max_rm_effective": float(pd.Series(sal_max).mean()) if sal_max else None,
            "dominant_regime": dominant,
            "mean_reliability": float(pd.Series(rel_vals).mean()) if rel_vals else None,
            "n_realizations": n,
        })

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    default_dir = Path(__file__).parent.parent / "results" / "failure_surface" / CONFIG_NAME
    ap.add_argument("--results-dir", type=Path, default=default_dir)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    df = aggregate(args.results_dir)
    out_path = args.out or args.results_dir / "failure_surface_summary.parquet"
    df.to_parquet(out_path, index=False)
    print(f"Wrote {len(df)} rows → {out_path}")
    if len(df):
        print(f"Failed cells: {df['cell_fails'].sum()} / {len(df)}")


if __name__ == "__main__":
    main()

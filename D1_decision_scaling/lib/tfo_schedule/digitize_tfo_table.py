"""
One-time helper: validate / refresh tfo_slr_table.csv from DRBC PDF or manual edits.

The committed CSV is the source of truth for experiments/config.py SLR_LEVELS.
Edit tfo_slr_table.csv directly when PDF values are confirmed.

Usage
-----
    python digitize_tfo_table.py --validate
    python digitize_tfo_table.py --print
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

TABLE_PATH = Path(__file__).parent / "tfo_slr_table.csv"
CFS_TO_MGD = 0.646317


def validate_table(df: pd.DataFrame) -> None:
    required = {"slr_id", "slr_m", "slr_ft", "tfo_cfs", "tfo_mgd", "status"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # S0 must match pywrdrb baseline
    s0 = df.loc[df["slr_id"] == "S0"].iloc[0]
    if abs(s0["tfo_mgd"] - 1938.95) > 0.1:
        raise ValueError(f"S0 TFO must be 1938.95 MGD (3000 cfs); got {s0['tfo_mgd']}")

    # cfs ↔ mgd consistency
    for _, row in df.iterrows():
        expected_mgd = row["tfo_cfs"] * CFS_TO_MGD
        if abs(row["tfo_mgd"] - expected_mgd) > 1.0:
            raise ValueError(
                f"{row['slr_id']}: tfo_mgd={row['tfo_mgd']} != "
                f"tfo_cfs×{CFS_TO_MGD}={expected_mgd:.2f}"
            )

    slr_m = df["slr_m"].values
    if not all(slr_m[i] <= slr_m[i + 1] for i in range(len(slr_m) - 1)):
        raise ValueError("slr_m must be monotonically increasing")

    print(f"Validation OK: {len(df)} SLR levels, S0={s0['tfo_mgd']} MGD")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--validate", action="store_true", help="Validate committed CSV")
    ap.add_argument("--print", action="store_true", help="Print table")
    args = ap.parse_args()

    df = pd.read_csv(TABLE_PATH)
    if args.validate or not args.print:
        validate_table(df)
    if args.print or not args.validate:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()

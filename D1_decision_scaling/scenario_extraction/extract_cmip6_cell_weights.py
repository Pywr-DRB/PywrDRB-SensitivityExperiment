"""
D1 Step 3 — Extract CMIP6 streamflow conditions and map to failure surface cells.

For each of the 14 SSP245 2020-2059 CMIP6 projections (7 GCMs × 2 hydro models),
computes a summary streamflow statistic and maps it to a percentile position on
the failure surface streamflow axis. The result is a probability weight per cell:
how many CMIP6 projections land in each streamflow band.

Output:
    scenario_extraction/cmip6_cell_weights.csv
        columns: dataset, gcm, hydro_model, ssp, period,
                 mean_annual_nyc_inflow_mgd, percentile_vs_baseline, cell_idx

Usage:
    python extract_cmip6_cell_weights.py

Requires:
    - CMIP6 data in ~/Research/CMIP6_multimodel_streamflow/pywrdrb/inputs/
    - Baseline: PRMS_RAPID_Daymet2019_1980_2019 and VIC5_RAPID_Daymet2019_...
    - No Pywr-DRB model run needed — reads gage_flow_mgd.csv directly

TODO (ask Scott):
    - Which streamflow metric best represents the failure surface streamflow axis?
      Options: mean annual flow at Montague, mean NYC inflow aggregate (cannonsville +
      pepacton + neversink), or low-flow percentile (e.g. 10th percentile annual min).
    - How many streamflow cells on the failure surface grid?
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

CMIP6_DIR = Path.home() / "Research/CMIP6_multimodel_streamflow/pywrdrb/inputs"

# D1 target: SSP245, 2020-2059 (near-future, "by 2075" framing)
TARGET_SSP = "ssp245"
TARGET_PERIOD = "2020_2059"

# Historical baselines (both hydro models)
BASELINES = [
    "PRMS_RAPID_Daymet2019_1980_2019",
    "VIC5_RAPID_Daymet2019_1980_2019",
]

# NYC inflow nodes (aggregate = cannonsville + pepacton + neversink catchment inflows)
# TODO: confirm with Scott whether to use gage_flow or catchment_inflow for this metric
NYC_NODES = ["cannonsville", "pepacton", "neversink"]

# Streamflow axis: number of percentile bins on failure surface
# TODO: finalize with Scott
N_STREAMFLOW_CELLS = 10


# =============================================================================
# HELPERS
# =============================================================================

def parse_dataset_name(name: str) -> dict:
    """Parse folder name into components."""
    parts = name.split("_")
    hydro_model = parts[0]  # PRMS or VIC5
    # Format: <hydro>_RAPID_<GCM>_<ssp>_<run>_DBCCA_Daymet_<start>_<end>
    # or: <hydro>_RAPID_Daymet2019_<start>_<end>  (baseline)
    if "Daymet2019" in name or "Livneh2018" in name:
        return {"hydro_model": hydro_model, "gcm": None, "ssp": None,
                "period": f"{parts[-2]}_{parts[-1]}", "is_baseline": True}
    return {
        "hydro_model": hydro_model,
        "gcm": parts[2],
        "ssp": parts[3],
        "run_id": parts[4],
        "period": f"{parts[-2]}_{parts[-1]}",
        "is_baseline": False,
    }


def load_nyc_aggregate_flow(dataset_path: Path) -> pd.Series:
    """
    Load gage_flow_mgd.csv and return mean daily NYC aggregate inflow (MGD).
    NYC aggregate = sum of cannonsville + pepacton + neversink columns.
    Falls back to available NYC columns if some are missing.
    """
    fpath = dataset_path / "gage_flow_mgd.csv"
    if not fpath.exists():
        raise FileNotFoundError(f"Missing: {fpath}")
    df = pd.read_csv(fpath, index_col=0, parse_dates=True)
    available = [c for c in NYC_NODES if c in df.columns]
    if not available:
        raise ValueError(f"No NYC nodes found in {fpath.parent.name}. Columns: {df.columns.tolist()}")
    return df[available].sum(axis=1)


# =============================================================================
# MAIN
# =============================================================================

def main():
    datasets = [d for d in CMIP6_DIR.iterdir() if d.is_dir()]

    # --- Load baselines (one per hydro model) ---
    baseline_stats = {}
    for bname in BASELINES:
        bpath = CMIP6_DIR / bname
        if not bpath.exists():
            print(f"WARNING: baseline not found: {bname}")
            continue
        meta = parse_dataset_name(bname)
        flow = load_nyc_aggregate_flow(bpath)
        mean_annual = flow.resample("YE").sum().mean()  # MGD → annual total → mean
        baseline_stats[meta["hydro_model"]] = {
            "dataset": bname,
            "mean_annual_mgd": mean_annual,
            "daily_series": flow,
        }
        print(f"Baseline {meta['hydro_model']}: mean annual NYC inflow = {mean_annual:.0f} MGD")

    # --- Process SSP245 2020-2059 projections ---
    records = []
    for dpath in sorted(datasets):
        meta = parse_dataset_name(dpath.name)
        if meta.get("is_baseline"):
            continue
        if meta.get("ssp") != TARGET_SSP or meta.get("period") != TARGET_PERIOD:
            continue

        hm = meta["hydro_model"]
        if hm not in baseline_stats:
            print(f"SKIP (no baseline for {hm}): {dpath.name}")
            continue

        try:
            flow = load_nyc_aggregate_flow(dpath)
        except (FileNotFoundError, ValueError) as e:
            print(f"ERROR: {dpath.name}: {e}")
            continue

        mean_annual = flow.resample("YE").sum().mean()
        pct_change = (mean_annual - baseline_stats[hm]["mean_annual_mgd"]) / \
                     baseline_stats[hm]["mean_annual_mgd"] * 100.0

        records.append({
            "dataset": dpath.name,
            "hydro_model": hm,
            "gcm": meta["gcm"],
            "ssp": meta["ssp"],
            "period": meta["period"],
            "mean_annual_nyc_inflow_mgd": mean_annual,
            "pct_change_vs_baseline": pct_change,
        })
        print(f"{dpath.name}: {mean_annual:.0f} MGD  ({pct_change:+.1f}% vs baseline)")

    if not records:
        print("No matching projections found. Check CMIP6_DIR and TARGET_SSP/TARGET_PERIOD.")
        return

    df = pd.DataFrame(records).sort_values("pct_change_vs_baseline")

    # --- Assign streamflow cell index ---
    # Cell 0 = driest, cell N-1 = wettest
    # TODO: finalize cell boundaries with Scott (percentile-based vs fixed interval)
    df["streamflow_cell"] = pd.qcut(
        df["pct_change_vs_baseline"], q=N_STREAMFLOW_CELLS,
        labels=False, duplicates="drop"
    )

    # --- Compute cell weights (fraction of projections per cell) ---
    cell_counts = df.groupby("streamflow_cell").size().rename("n_projections")
    df = df.join(cell_counts, on="streamflow_cell")
    df["cell_weight"] = df["n_projections"] / len(df)

    # --- Save ---
    out_dir = Path(__file__).parent
    out_path = out_dir / "cmip6_cell_weights.csv"
    df.to_csv(out_path, index=False)
    print(f"\nSaved {len(df)} projections → {out_path}")

    # Summary
    print("\n=== CMIP6 projection distribution across streamflow cells ===")
    print(df[["dataset", "pct_change_vs_baseline", "streamflow_cell", "cell_weight"]]
          .to_string(index=False))

    print("\n=== Cell weights (for GCM probability overlay) ===")
    print(cell_counts.to_string())


if __name__ == "__main__":
    main()

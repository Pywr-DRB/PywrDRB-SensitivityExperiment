"""
D1 Step 3 — Extract CMIP6 streamflow conditions and map to failure surface bins.

Computes both NYC aggregate and Montague metrics; writes separate CSVs plus summary.

Usage
-----
    python extract_cmip6_cell_weights.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

DISSERTATION_ROOT = Path(__file__).parents[3]
CMIP6_DIR = DISSERTATION_ROOT / "cmip6" / "pywrdrb" / "inputs"

sys.path.insert(0, str(DISSERTATION_ROOT / "D1_decision_scaling" / "experiments"))
from config import STREAMFLOW_BINS

TARGET_SSP = "ssp245"
TARGET_PERIOD = "2020_2059"

BASELINES: dict[str, str] = {
    "PRMS": "PRMS_RAPID_Daymet2019_1980_2019",
    "VIC5": "VIC5_RAPID_Daymet2019_v20200704D_1980_2019",
}

METRICS = ("nyc_aggregate", "montague")
NYC_NODES = ["cannonsville", "pepacton", "neversink"]
MONTAGUE_NODE = "delMontague"


def parse_dataset_name(name: str) -> dict:
    parts = name.split("_")
    hydro_model = parts[0]
    is_baseline = "Daymet2019" in name or "Livneh2018" in name or "Daymet2020" in name
    if is_baseline:
        return {
            "hydro_model": hydro_model,
            "gcm": None, "ssp": None, "run_id": None,
            "period": f"{parts[-2]}_{parts[-1]}",
            "is_baseline": True,
        }
    return {
        "hydro_model": hydro_model,
        "gcm": parts[2],
        "ssp": parts[3],
        "run_id": parts[4],
        "period": f"{parts[-2]}_{parts[-1]}",
        "is_baseline": False,
    }


def load_flow_series(dataset_path: Path, metric: str) -> pd.Series:
    fpath = dataset_path / "gage_flow_mgd.csv"
    if not fpath.exists():
        raise FileNotFoundError(f"Missing: {fpath}")
    df = pd.read_csv(fpath, index_col=0, parse_dates=True)
    if metric == "nyc_aggregate":
        available = [c for c in NYC_NODES if c in df.columns]
        if not available:
            raise ValueError(f"No NYC nodes in {fpath.parent.name}")
        return df[available].sum(axis=1)
    if metric == "montague":
        if MONTAGUE_NODE not in df.columns:
            raise ValueError(f"No {MONTAGUE_NODE} in {fpath.parent.name}")
        return df[MONTAGUE_NODE]
    raise ValueError(f"Unknown metric: {metric}")


def map_to_config_bin(pct_change: float) -> dict:
    centers = [b["pct_change"] * 100.0 for b in STREAMFLOW_BINS]
    dists = [abs(pct_change - c) for c in centers]
    return STREAMFLOW_BINS[int(np.argmin(dists))]


def process_metric(metric: str) -> pd.DataFrame:
    if not CMIP6_DIR.exists():
        raise FileNotFoundError(f"CMIP6 dir not found: {CMIP6_DIR}")

    baseline_stats: dict[str, dict] = {}
    for hydro_key, bname in BASELINES.items():
        bpath = CMIP6_DIR / bname
        if not bpath.exists():
            print(f"WARNING: baseline missing {hydro_key}: {bpath}")
            continue
        flow = load_flow_series(bpath, metric)
        mean_annual = flow.resample("YE").sum().mean()
        baseline_stats[hydro_key] = {"mean_annual_mgd": mean_annual}
        print(f"[{metric}] Baseline {hydro_key}: {mean_annual:,.0f} MGD")

    records = []
    for dpath in sorted(CMIP6_DIR.iterdir()):
        if not dpath.is_dir():
            continue
        meta = parse_dataset_name(dpath.name)
        if meta.get("is_baseline"):
            continue
        if meta.get("ssp") != TARGET_SSP or meta.get("period") != TARGET_PERIOD:
            continue
        hm = meta["hydro_model"]
        if hm not in baseline_stats:
            continue
        try:
            flow = load_flow_series(dpath, metric)
        except (FileNotFoundError, ValueError) as e:
            print(f"  ERROR {dpath.name}: {e}")
            continue
        mean_annual = flow.resample("YE").sum().mean()
        pct_change = (
            (mean_annual - baseline_stats[hm]["mean_annual_mgd"])
            / baseline_stats[hm]["mean_annual_mgd"] * 100.0
        )
        bin_match = map_to_config_bin(pct_change)
        records.append({
            "dataset": dpath.name,
            "hydro_model": hm,
            "gcm": meta["gcm"],
            "ssp": meta["ssp"],
            "period": meta["period"],
            "streamflow_metric": metric,
            "mean_annual_flow_mgd": mean_annual,
            "pct_change_vs_baseline": pct_change,
            "streamflow_bin_id": bin_match["id"],
            "streamflow_bin_label": bin_match["label"],
            "bin_pct_change_center": bin_match["pct_change"] * 100.0,
        })

    df = pd.DataFrame(records).sort_values("pct_change_vs_baseline").reset_index(drop=True)
    if df.empty:
        return df

    bin_counts = df.groupby("streamflow_bin_id").size().rename("n_projections")
    bin_weights = (bin_counts / len(df)).rename("bin_weight")
    df = df.join(bin_counts, on="streamflow_bin_id")
    df = df.join(bin_weights, on="streamflow_bin_id")
    return df


def main() -> None:
    out_dir = Path(__file__).parent
    all_dfs = []
    for metric in METRICS:
        print(f"\n{'='*60}\nProcessing metric: {metric}\n{'='*60}")
        df = process_metric(metric)
        if df.empty:
            print(f"No records for {metric}")
            continue
        path = out_dir / f"cmip6_cell_weights_{metric}.csv"
        df.to_csv(path, index=False)
        print(f"Saved: {path} ({len(df)} projections)")
        all_dfs.append(df)

        zero = [b["id"] for b in STREAMFLOW_BINS if b["id"] not in df["streamflow_bin_id"].unique()]
        if zero:
            print(f"  Zero-weight bins: {zero}")

    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        combined.to_csv(out_dir / "cmip6_cell_weights_combined.csv", index=False)
        # Legacy filename = montague (primary for RQ3)
        montague = combined[combined["streamflow_metric"] == "montague"]
        if not montague.empty:
            montague.drop(columns=["streamflow_metric"]).to_csv(
                out_dir / "cmip6_cell_weights.csv", index=False
            )
        print(f"\nSaved combined + legacy cmip6_cell_weights.csv (montague primary)")


if __name__ == "__main__":
    main()

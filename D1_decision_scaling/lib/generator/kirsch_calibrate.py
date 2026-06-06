"""
D1 — Calibrate Kirsch-Nowak generator to historical DRB streamflows.

Fits:
  - KirschGenerator  : multisite monthly log-normal VAR model
  - NowakDisaggregator : monthly-to-daily disaggregation

Both from the `synhydro` package (Reed Research Group standard).
See stochastic_experiment/methods/generate.py for the SEE calibration pattern (DO NOT COPY).

Usage
-----
    python kirsch_calibrate.py \
        --inflow-dataset pub_nhmv10_BC_withObsScaled \
        --outdir generator/fitted_model

Output
------
    generator/fitted_model/kirsch_baseline.pkl    — fitted KirschGenerator
    generator/fitted_model/nowak_disagg.pkl       — fitted NowakDisaggregator
    generator/fitted_model/calibration_summary.csv

Decision blocker: Scott must choose Kirsch vs Gosney before this runs.
See committee/D1_D4_experimental_plans.md Decision D1-1.
"""

import argparse
import pickle
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from synhydro.kirsch import KirschGenerator
    from synhydro.nowak import NowakDisaggregator
except ImportError:
    raise ImportError(
        "synhydro not installed.  Install from Reed Research Group repo:\n"
        "  pip install git+https://github.com/reedgroup/synhydro.git\n"
        "(confirm package name/URL with lab before installing)"
    )

# ---------------------------------------------------------------------------
# Calibration period — match historical Pywr-DRB input dataset
# ---------------------------------------------------------------------------
BASELINE_DATASET: str = "pub_nhmv10_BC_withObsScaled"  # naturalized flows
CALIB_START: str = "1945-01-01"
CALIB_END:   str = "2005-12-31"

# Pywr-DRB inflow nodes used as generator sites
# These must match the column names in the inflow input CSV.
# TODO: confirm against pywrdrb.pywr_drb_node_data node list.
INFLOW_SITES: list[str] = [
    "cannonsville",
    "pepacton",
    "neversink",
    "delMontague",        # Montague — combined upstream; used for streamflow axis binning
    "beltzvilleCombined", # LB tributary
    "blueMarsh",          # LB tributary
    "fewalter",           # LB tributary
]
# NOTE: Kirsch-Nowak is a multisite model — all sites are fitted jointly to
# preserve cross-site correlations. Do not fit each site independently.

# Streamflow axis binning target site (Axis 1 in config.py)
# This is the site whose mean annual flow percentile defines scenario cells.
# Choice: "delMontague" (Trenton driver) or "nyc_aggregate" (sum of 3 NYC tributaries)
# Pending Scott's decision D1-2.
STREAMFLOW_AXIS_SITE: str = "delMontague"   # TODO: confirm with Scott


def load_historical_flows(inflow_dataset: str) -> pd.DataFrame:
    """
    Load historical naturalized flows from Pywr-DRB input data.

    Returns DataFrame: DatetimeIndex, columns = INFLOW_SITES (cfs or MGD).
    TODO: confirm units and conversion factor.
    """
    try:
        import pywrdrb
        flow_df = pywrdrb.utils.load_inflows(
            inflow_type=inflow_dataset,
            nodes=INFLOW_SITES,
        )
    except Exception as e:
        raise RuntimeError(
            f"Could not load {inflow_dataset} from pywrdrb.utils.load_inflows(): {e}\n"
            "Confirm pywrdrb API for loading input datasets."
        ) from e
    return flow_df.loc[CALIB_START:CALIB_END]


def calibrate(flow_df: pd.DataFrame, outdir: Path) -> tuple:
    """
    Fit KirschGenerator and NowakDisaggregator to historical flows.

    Parameters
    ----------
    flow_df : pd.DataFrame
        Daily flows, DatetimeIndex, columns = INFLOW_SITES.
    outdir : Path
        Directory for fitted model objects.

    Returns
    -------
    (kirsch_gen, nowak_disagg)
    """
    outdir.mkdir(parents=True, exist_ok=True)

    print("Fitting KirschGenerator (monthly VAR model)...")
    kirsch_gen = KirschGenerator(debug=False, generate_using_log_flow=True)
    kirsch_gen.preprocessing(flow_df)
    kirsch_gen.fit()

    print("Fitting NowakDisaggregator (monthly → daily)...")
    nowak_disagg = NowakDisaggregator(debug=False)
    nowak_disagg.preprocessing(flow_df)
    nowak_disagg.fit()

    # Save
    kirsch_path = outdir / "kirsch_baseline.pkl"
    nowak_path  = outdir / "nowak_disagg.pkl"
    with open(kirsch_path, "wb") as f:
        pickle.dump(kirsch_gen, f)
    with open(nowak_path, "wb") as f:
        pickle.dump(nowak_disagg, f)
    print(f"  Saved {kirsch_path}")
    print(f"  Saved {nowak_path}")

    # Summary stats
    summary = pd.DataFrame({
        "site": INFLOW_SITES,
        "mean_annual_flow": [
            flow_df[site].resample("YE").sum().mean() for site in INFLOW_SITES
        ],
    })
    summary.to_csv(outdir / "calibration_summary.csv", index=False)
    print(f"  Saved {outdir / 'calibration_summary.csv'}")

    return kirsch_gen, nowak_disagg


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--inflow-dataset", default=BASELINE_DATASET)
    ap.add_argument("--outdir", default="generator/fitted_model")
    args = ap.parse_args()

    flow_df = load_historical_flows(args.inflow_dataset)
    print(f"Historical flows: {flow_df.index[0].date()} to {flow_df.index[-1].date()}, "
          f"{len(flow_df.columns)} sites")
    calibrate(flow_df, Path(args.outdir))
    print("\nCalibration complete.  Next: run kirsch_generate.py")

"""
Shared Kirsch-Nowak synthetic DRB flow generation for D1 and D4.

Calibrates on pub_nhmv10_BC_withObsScaled (1946–2005) at 7 major sites;
fills 24 minor sites via annual block bootstrap.  Each realization spans
1945-01-01 → 2023-12-31 (28854 days, 31 pywrdrb nodes).
"""

from __future__ import annotations

import copy
import logging
import pickle
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

try:
    from synhydro.methods.generation.hybrid.kirsch import KirschGenerator
    from synhydro.methods.disaggregation.temporal.nowak import NowakDisaggregator
except ImportError as e:
    raise ImportError(
        "synhydro not installed.  Install:\n"
        "  pip install git+https://github.com/TrevorJA/SynHydro.git"
    ) from e

import pywrdrb
from pywrdrb_utils.amestoy_io import AMESTOY_NODE_NAMES, AMESTOY_START_DATE, AMESTOY_END_DATE

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

KIRSCH_SITES: list[str] = [
    "cannonsville",
    "pepacton",
    "neversink",
    "delMontague",
    "beltzvilleCombined",
    "blueMarsh",
    "fewalter",
]

BOOTSTRAP_SITES: list[str] = [n for n in AMESTOY_NODE_NAMES if n not in KIRSCH_SITES]

CALIB_START: str = "1946-01-01"
CALIB_END: str = "2005-12-31"
SIM_YEARS: int = 79
SYN_START: str = AMESTOY_START_DATE
SYN_END: str = AMESTOY_END_DATE
SYN_N_DAYS: int = len(pd.date_range(SYN_START, SYN_END, freq="D"))


def get_historical_inflows() -> pd.DataFrame:
    """Load pub_nhmv10_BC_withObsScaled catchment inflows (31 nodes, MGD)."""
    pn_config = pywrdrb.get_pn_config()
    flow_key = "flows/pub_nhmv10_BC_withObsScaled"
    if flow_key not in pn_config:
        raise KeyError(f"pywrdrb path navigator missing '{flow_key}'")
    csv_path = Path(pn_config[flow_key]) / "catchment_inflow_mgd.csv"
    if not csv_path.exists():
        raise FileNotFoundError(f"Historical inflow CSV not found: {csv_path}")
    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    for node in AMESTOY_NODE_NAMES:
        if node not in df.columns:
            logger.warning("Node '%s' missing — filling 0.0", node)
            df[node] = 0.0
    return df[list(AMESTOY_NODE_NAMES)]


def calibrate(Q_hist: pd.DataFrame, outdir: Path) -> tuple[KirschGenerator, NowakDisaggregator]:
    """Fit KirschGenerator + NowakDisaggregator; save pkls to outdir."""
    outdir.mkdir(parents=True, exist_ok=True)
    Q_cal = (
        Q_hist.loc[CALIB_START:CALIB_END, KIRSCH_SITES]
        .replace(0, np.nan)
    )
    Q_cal = Q_cal.fillna(Q_cal.median()).fillna(1.0)

    kirsch_gen = KirschGenerator(generate_using_log_flow=True, debug=False)
    kirsch_gen.preprocessing(Q_cal)
    kirsch_gen.fit()

    nowak_disagg = NowakDisaggregator(n_neighbors=5, debug=False)
    nowak_disagg.preprocessing(Q_cal)
    nowak_disagg.fit()

    kirsch_path = outdir / "kirsch_fitted.pkl"
    nowak_path = outdir / "nowak_fitted.pkl"
    with open(kirsch_path, "wb") as f:
        pickle.dump(kirsch_gen, f)
    with open(nowak_path, "wb") as f:
        pickle.dump(nowak_disagg, f)
    return kirsch_gen, nowak_disagg


def load_fitted_models(outdir: Path) -> tuple[KirschGenerator, NowakDisaggregator]:
    """Load persisted fitted models."""
    kirsch_path = outdir / "kirsch_fitted.pkl"
    nowak_path = outdir / "nowak_fitted.pkl"
    if not kirsch_path.exists() or not nowak_path.exists():
        raise FileNotFoundError(f"Fitted models not found in {outdir}")
    with open(kirsch_path, "rb") as f:
        kirsch_gen = pickle.load(f)
    with open(nowak_path, "rb") as f:
        nowak_disagg = pickle.load(f)
    return kirsch_gen, nowak_disagg


def shift_kirsch_means(kirsch_gen: KirschGenerator, pct_change: float) -> KirschGenerator:
    """
    Return deep copy of generator with monthly means shifted by pct_change.

    synhydro 0.0.2 stores log-flow means in ``mean_period`` (DataFrame) and
    ``fitted_params_['means_']``.  A uniform multiplicative shift in linear
    space is additive in log space:  log(m × (1+p)) = log(m) + log(1+p).
    """
    if pct_change == 0.0:
        return kirsch_gen
    shifted = copy.deepcopy(kirsch_gen)
    delta = float(np.log(1.0 + pct_change))
    if hasattr(shifted, "mean_period") and shifted.mean_period is not None:
        shifted.mean_period = shifted.mean_period + delta
    fp = getattr(shifted, "fitted_params_", None)
    if isinstance(fp, dict) and "means_" in fp:
        shifted.fitted_params_ = copy.deepcopy(fp)
        shifted.fitted_params_["means_"] = fp["means_"] + delta
    return shifted


def _bootstrap_minor_sites(Q_hist: pd.DataFrame, n_years: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    Q_bootstrap = Q_hist.loc[CALIB_START:CALIB_END, BOOTSTRAP_SITES]
    available_years = sorted(set(Q_bootstrap.index.year))
    sampled_years = rng.choice(available_years, size=n_years, replace=True)
    year_blocks = [
        Q_bootstrap[Q_bootstrap.index.year == yr].copy() for yr in sampled_years
    ]
    resampled = pd.concat(year_blocks, ignore_index=True)
    if len(resampled) < SYN_N_DAYS:
        extra = SYN_N_DAYS - len(resampled)
        last_yr = available_years[-1]
        pad = Q_bootstrap[Q_bootstrap.index.year == last_yr].iloc[:extra]
        resampled = pd.concat([resampled, pad], ignore_index=True)
    resampled = resampled.iloc[:SYN_N_DAYS]
    syn_dates = pd.date_range(SYN_START, periods=SYN_N_DAYS, freq="D")
    resampled.index = syn_dates
    resampled.index.name = "datetime"
    return resampled


def generate_realization(
    kirsch_gen: KirschGenerator,
    nowak_disagg: NowakDisaggregator,
    Q_hist: pd.DataFrame,
    seed: int = 42,
    pct_change: float = 0.0,
) -> pd.DataFrame:
    """
    Generate one synthetic daily flow DataFrame (28854 × 31, MGD).

    Parameters
    ----------
    pct_change : float
        Fractional shift applied to Kirsch monthly means (D1 streamflow bins).
    """
    gen = shift_kirsch_means(kirsch_gen, pct_change) if pct_change != 0.0 else kirsch_gen
    kirsch_seed = seed
    nowak_seed = seed + 1
    bootstrap_seed = seed + 2

    monthly_ensemble = gen.generate(n_realizations=1, n_years=SIM_YEARS, seed=kirsch_seed)
    daily_ensemble = nowak_disagg.disaggregate(monthly_ensemble, seed=nowak_seed)
    df_kirsch = daily_ensemble.data_by_realization[0]

    syn_dates = pd.date_range(SYN_START, periods=SYN_N_DAYS, freq="D")
    if len(df_kirsch) < SYN_N_DAYS:
        extra = SYN_N_DAYS - len(df_kirsch)
        pad = pd.DataFrame(
            np.tile(df_kirsch.iloc[-1].values, (extra, 1)),
            columns=df_kirsch.columns,
        )
        df_kirsch = pd.concat([df_kirsch, pad], ignore_index=True)
    df_kirsch = df_kirsch.iloc[:SYN_N_DAYS].copy()
    df_kirsch.index = syn_dates
    df_kirsch.index.name = "datetime"

    df_minor = _bootstrap_minor_sites(Q_hist, SIM_YEARS, seed=bootstrap_seed)
    df_full = pd.concat([df_kirsch, df_minor], axis=1)[list(AMESTOY_NODE_NAMES)]
    return df_full.clip(lower=0.0)


def generate_realizations_to_dir(
    kirsch_gen: KirschGenerator,
    nowak_disagg: NowakDisaggregator,
    Q_hist: pd.DataFrame,
    n_realizations: int,
    outdir: Path,
    master_seed: int = 42,
    pct_change: float = 0.0,
    skip_existing: bool = True,
) -> pd.DataFrame:
    """Generate n realizations; save as realization_{r:03d}.parquet. Returns log DataFrame."""
    outdir.mkdir(parents=True, exist_ok=True)
    log_rows = []
    for r in range(n_realizations):
        out_path = outdir / f"realization_{r:03d}.parquet"
        if skip_existing and out_path.exists():
            log_rows.append({"realization": r, "status": "skipped", "path": str(out_path)})
            continue
        seed = master_seed + r * 1000
        df = generate_realization(
            kirsch_gen, nowak_disagg, Q_hist, seed=seed, pct_change=pct_change
        )
        df.to_parquet(out_path)
        log_rows.append({"realization": r, "status": "ok", "path": str(out_path)})
    return pd.DataFrame(log_rows)


def validate_against_historical(
    kirsch_gen: KirschGenerator,
    nowak_disagg: NowakDisaggregator,
    Q_hist: pd.DataFrame,
    n_samples: int = 20,
    seed: int = 42,
) -> pd.DataFrame:
    """
    Compare synthetic vs historical statistics for Kirsch sites.

    Returns long-form DataFrame: site, metric, historical, synthetic.
    """
    Q_cal = Q_hist.loc[CALIB_START:CALIB_END, KIRSCH_SITES]
    hist_annual = Q_cal.resample("YE").sum().mean()

    syn_annuals = []
    for i in range(n_samples):
        df = generate_realization(kirsch_gen, nowak_disagg, Q_hist, seed=seed + i * 100)
        syn_annuals.append(df[KIRSCH_SITES].resample("YE").sum().mean())
    syn_mean = pd.concat(syn_annuals, axis=1).mean(axis=1)

    rows = []
    for site in KIRSCH_SITES:
        rows.append({
            "site": site,
            "metric": "mean_annual_mgd",
            "historical": float(hist_annual[site]),
            "synthetic": float(syn_mean[site]),
            "rel_error": float((syn_mean[site] - hist_annual[site]) / hist_annual[site]),
        })
    return pd.DataFrame(rows)

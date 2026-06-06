"""
Post-hoc SalinityLSTM — same Mode A physics, faster than in-model coupling.

Pywr-DRB runs without SalinityModelLSTM; this module replays Trenton/Schuylkill
flows through SalinityLSTMModel after the simulation (one pass, no LP overhead).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

from salinity_paths import build_salinity_model_options, resolve_pywrdrb_ml_plugin_path


def predict_salt_front_series(
    trenton_flow: pd.Series,
    schuylkill_flow: pd.Series,
    start_date: str,
    end_date: str,
) -> pd.Series:
    """
    Daily salt_front_location_mu (river miles) aligned to trenton_flow index.

    Uses previous-day flows to match pywrdrb UpdateSaltFrontLocation + SalinityModelLSTM.
    """
    plugin = resolve_pywrdrb_ml_plugin_path()
    sys.path.insert(1, str(plugin))
    from src.lstm_model import SalinityLSTMModel

    opts = build_salinity_model_options(start_date, end_date)
    ml = SalinityLSTMModel(
        model_salinity=opts["model_salinity"],
        start_date=start_date,
        end_date=end_date,
        Q_Trenton_lstm_var_name=opts["Q_Trenton_lstm_var_name"],
        Q_Schuylkill_lstm_var_name=opts["Q_Schuylkill_lstm_var_name"],
        debug=False,
        disable_tqdm=True,
    )
    ml.load_data()

    idx = trenton_flow.index
    n = len(idx)
    out = np.full(n, np.nan, dtype=float)

    # t=0: baseline from loaded X; subsequent steps use prior-day simulated flows
    for t in range(1, n):
        q_t = float(trenton_flow.iloc[t - 1])
        q_s = float(schuylkill_flow.iloc[t - 1]) if t - 1 < len(schuylkill_flow) else float(
            schuylkill_flow.iloc[min(t - 1, len(schuylkill_flow) - 1)]
        )
        ml.update(t, Q_Trenton=q_t, Q_Schuylkill=q_s, asycronized_update=False)
        out[t] = ml.sf_mu

    if n > 0 and np.isnan(out[0]):
        out[0] = ml.sf_mu

    return pd.Series(out, index=idx, name="salt_front_rm")

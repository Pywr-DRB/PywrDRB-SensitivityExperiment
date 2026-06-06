"""
I/O utilities for the Amestoy et al. (2025) 1000-member streamflow ensemble.

HDF5 structure (catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5):
    /{node_name}/{str(member_id)}  →  np.ndarray shape (28854,)  [MGD]

where node_name is a pywrdrb inflow node (e.g. 'cannonsville', 'delTrenton', ...),
member_id is an integer 0–999, and the array contains 28,854 daily flow values
spanning 1945-01-01 → 2023-12-31.

This structure was confirmed by direct h5py inspection on 2026-05-31.

Reference
---------
Amestoy, T.J. et al. (2025). A 1000-member stochastic reconstruction of
Delaware River Basin streamflow (1945–2023). Zenodo.
DOI 10.5281/zenodo.15101164
"""

from __future__ import annotations

from pathlib import Path

import h5py
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Confirmed constants (verified by h5py inspection 2026-05-31)
# ---------------------------------------------------------------------------

AMESTOY_START_DATE: str = "1945-01-01"
AMESTOY_END_DATE: str   = "2023-12-31"
AMESTOY_N_DAYS: int     = 28_854          # len(pd.date_range(start, end, freq='D'))
AMESTOY_N_MEMBERS: int  = 1_000           # member IDs: 0 – 999

# pywrdrb inflow node names present in the HDF5 (31 nodes)
# Values match columns in pub_nhmv10_BC_withObsScaled/gage_flow_mgd.csv
AMESTOY_NODE_NAMES: tuple = (
    "01417000", "01425000", "01433500", "01436000", "01447800",
    "01449800", "01463620", "01470960",
    "assunpink", "beltzvilleCombined", "blueMarsh", "cannonsville",
    "delDRCanal", "delLordville", "delMontague", "delTrenton",
    "fewalter", "greenLane", "hopatcong", "merrillCreek",
    "mongaupeCombined", "neversink", "nockamixon", "ontelaunee",
    "outletAssunpink", "outletSchuylkill", "pepacton", "prompton",
    "shoholaMarsh", "stillCreek", "wallenpaupack",
)


def load_member_flows(
    inputs_hdf5: Path,
    member_id: int,
    nodes: tuple = AMESTOY_NODE_NAMES,
    start_date: str = AMESTOY_START_DATE,
    n_days: int = AMESTOY_N_DAYS,
) -> pd.DataFrame:
    """
    Load one ensemble member's daily inflow time series from the Amestoy inputs HDF5.

    Parameters
    ----------
    inputs_hdf5 : Path
        Absolute path to catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5.
    member_id : int
        0-based ensemble member index (0 – 999).
    nodes : tuple, optional
        Node names to include (default: all 31 AMESTOY_NODE_NAMES).
    start_date : str, optional
        ISO date string for day 0 of the array (default: '1945-01-01').
    n_days : int, optional
        Total number of timesteps (default: 28,854 = 1945-01-01 → 2023-12-31).

    Returns
    -------
    pd.DataFrame
        DatetimeIndex (daily), columns = node names, values in MGD.
        Ready to pass directly to ``pywrdrb_utils.run_model.run_single(flow_df=...)``.

    Raises
    ------
    FileNotFoundError
        If ``inputs_hdf5`` does not exist.
    KeyError
        If ``member_id`` (as string) is not present in a node's group.
    ValueError
        If the loaded array length does not match ``n_days``.

    Examples
    --------
    >>> from shared.pywrdrb_utils.amestoy_io import load_member_flows
    >>> from pathlib import Path
    >>> flow_df = load_member_flows(
    ...     Path("~/data/amestoy_2026/pywrdrb_inputs/historic_ensembles/"
    ...          "catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5"),
    ...     member_id=42,
    ... )
    >>> flow_df.shape
    (28854, 31)
    >>> flow_df.index[0], flow_df.index[-1]
    (Timestamp('1945-01-01'), Timestamp('2023-12-31'))
    """
    if not inputs_hdf5.exists():
        raise FileNotFoundError(
            f"Amestoy inputs HDF5 not found: {inputs_hdf5}\n"
            "Did you unzip pywrdrb_data.zip and set the correct path?"
        )

    date_index = pd.date_range(start_date, periods=n_days, freq="D")
    mid_str = str(member_id)

    data_dict: dict[str, np.ndarray] = {}
    with h5py.File(inputs_hdf5, "r") as f:
        for node in nodes:
            if node not in f:
                # Node not in this file version — skip silently; pywrdrb handles missing
                continue
            if mid_str not in f[node]:
                raise KeyError(
                    f"member_id={member_id} (key '{mid_str}') not found in "
                    f"HDF5 group '{node}'.\n"
                    f"Available member keys: {list(f[node].keys())[:10]} ..."
                )
            arr = np.asarray(f[node][mid_str])
            if len(arr) != n_days:
                raise ValueError(
                    f"Node '{node}' member {member_id}: "
                    f"expected {n_days} timesteps, got {len(arr)}."
                )
            data_dict[node] = arr

    flow_df = pd.DataFrame(data_dict, index=date_index)
    flow_df.index.name = "datetime"
    return flow_df

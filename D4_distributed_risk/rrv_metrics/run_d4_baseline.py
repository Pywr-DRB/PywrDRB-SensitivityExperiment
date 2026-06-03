"""
D4 Cooperative Risk Attribution — Baseline run with Amestoy 1000-member ensemble.

Steps:
1. Load 1000-member streamflow reconstruction (Amestoy 2026, Zenodo)
2. Run Pywr-DRB with current DRBC rules across all members
3. Compute per-party RRV metrics
4. Decompose into NYC-limited vs LB-limited regimes

Status: SCAFFOLD — requires lower_basin_ffmp drought-stage switching before running.
Requires: Amestoy 1000-member ensemble download from Zenodo.

TODO before running:
- [ ] Complete lower_basin_ffmp Gap 1 (LB drought state variable)
- [ ] Download Amestoy 1000-member reconstruction from Zenodo
- [ ] Confirm D4 committee endorsement (five-party vs two-subsystem framing)
- [ ] Check no overlap with Trevor's dissertation work
"""

import numpy as np
import pandas as pd
from pathlib import Path

# --- Paths ---
PYWRDRB_ROOT = Path.home() / "Research/PywrDRB_master/Pywr-DRB"
DATA_ROOT = Path.home() / "DRB_reservoir_observations_package"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# TODO: Set path to Amestoy 1000-member reconstruction after Zenodo download
AMESTOY_ENSEMBLE_PATH = Path.home() / "data/amestoy_2026_1000member_reconstruction"

# --- Configuration ---
# Framing choice: set to "two_subsystem" initially (immediately executable)
# Change to "five_party" after committee confirms
FRAMING = "two_subsystem"  # or "five_party"

# LB conservation pool threshold (combined blueMarsh + beltzville)
# blueMarsh usable: 7450 MG; beltzville usable: 13500 MG; combined: 20950 MG
# Conservation pool at ~69% blueMarsh + ~73.7% beltzville
LB_CONSERVATION_POOL_MGD = 0.5 * 20950  # placeholder — adjust from Water Code

# IERQ exhaustion threshold
IERQ_MAX_BG = 6.09  # BG/yr = 6090 MG/yr
IERQ_EXHAUSTION_THRESHOLD_MG = 50  # near-zero threshold


def load_amestoy_ensemble():
    """Load 1000-member streamflow reconstruction."""
    # TODO: implement once Zenodo data is downloaded
    # Expected format: dict of DataFrames, one per member
    # Each DataFrame: DatetimeIndex, columns = Pywr-DRB node names
    raise NotImplementedError("Download Amestoy ensemble from Zenodo first")


def run_pywrdrb_ensemble(ensemble_flows):
    """
    Run Pywr-DRB across all ensemble members with current DRBC operating rules.

    Returns dict: member_id -> simulation output DataFrame
    """
    import pywrdrb
    # TODO: implement ensemble run
    # Loop over members, set streamflow input, run model, collect outputs
    pass


def compute_per_party_rrv(simulation_outputs):
    """
    Compute Hashimoto (1982) RRV metrics for each Decree party.

    Returns DataFrame with columns:
    [member_id, party, reliability, resilience, vulnerability, regime]
    """
    results = []

    for member_id, outputs in simulation_outputs.items():
        # Delaware (DE): Trenton flow reliability
        trenton_flow = outputs["del_trenton_flow"]
        trenton_target = outputs["trenton_target"]
        de_reliability = np.sum(trenton_flow >= trenton_target) / len(trenton_flow)
        de_vulnerability = np.max(np.maximum(trenton_target - trenton_flow, 0))

        # NYC: IERQ exhaustion days
        ierq_remaining = outputs["ierq_bank_remaining"]
        nyc_exhaustion_days = np.sum(ierq_remaining < IERQ_EXHAUSTION_THRESHOLD_MG)

        # PA: LB storage depletion
        lb_storage = outputs["blueMarsh_volume"] + outputs["beltzville_volume"]
        pa_depletion_days = np.sum(lb_storage < LB_CONSERVATION_POOL_MGD)

        # NY: Montague flow reliability
        montague_flow = outputs["del_montague_flow"]
        montague_target = outputs["montague_target"]
        ny_reliability = np.sum(montague_flow >= montague_target) / len(montague_flow)

        # NJ: diversion restriction days (TODO: identify correct output variable)
        # nj_restriction_days = ...

        # Regime attribution
        # NYC-limited: IERQ exhausted before LB hits conservation pool
        ierq_first_exhaustion = _first_occurrence(ierq_remaining < IERQ_EXHAUSTION_THRESHOLD_MG)
        lb_first_depletion = _first_occurrence(lb_storage < LB_CONSERVATION_POOL_MGD)

        if ierq_first_exhaustion is None and lb_first_depletion is None:
            regime = "no_failure"
        elif ierq_first_exhaustion is None:
            regime = "lb_limited"
        elif lb_first_depletion is None:
            regime = "nyc_limited"
        elif ierq_first_exhaustion <= lb_first_depletion:
            regime = "nyc_limited"
        else:
            regime = "lb_limited"

        results.append({
            "member_id": member_id,
            "de_reliability": de_reliability,
            "de_vulnerability": de_vulnerability,
            "nyc_exhaustion_days": nyc_exhaustion_days,
            "pa_depletion_days": pa_depletion_days,
            "ny_reliability": ny_reliability,
            "regime": regime,
        })

    return pd.DataFrame(results)


def _first_occurrence(boolean_series):
    """Return index of first True in boolean series, or None."""
    idx = np.where(boolean_series)[0]
    return idx[0] if len(idx) > 0 else None


if __name__ == "__main__":
    print("D4 Baseline Run — Cooperative Risk Attribution")
    print(f"Framing: {FRAMING}")
    print("\nRequired before running:")
    print("  1. Complete lower_basin_ffmp.py LB drought stage switching")
    print("  2. Download Amestoy 1000-member ensemble from Zenodo")
    print("  3. Confirm D4 endorsement from committee (May 30)")
    print("\nScaffold ready. Implement load_amestoy_ensemble() and run_pywrdrb_ensemble() next.")

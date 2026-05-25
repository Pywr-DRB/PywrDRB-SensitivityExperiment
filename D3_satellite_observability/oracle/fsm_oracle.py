"""
D3 Satellite Observability — FSM Oracle

Finite-state machine oracle for DRB lower basin reservoir operations.
~150 lines, zero fitted parameters. Institutionally grounded from Water Code §2.5.5.

Used as ground truth in the controlled synthetic experiment:
- Synthetic satellite observations (with known degradation) are passed to the inference pipeline
- Inferred operating rules are compared against this FSM oracle
- Uncertainty propagation: 500 storage estimate draws → 500 inferred rules → Trenton risk envelope

Status: SCAFFOLD — activate after committee confirms FSM oracle family (May 30).

Reference: Water Code §2.5.5; DRBC Operating Tables
"""

import numpy as np
from enum import IntEnum


class DroughtStage(IntEnum):
    NORMAL = 0
    STAGE_1 = 1
    STAGE_2 = 2
    STAGE_3 = 3
    STAGE_4 = 4
    STAGE_5 = 5


class Season(IntEnum):
    WINTER = 0   # Dec–Feb
    SPRING = 1   # Mar–May
    SUMMER = 2   # Jun–Aug
    FALL = 3     # Sep–Nov


# Storage thresholds (as fraction of usable pool) for each drought stage
# Derived from Water Code §2.5.5 priority staging
# These are the LOWER BOUNDS of each stage — being ABOVE threshold = normal
DROUGHT_STAGE_THRESHOLDS = {
    "beltzvilleCombined": {
        DroughtStage.STAGE_1: 0.737,
        DroughtStage.STAGE_3: 0.380,
        DroughtStage.STAGE_5: 0.034,
    },
    "blueMarsh": {
        DroughtStage.STAGE_1: 0.689,
        DroughtStage.STAGE_4: 0.368,
        DroughtStage.STAGE_5: 0.130,
    },
}

# Release fractions by (drought_stage, season) — fraction of conservation release
# These represent the deterministic lookup table of the FSM oracle
# Entries based on Water Code Table 4 and operational patterns
# TODO: calibrate against observed release data (Research/Baseline_Policy_Optimization/)
RELEASE_LOOKUP = {
    # (stage, season): release_fraction_of_conservation_release
    (DroughtStage.NORMAL, Season.WINTER): 1.0,
    (DroughtStage.NORMAL, Season.SPRING): 1.0,
    (DroughtStage.NORMAL, Season.SUMMER): 1.0,
    (DroughtStage.NORMAL, Season.FALL): 1.0,
    (DroughtStage.STAGE_1, Season.WINTER): 0.85,
    (DroughtStage.STAGE_1, Season.SPRING): 0.90,
    (DroughtStage.STAGE_1, Season.SUMMER): 0.80,
    (DroughtStage.STAGE_1, Season.FALL): 0.85,
    (DroughtStage.STAGE_3, Season.WINTER): 0.60,
    (DroughtStage.STAGE_3, Season.SPRING): 0.65,
    (DroughtStage.STAGE_3, Season.SUMMER): 0.55,
    (DroughtStage.STAGE_3, Season.FALL): 0.60,
    (DroughtStage.STAGE_5, Season.WINTER): 0.40,
    (DroughtStage.STAGE_5, Season.SPRING): 0.45,
    (DroughtStage.STAGE_5, Season.SUMMER): 0.35,
    (DroughtStage.STAGE_5, Season.FALL): 0.40,
}

# Conservation releases (MGD) from Water Code Table 4
CONSERVATION_RELEASES_MGD = {
    "blueMarsh": 50 * 0.6463,      # 50 cfs → MGD
    "beltzvilleCombined": 35 * 0.6463,  # 35 cfs → MGD
    "nockamixon": 11 * 0.6463,
}


class LowerBasinFSMOracle:
    """
    Finite-state machine oracle for lower basin reservoir operations.

    Maps (storage_fraction, month) → release_mgd using deterministic lookup table.
    Represents the Water Code operating rules without any fitted parameters.

    This is the 'ground truth' against which satellite-derived inferred rules are compared.
    """

    def __init__(self, reservoir: str):
        """
        Parameters
        ----------
        reservoir : str
            One of: 'blueMarsh', 'beltzvilleCombined', 'nockamixon'
        """
        assert reservoir in CONSERVATION_RELEASES_MGD, f"Unknown reservoir: {reservoir}"
        self.reservoir = reservoir
        self.conservation_release = CONSERVATION_RELEASES_MGD[reservoir]
        self.thresholds = DROUGHT_STAGE_THRESHOLDS.get(reservoir, {})

    def _storage_to_drought_stage(self, storage_fraction: float) -> DroughtStage:
        """Determine drought stage from storage fraction (0–1)."""
        if not self.thresholds:
            return DroughtStage.NORMAL

        # Check stages from deepest to shallowest — return deepest active
        for stage in [DroughtStage.STAGE_5, DroughtStage.STAGE_3, DroughtStage.STAGE_1]:
            threshold = self.thresholds.get(stage)
            if threshold is not None and storage_fraction < threshold:
                return stage
        return DroughtStage.NORMAL

    def _month_to_season(self, month: int) -> Season:
        """Convert month (1–12) to Season enum."""
        if month in [12, 1, 2]:
            return Season.WINTER
        elif month in [3, 4, 5]:
            return Season.SPRING
        elif month in [6, 7, 8]:
            return Season.SUMMER
        else:
            return Season.FALL

    def get_release(self, storage_fraction: float, month: int) -> float:
        """
        Compute release from storage fraction and month.

        Parameters
        ----------
        storage_fraction : float
            Storage as fraction of usable pool (0–1)
        month : int
            Calendar month (1–12)

        Returns
        -------
        float
            Release in MGD
        """
        stage = self._storage_to_drought_stage(storage_fraction)
        season = self._month_to_season(month)

        # Find release fraction — use closest available stage if exact not found
        key = (stage, season)
        if key not in RELEASE_LOOKUP:
            # Fall back to nearest stage
            available_stages = [s for (s, ss) in RELEASE_LOOKUP if ss == season]
            closest = min(available_stages, key=lambda s: abs(int(s) - int(stage)))
            key = (closest, season)

        release_fraction = RELEASE_LOOKUP[key]
        return release_fraction * self.conservation_release

    def simulate(self, storage_fractions: np.ndarray, months: np.ndarray) -> np.ndarray:
        """
        Simulate releases for a full time series.

        Parameters
        ----------
        storage_fractions : np.ndarray, shape (T,)
        months : np.ndarray, shape (T,), values 1–12

        Returns
        -------
        np.ndarray, shape (T,) — releases in MGD
        """
        return np.array([
            self.get_release(s, m)
            for s, m in zip(storage_fractions, months)
        ])


if __name__ == "__main__":
    # Quick sanity check
    oracle = LowerBasinFSMOracle("blueMarsh")

    test_cases = [
        (0.90, 7, "Normal summer → full conservation release"),
        (0.60, 7, "Stage 1 summer → reduced release"),
        (0.25, 1, "Stage 3 winter → further reduced"),
        (0.05, 8, "Stage 5 summer → minimum release"),
    ]

    for storage_frac, month, desc in test_cases:
        release = oracle.get_release(storage_frac, month)
        stage = oracle._storage_to_drought_stage(storage_frac)
        print(f"{desc}")
        print(f"  storage={storage_frac:.0%}, month={month}, stage={stage.name}")
        print(f"  release={release:.1f} MGD (conservation={oracle.conservation_release:.1f})")
        print()

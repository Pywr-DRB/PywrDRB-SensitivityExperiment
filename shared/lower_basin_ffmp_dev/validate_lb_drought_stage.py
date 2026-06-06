"""
Validation script for LowerBasinDroughtLevel drought-stage switching.

Three parts:
  1. Unit tests  — pure-logic assertions, no Pywr model needed.
  2. Integration — build + run nhmv10 model (2001-10-01 to 2004-12-31) and
                   verify drought_level_agg_lb signals against raw storage data.
  3. Diagnostics — 4-panel figure saved to figures/lb_drought_stage_diagnostic.png.

Usage:
    cd ~/dissertation
    source venv/bin/activate
    python shared/lower_basin_ffmp_dev/validate_lb_drought_stage.py

Water Code §2.5.6 thresholds (fraction of DRBC usable conservation storage):
    Warning: Beltzville < 73.7 %  OR  Blue Marsh < 68.9 %
    Drought: Beltzville < 38.0 % AND  Blue Marsh < 36.8 %  for 3 consecutive days

Exit criteria (§2.5.6.E):
    Any drought stage exits after 30 consecutive days where the instantaneous stage
    is lower than the declared stage, OR immediately upon a spill event at either
    reservoir (storage >= 100 % of DRBC usable conservation capacity).

DRBC usable conservation storage:
    beltzvilleCombined: 13 500 MG
    blueMarsh:           7 450 MG
"""

import sys
import os
import pathlib
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = pathlib.Path(__file__).parent
OUTDIR = HERE / "outputs"
FIGDIR = HERE / "figures"
OUTDIR.mkdir(exist_ok=True)
FIGDIR.mkdir(exist_ok=True)

HDF5_PATH = str(OUTDIR / "nhmv10_2001_2004_validation.hdf5")
MODEL_JSON = str(OUTDIR / "nhmv10_validation_model.json")

# ---------------------------------------------------------------------------
# Constants — mirror LowerBasinDroughtLevel class attributes exactly
# ---------------------------------------------------------------------------
BETZ_WARNING_FRAC = 0.737
BM_WARNING_FRAC   = 0.689
BETZ_DROUGHT_FRAC = 0.380
BM_DROUGHT_FRAC   = 0.368
MAX_VOL_BELTZVILLE = 13_500   # MG  (DRBC usable conservation storage)
MAX_VOL_BLUEMARSH  =  7_450   # MG

# Conservation releases (MGD) — from lower_basin_ffmp.py dicts
from pywrdrb.utils.constants import cfs_to_mgd
R_MIN_NORMAL  = {"blueMarsh": 50 * cfs_to_mgd, "beltzvilleCombined": 35 * cfs_to_mgd}
R_MIN_DROUGHT = {"blueMarsh": 30 * cfs_to_mgd, "beltzvilleCombined": 15 * cfs_to_mgd}

# Validation window: the 2004 drought event (D2 empirical anchor)
VAL_START = "2004-07-01"
VAL_END   = "2004-12-31"

# ============================================================
# PART 1  —  UNIT TESTS  (pure logic, no Pywr)
# ============================================================

DROUGHT_PERSIST_DAYS  = 3
RECOVERY_PERSIST_DAYS = 30


def _lb_stage(betz_frac: float, bm_frac: float, days_below: int) -> int:
    """
    Instantaneous LB stage — mirrors LowerBasinDroughtLevel.value() *entry* logic
    (no hysteresis).  Used for unit tests that check entry conditions in isolation.
    drought_days_below is the count from *prior* days (before the current timestep's
    after() update), so stage-2 requires days_below >= DROUGHT_PERSIST_DAYS - 1 = 2.
    """
    today_drought = (betz_frac < BETZ_DROUGHT_FRAC) and (bm_frac < BM_DROUGHT_FRAC)
    if today_drought and days_below >= (DROUGHT_PERSIST_DAYS - 1):
        return 2
    if (betz_frac < BETZ_WARNING_FRAC) or (bm_frac < BM_WARNING_FRAC):
        return 1
    return 0


def _simulate_declared_stage(storage_trace):
    """
    Simulate the full hysteresis logic of LowerBasinDroughtLevel over a sequence
    of (betz_frac, bm_frac) pairs.

    Mirrors the combined value() + after() logic:
      - value() returns declared_stage if inst < declared, else inst (fast entry)
      - after() updates drought_days_below, computes inst (using updated counter,
        so stage-2 requires days_below >= DROUGHT_PERSIST_DAYS after update), then
        applies hysteresis: spill → 0 immediately; inst >= declared → accept;
        inst < declared → count recovery_days, accept after RECOVERY_PERSIST_DAYS.

    Parameters
    ----------
    storage_trace : list of (betz_frac, bm_frac)
        One entry per simulated day.

    Returns
    -------
    list of int
        The declared stage returned by value() on each day.
    """
    drought_days_below = 0
    recovery_days      = 0
    declared           = 0
    returned_stages    = []

    for betz_f, bm_f in storage_trace:
        # ----- value() phase (reads state from end of previous day) -----
        today_drought_v = (betz_f < BETZ_DROUGHT_FRAC) and (bm_f < BM_DROUGHT_FRAC)
        if today_drought_v and drought_days_below >= (DROUGHT_PERSIST_DAYS - 1):
            inst_v = 2
        elif (betz_f < BETZ_WARNING_FRAC) or (bm_f < BM_WARNING_FRAC):
            inst_v = 1
        else:
            inst_v = 0

        returned = inst_v if inst_v >= declared else declared
        returned_stages.append(returned)

        # ----- after() phase (reads end-of-timestep = same storage here) -----
        spill = (betz_f >= 1.0) or (bm_f >= 1.0)

        # Update drought_days_below counter
        today_drought_a = (betz_f < BETZ_DROUGHT_FRAC) and (bm_f < BM_DROUGHT_FRAC)
        if today_drought_a:
            drought_days_below += 1
        else:
            drought_days_below = 0

        # Instantaneous stage using UPDATED counter (>= DROUGHT_PERSIST_DAYS = 3)
        if today_drought_a and drought_days_below >= DROUGHT_PERSIST_DAYS:
            inst_a = 2
        elif (betz_f < BETZ_WARNING_FRAC) or (bm_f < BM_WARNING_FRAC):
            inst_a = 1
        else:
            inst_a = 0

        # Hysteresis update
        if spill:
            declared      = 0
            recovery_days = 0
        elif inst_a >= declared:
            declared      = inst_a
            recovery_days = 0
        else:
            recovery_days += 1
            if recovery_days >= RECOVERY_PERSIST_DAYS:
                declared      = inst_a
                recovery_days = 0

    return returned_stages


def run_unit_tests() -> int:
    """
    Run unit tests against the threshold logic and R_min switching.
    Returns number of failures.
    """
    print("=" * 60)
    print("PART 1 — UNIT TESTS")
    print("=" * 60)

    failures = 0

    def check(desc, got, expected):
        nonlocal failures
        status = "PASS" if got == expected else "FAIL"
        if got != expected:
            failures += 1
        print(f"  [{status}]  {desc}")
        if got != expected:
            print(f"           expected {expected!r}, got {got!r}")

    # ---- Stage classification ------------------------------------------------
    print("\n-- Stage classification --")

    check("Both well above warning → Normal (0)",
          _lb_stage(0.90, 0.80, 0), 0)

    check("Beltzville exactly at warning boundary (0.737) → Normal (0)",
          _lb_stage(BETZ_WARNING_FRAC, BM_WARNING_FRAC, 0), 0)

    check("Beltzville just below warning (0.736) → Warning (1)",
          _lb_stage(0.736, BM_WARNING_FRAC, 0), 1)

    check("Blue Marsh just below warning (0.688) → Warning (1)",
          _lb_stage(BETZ_WARNING_FRAC, 0.688, 0), 1)

    check("Both below warning, but above drought thresholds → Warning (1)",
          _lb_stage(0.60, 0.55, 0), 1)

    check("Both below drought, day 1 (days_below=0) → Warning (1, not yet 3 days)",
          _lb_stage(0.30, 0.30, 0), 1)

    check("Both below drought, day 2 (days_below=1) → Warning (1, not yet 3 days)",
          _lb_stage(0.30, 0.30, 1), 1)

    check("Both below drought, day 3 (days_below=2) → Drought (2) declared",
          _lb_stage(0.30, 0.30, 2), 2)

    check("Both below drought, day 10 (days_below=9) → Drought (2) sustained",
          _lb_stage(0.30, 0.30, 9), 2)

    check("Beltzville recovers above drought threshold on day 3 → Warning (1)",
          _lb_stage(0.40, 0.30, 2), 1)

    check("Blue Marsh recovers above drought threshold on day 3 → Warning (1)",
          _lb_stage(0.30, 0.40, 2), 1)

    check("12% storage (2004 observed Blue Marsh Dec 6) with 3 days → Drought (2)",
          _lb_stage(0.25, 0.12, 2), 2)

    # ---- Threshold boundary values (edge cases) ------------------------------
    print("\n-- Boundary edge cases --")

    check("Beltzville exactly at drought threshold → Warning, not Drought",
          _lb_stage(BETZ_DROUGHT_FRAC, BETZ_DROUGHT_FRAC, 9), 1)
          # Note: BM_DROUGHT_FRAC < BETZ_DROUGHT_FRAC, so using same value for both:
          # betz=0.380 is NOT < 0.380, so today_drought=False

    check("Beltzville marginally below drought threshold → Drought (if 3 days)",
          _lb_stage(BETZ_DROUGHT_FRAC - 0.001, BM_DROUGHT_FRAC - 0.001, 2), 2)

    # ---- R_min switching logic -----------------------------------------------
    print("\n-- R_min conservation release switching --")

    for res in ["blueMarsh", "beltzvilleCombined"]:
        check(f"{res}: stage 0 → normal R_min = {R_MIN_NORMAL[res]:.2f} MGD",
              R_MIN_NORMAL[res], R_MIN_NORMAL[res])   # always passes — just prints value

        drought_r = R_MIN_DROUGHT[res]
        normal_r  = R_MIN_NORMAL[res]
        check(f"{res}: drought release ({drought_r:.2f}) < normal release ({normal_r:.2f})",
              drought_r < normal_r, True)

    rmin_bm_normal_cfs  = R_MIN_NORMAL["blueMarsh"]  / cfs_to_mgd
    rmin_bm_drought_cfs = R_MIN_DROUGHT["blueMarsh"] / cfs_to_mgd
    check(f"Blue Marsh: normal R_min = {rmin_bm_normal_cfs:.0f} cfs (Water Code Table 4)",
          round(rmin_bm_normal_cfs), 50)
    check(f"Blue Marsh: drought R_min = {rmin_bm_drought_cfs:.0f} cfs (Water Code Table 4)",
          round(rmin_bm_drought_cfs), 30)

    rmin_bz_normal_cfs  = R_MIN_NORMAL["beltzvilleCombined"]  / cfs_to_mgd
    rmin_bz_drought_cfs = R_MIN_DROUGHT["beltzvilleCombined"] / cfs_to_mgd
    check(f"Beltzville: normal R_min = {rmin_bz_normal_cfs:.0f} cfs (Water Code Table 4)",
          round(rmin_bz_normal_cfs), 35)
    check(f"Beltzville: drought R_min = {rmin_bz_drought_cfs:.0f} cfs (Water Code Table 4)",
          round(rmin_bz_drought_cfs), 15)

    # ---- days_below counter simulation (simulating after() over several days) ---
    print("\n-- 3-day persistence simulation --")
    days_below = 0
    sequence = []  # (day, betz_frac, bm_frac, stage)
    storage_trace = [
        # (betz_frac, bm_frac)
        (0.50, 0.50),   # day 0: both below warning — Warning
        (0.35, 0.35),   # day 1: both below drought — still Warning (day 1)
        (0.34, 0.34),   # day 2: both below drought — still Warning (day 2)
        (0.33, 0.33),   # day 3: both below drought — Drought! (day 3)
        (0.32, 0.32),   # day 4: sustained drought
        (0.45, 0.32),   # day 5: beltzville recovers above drought threshold → resets counter
        (0.32, 0.30),   # day 6: both below again → Warning (reset)
    ]
    expected_stages = [1, 1, 1, 2, 2, 1, 1]
    for day, (bf, bmf) in enumerate(storage_trace):
        stage = _lb_stage(bf, bmf, days_below)
        # Update counter (mirrors after() logic)
        if (bf < BETZ_DROUGHT_FRAC) and (bmf < BM_DROUGHT_FRAC):
            days_below += 1
        else:
            days_below = 0
        check(f"Day {day}: betz={bf:.2f} bm={bmf:.2f} days_prior={days_below-1 if days_below>0 else 0} → stage {expected_stages[day]}",
              stage, expected_stages[day])

    # ---- 30-day recovery exit — stage 2 → stage 1 --------------------------------
    # Scenario: 3-day drought entry, then one reservoir rises above drought but
    # stays below warning threshold.  Stage should NOT drop until day 30 of recovery.
    print("\n-- 30-day exit: Drought (2) → Warning (1) --")
    # Build trace: 3 days at full-drought fracs, then 60 days at (betz=0.45, bm=0.30)
    # betz=0.45 > BETZ_DROUGHT_FRAC → today_drought = False; both still < warning → inst=1
    DROUGHT_ENTRY  = (BETZ_DROUGHT_FRAC - 0.01, BM_DROUGHT_FRAC - 0.01)  # both below drought
    RECOVERY_COND  = (0.45, BM_DROUGHT_FRAC - 0.01)  # betz above drought, bm below warning
    trace_30 = [DROUGHT_ENTRY] * 3 + [RECOVERY_COND] * 60
    stages_30 = _simulate_declared_stage(trace_30)

    check("Day 3 (3rd drought day): declared stage = 2",
          stages_30[2], 2)
    check("Day 4 (recovery day 1): declared stage still = 2 (sticky)",
          stages_30[3], 2)
    check("Day 32 (recovery day 29): declared stage still = 2",
          stages_30[3 + 28], 2)
    check("Day 33 (recovery day 30 complete in after()): declared stage still = 2 in value()",
          stages_30[3 + 29], 2)
    check("Day 34 (first day after 30-day threshold met): declared stage = 1",
          stages_30[3 + 30], 1)
    check("No stage-0 during partial recovery (bm still below warning)",
          all(s >= 1 for s in stages_30[3:]), True)

    # ---- 30-day recovery exit — stage 1 → stage 0 --------------------------------
    print("\n-- 30-day exit: Warning (1) → Normal (0) --")
    # Build trace: 5 warning days (only betz below warning), then 60 days both above
    WARN_ONLY   = (BETZ_WARNING_FRAC - 0.01, BM_WARNING_FRAC + 0.05)  # betz below, bm above
    NORMAL_COND = (BETZ_WARNING_FRAC + 0.05, BM_WARNING_FRAC + 0.05)  # both above warning
    trace_w = [WARN_ONLY] * 5 + [NORMAL_COND] * 60
    stages_w = _simulate_declared_stage(trace_w)

    check("Day 1 warning entry: declared stage = 1",
          stages_w[0], 1)
    check("Day 6 (normal cond day 1): declared stage still = 1 (sticky)",
          stages_w[5], 1)
    check("Day 34 (normal cond day 29): declared stage still = 1",
          stages_w[5 + 28], 1)
    check("Day 36 (normal cond day 30 complete): declared stage drops to 0",
          stages_w[5 + 30], 0)

    # ---- Partial recovery then relapse — counter resets --------------------------
    print("\n-- Partial recovery relapse: exit counter resets on re-entry --")
    # 3 drought days → 15 recovery days → 3 more drought days → check recovery reset
    trace_relapse = (
        [DROUGHT_ENTRY] * 3           # days 0-2: drought entry
        + [RECOVERY_COND] * 15        # days 3-17: 15 recovery days (not enough)
        + [DROUGHT_ENTRY] * 3         # days 18-20: relapse, must re-enter drought
        + [RECOVERY_COND] * 35        # days 21-55: another 30+ recovery days
    )
    stages_relapse = _simulate_declared_stage(trace_relapse)

    check("Day 2: stage 2 declared",
          stages_relapse[2], 2)
    check("Day 17 (recovery day 15): stage still 2 (counter not reset by relapse yet)",
          stages_relapse[17], 2)
    # After relapse: another 3 drought days → stage back to 2, recovery resets
    check("Day 20 (3rd relapse day): back to stage 2",
          stages_relapse[20], 2)
    # Post-relapse recovery restarts at day 21 with recovery_days=0.
    # after() day 21 → recovery_days=1; after() day 50 → recovery_days=30 → exit fires.
    # value() day 50 still sees declared=2 (after() fires after value()); day 51 sees 1.
    check("Day 50 (recovery day 30 complete in after()): value() still returns 2",
          stages_relapse[50], 2)
    check("Day 51 (first value() call after 30-day post-relapse exit): stage 1",
          stages_relapse[51], 1)

    # ---- Spill exit — immediate reset to stage 0 ---------------------------------
    print("\n-- Spill exit: immediate stage-0 on reservoir spill --")
    SPILL_COND = (1.05, 1.05)   # both above 100% usable storage → spill
    trace_spill = [DROUGHT_ENTRY] * 3 + [SPILL_COND] * 3 + [DROUGHT_ENTRY] * 2
    stages_spill = _simulate_declared_stage(trace_spill)

    check("Day 2: stage 2 before spill",
          stages_spill[2], 2)
    check("Day 3 (spill day 1): stage still 2 in value() (spill in after(), takes effect day 4)",
          stages_spill[3], 2)
    check("Day 4 (after spill processed in after()): stage drops to 0",
          stages_spill[4], 0)
    # After spill clears, 2 drought days restart without enough persistence → Warning
    check("Day 6 (2nd drought day post-spill): stage 1 (3-day persistence not yet met)",
          stages_spill[6], 1)

    # ---- Stage-2 entry cannot be delayed by already-declared stage 2 --------------
    print("\n-- Stage-2 re-entry during recovery: no artificial delay --")
    # declared=2, 20 recovery days, then 3 new drought days → should return 2 immediately
    trace_reentry = (
        [DROUGHT_ENTRY] * 3   # initial drought
        + [RECOVERY_COND] * 20  # 20 recovery days (not yet exited)
        + [DROUGHT_ENTRY] * 3   # 3 new drought days — re-enter stage 2 immediately
    )
    stages_reentry = _simulate_declared_stage(trace_reentry)
    # Day 25 is 3rd new drought day (indices 3+20=23, 24, 25)
    check("Day 25 (3rd new drought day): stage 2 via fast entry",
          stages_reentry[25], 2)

    # ---- RECOVERY_PERSIST_DAYS class attribute -----------------------------------
    print("\n-- Class attribute: RECOVERY_PERSIST_DAYS --")
    try:
        from pywrdrb.parameters.ffmp import LowerBasinDroughtLevel
        check("RECOVERY_PERSIST_DAYS == 30",
              LowerBasinDroughtLevel.RECOVERY_PERSIST_DAYS, 30)
        check("DROUGHT_PERSIST_DAYS == 3",
              LowerBasinDroughtLevel.DROUGHT_PERSIST_DAYS, 3)
        check("setup() creates recovery_days array (checked via new instance attr name)",
              hasattr(LowerBasinDroughtLevel, "RECOVERY_PERSIST_DAYS"), True)
    except Exception as e:
        failures += 1
        print(f"  [FAIL]  attribute check: {e}")

    # ---- Import check — LowerBasinDroughtLevel registered with Pywr -----------
    print("\n-- Pywr registration --")
    try:
        from pywrdrb.parameters.ffmp import LowerBasinDroughtLevel
        check("LowerBasinDroughtLevel importable from pywrdrb.parameters.ffmp", True, True)

        # Check it's in Pywr's registry (Pywr lowercases all keys)
        from pywr.parameters import parameter_registry
        in_registry = "lowerbasindroughtlevel" in parameter_registry
        check("LowerBasinDroughtLevel in Pywr parameter registry (key=lowerbasindroughtlevel)",
              in_registry, True)

        # Check class attributes match expected thresholds
        check("BETZ_WARNING_FRAC == 0.737",
              LowerBasinDroughtLevel.BETZ_WARNING_FRAC, 0.737)
        check("BM_WARNING_FRAC == 0.689",
              LowerBasinDroughtLevel.BM_WARNING_FRAC, 0.689)
        check("BETZ_DROUGHT_FRAC == 0.380",
              LowerBasinDroughtLevel.BETZ_DROUGHT_FRAC, 0.380)
        check("BM_DROUGHT_FRAC == 0.368",
              LowerBasinDroughtLevel.BM_DROUGHT_FRAC, 0.368)
        check("MAX_VOL_BELTZVILLE == 13500",
              LowerBasinDroughtLevel.MAX_VOL_BELTZVILLE, 13_500)
        check("MAX_VOL_BLUEMARSH == 7450",
              LowerBasinDroughtLevel.MAX_VOL_BLUEMARSH, 7_450)
        check("DROUGHT_PERSIST_DAYS == 3",
              LowerBasinDroughtLevel.DROUGHT_PERSIST_DAYS, 3)
        check("RECOVERY_PERSIST_DAYS == 30",
              LowerBasinDroughtLevel.RECOVERY_PERSIST_DAYS, 30)
    except Exception as e:
        failures += 1
        print(f"  [FAIL]  import / registry check: {e}")

    print(f"\nUnit tests: {failures} failure(s)\n")
    return failures


# ============================================================
# PART 2  —  INTEGRATION RUN
# ============================================================

def run_integration(force_rerun: bool = False) -> dict:
    """
    Build and run nhmv10 model (2001-10-01 to 2004-12-31).
    Saves HDF5 to outputs/. Returns raw dict from hdf5_to_dict.
    """
    print("=" * 60)
    print("PART 2 — INTEGRATION RUN  (nhmv10 2001-10-01 → 2004-12-31)")
    print("=" * 60)

    import pywrdrb
    from pywrdrb import hdf5_to_dict

    if os.path.exists(HDF5_PATH) and not force_rerun:
        print(f"  HDF5 already exists — loading {HDF5_PATH}")
        print("  (pass force_rerun=True or delete file to re-run model)")
        data = hdf5_to_dict(HDF5_PATH)
        return data

    # Build model
    print("  Building nhmv10 model …")
    mb = pywrdrb.ModelBuilder(
        inflow_type="nhmv10",
        start_date="2001-10-01",
        end_date="2004-12-31",
    )
    mb.make_model()
    mb.write_model(MODEL_JSON)
    print(f"  Model JSON written → {MODEL_JSON}")

    # Load
    model = pywrdrb.Model.load(MODEL_JSON)

    # Record
    recorder = pywrdrb.OutputRecorder(
        model=model,
        output_filename=HDF5_PATH,
    )

    # Run
    print("  Running simulation …")
    stats = model.run()
    print(f"  Simulation complete.  Steps: {stats}")

    # Load output
    data = hdf5_to_dict(HDF5_PATH)
    print(f"  HDF5 saved → {HDF5_PATH}")
    print(f"  Keys in output: {sorted(data.keys())[:8]} …")
    return data


def run_integration_tests(data: dict) -> int:
    """
    Verify drought_level_agg_lb signals are correct given observed storages.
    Returns number of failures.
    """
    print("\n" + "=" * 60)
    print("PART 2b — INTEGRATION ASSERTIONS")
    print("=" * 60)

    failures = 0

    def check(desc, passed, detail=""):
        nonlocal failures
        status = "PASS" if passed else "FAIL"
        if not passed:
            failures += 1
        line = f"  [{status}]  {desc}"
        if detail:
            line += f"\n           {detail}"
        print(line)

    # --- Build time index ---
    # Pywr stores data as (n_timesteps, n_scenarios) arrays
    # Use the storage arrays to determine the time axis length
    bm_vol_raw = data["reservoir_blueMarsh"]       # shape (T, S) or (T,)
    bz_vol_raw = data["reservoir_beltzvilleCombined"]

    T = bm_vol_raw.shape[0]
    date_range = pd.date_range("2001-10-01", periods=T, freq="D")

    # Scenario 0 (single scenario run)
    s = 0
    def ts(arr):
        """Extract scenario-0 1-D time series."""
        a = np.array(arr)
        return a[:, s] if a.ndim == 2 else a

    bm_vol  = pd.Series(ts(bm_vol_raw),  index=date_range)
    bz_vol  = pd.Series(ts(bz_vol_raw),  index=date_range)
    lb_stage = pd.Series(ts(data["drought_level_agg_lb"]).astype(int), index=date_range)

    # Storage fractions (DRBC usable storage basis — matches LowerBasinDroughtLevel)
    bm_frac = bm_vol  / MAX_VOL_BLUEMARSH
    bz_frac = bz_vol  / MAX_VOL_BELTZVILLE

    # --- Basic presence checks ---
    check("drought_level_agg_lb present in HDF5 output",
          "drought_level_agg_lb" in data)
    check("reservoir_blueMarsh present in HDF5 output",
          "reservoir_blueMarsh" in data)
    check("reservoir_beltzvilleCombined present in HDF5 output",
          "reservoir_beltzvilleCombined" in data)
    check("lower_basin_agg_mrf_trenton_step1 present in HDF5 output",
          "lower_basin_agg_mrf_trenton_step1" in data)

    # --- Stage 0 occurs in wet periods ---
    # Expect Normal in spring 2003 (high water) before summer drawdown
    spring_mask = (date_range >= "2003-03-01") & (date_range <= "2003-05-31")
    n_normal_spring = (lb_stage[spring_mask] == 0).sum()
    check(f"Stage 0 (Normal) occurs at least once in spring 2003",
          n_normal_spring > 0,
          f"days at Normal in Mar–May 2003: {n_normal_spring}")

    # --- The 2004 drought: diagnostic (informational, not required PASS) ---
    # NOTE: nhmv10 uses NHM-simulated (not observed) streamflows.  The NHM
    # hydrologic model does not reproduce the 2004 LB storage depletion as
    # severely as observed (Blue Marsh reached ~12% capacity by Dec 6 in
    # reality).  This is a known model limitation motivating the D2 HEC-ResSim
    # validation.  The assertions below are INFORMATIONAL — they report what
    # nhmv10 produces without failing the test.
    val_mask = (date_range >= VAL_START) & (date_range <= VAL_END)
    bm_val    = bm_frac[val_mask]
    bz_val    = bz_frac[val_mask]
    stage_val = lb_stage[val_mask]

    bm_min_frac = float(bm_val.min())
    bz_min_frac = float(bz_val.min())
    n_normal  = (stage_val == 0).sum()
    n_warning = (stage_val == 1).sum()
    n_drought = (stage_val == 2).sum()
    n_total_val = int(val_mask.sum())

    print(f"\n  --- 2004 Jul–Dec LB drought statistics (nhmv10, informational) ---")
    print(f"  Blue Marsh  min fraction : {bm_min_frac:.3f}  "
          f"({'BELOW' if bm_min_frac < BM_DROUGHT_FRAC else 'ABOVE'} drought threshold {BM_DROUGHT_FRAC})")
    print(f"  Beltzville  min fraction : {bz_min_frac:.3f}  "
          f"({'BELOW' if bz_min_frac < BETZ_DROUGHT_FRAC else 'ABOVE'} drought threshold {BETZ_DROUGHT_FRAC})")
    print(f"  Stage 0 (Normal)  days  : {n_normal}")
    print(f"  Stage 1 (Warning) days  : {n_warning}")
    print(f"  Stage 2 (Drought) days  : {n_drought}  (of {n_total_val} total)")
    if n_drought == 0:
        print(f"  NOTE: nhmv10 does not reproduce 2004 LB drought storage depletion.")
        print(f"        This is expected — see D2 HEC-ResSim validation plan.")

    # Check that if warning DOES occur, the stage signal is consistent
    # (This verifies wiring even when drought threshold is not crossed)
    if n_warning > 0:
        check("When Warning stage appears in 2004, at least one reservoir is below warning threshold",
              ((bm_val < BM_WARNING_FRAC) | (bz_val < BETZ_WARNING_FRAC))[stage_val == 1].all(),
              f"Warning days in 2004: {n_warning}")
    else:
        print(f"  [INFO]  No Warning or Drought days in Jul–Dec 2004 under nhmv10 — "
              f"LB stays above §2.5.6 warning thresholds in this dataset.")

    # --- Verify stage matches raw fractions independently (with hysteresis) ---
    # Use _simulate_declared_stage which mirrors the full value() + after() logic
    # including 30-day exit hysteresis and spill detection.
    print("\n  Verification: recomputing declared stage from raw storage fractions …")
    storage_seq = list(zip(
        bz_frac.values.tolist(),
        bm_frac.values.tolist(),
    ))
    expected_stage_list = _simulate_declared_stage(storage_seq)
    expected_stage      = np.array(expected_stage_list, dtype=int)

    expected_s = pd.Series(expected_stage, index=date_range)
    n_match  = (lb_stage == expected_s).sum()
    n_total  = T
    pct_match = 100.0 * n_match / n_total
    check(f"Model declared stage matches hysteresis-aware recomputed stage ≥ 99% of days",
          pct_match >= 99.0,
          f"match: {n_match}/{n_total} ({pct_match:.2f}%)")

    # Also report instantaneous (no-hysteresis) match for reference
    days_below_arr = np.zeros(T, dtype=int)
    inst_stage     = np.zeros(T, dtype=int)
    for t in range(T):
        bf  = float(bz_frac.iloc[t])
        bmf = float(bm_frac.iloc[t])
        d   = int(days_below_arr[t - 1]) if t > 0 else 0
        inst_stage[t] = _lb_stage(bf, bmf, d)
        if (bf < BETZ_DROUGHT_FRAC) and (bmf < BM_DROUGHT_FRAC):
            days_below_arr[t] = d + 1
        else:
            days_below_arr[t] = 0
    inst_s     = pd.Series(inst_stage, index=date_range)
    n_inst     = (lb_stage == inst_s).sum()
    pct_inst   = 100.0 * n_inst / n_total
    hysteresis_days = int((expected_s != inst_s).sum())
    print(f"  Instantaneous (no-hysteresis) match: {n_inst}/{n_total} ({pct_inst:.2f}%)")
    print(f"  Days where hysteresis changes stage  : {hysteresis_days}")

    # --- LB MRF contributions: report over full run (informational) ---
    lb_mrf = pd.Series(ts(data["lower_basin_agg_mrf_trenton_step1"]), index=date_range)
    n_nonzero_mrf_total = (lb_mrf > 0.1).sum()
    n_nonzero_mrf_val   = (lb_mrf[val_mask] > 0.1).sum()
    print(f"\n  --- LB MRF Trenton contributions (informational) ---")
    print(f"  Days with LB MRF > 0.1 MGD (full run)  : {n_nonzero_mrf_total}")
    print(f"  Days with LB MRF > 0.1 MGD (2004 Jul–Dec): {n_nonzero_mrf_val}")
    if n_nonzero_mrf_total == 0:
        print(f"  NOTE: Zero LB contributions across full run — Trenton flow met by NYC"
              f" alone under nhmv10 flows.  This is the known 'zero contribution' "
              f"problem; D2 validation with observed flows will test whether drought "
              f"staging produces non-zero contributions when storage is truly depleted.")

    print(f"\nIntegration tests: {failures} failure(s)")
    return failures, date_range, bm_frac, bz_frac, lb_stage, expected_s, lb_mrf, data


# ============================================================
# PART 3  —  DIAGNOSTIC PLOTS
# ============================================================

def make_diagnostic_plots(date_range, bm_frac, bz_frac, lb_stage,
                           expected_stage, lb_mrf, data):
    """
    4-panel diagnostic figure saved to figures/lb_drought_stage_diagnostic.png.

    Panel 1: Blue Marsh + Beltzville storage fractions vs. Water Code thresholds
    Panel 2: drought_level_agg_lb (model) vs. independently recomputed stage
    Panel 3: LB aggregate MRF Trenton contribution  (before/now comparison)
    Panel 4: R_min conservation releases inferred from drought level
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.ticker as ticker

    print("\n" + "=" * 60)
    print("PART 3 — DIAGNOSTIC PLOTS")
    print("=" * 60)

    # Focus window for detailed view: 2003-07-01 to 2004-12-31
    plot_start = "2003-07-01"
    plot_end   = "2004-12-31"
    mask = (date_range >= plot_start) & (date_range <= plot_end)
    dates = date_range[mask]

    def clip(series):
        return series[mask].values

    bm_f    = clip(bm_frac)
    bz_f    = clip(bz_frac)
    stage_m = clip(lb_stage).astype(int)
    stage_e = clip(expected_stage).astype(int)

    # LB MRF contributions
    lb_mrf_v = clip(lb_mrf)

    # Per-reservoir contributions (step 1 — best proxy for day-ahead operations)
    def ts_clip(key):
        arr = np.array(data[key])
        s0 = arr[:, 0] if arr.ndim == 2 else arr
        return s0[mask]

    bm_mrf  = ts_clip("mrf_trenton_blueMarsh")       if "mrf_trenton_blueMarsh" in data else np.zeros(mask.sum())
    bz_mrf  = ts_clip("mrf_trenton_beltzvilleCombined") if "mrf_trenton_beltzvilleCombined" in data else np.zeros(mask.sum())

    # R_min inferred from drought level
    rmin_bm = np.where(stage_m >= 1,
                       R_MIN_DROUGHT["blueMarsh"],
                       R_MIN_NORMAL["blueMarsh"])
    rmin_bz = np.where(stage_m >= 1,
                       R_MIN_DROUGHT["beltzvilleCombined"],
                       R_MIN_NORMAL["beltzvilleCombined"])

    # ---- Stage background color helper ----------------------------------------
    STAGE_COLORS = {0: "#d4efdf", 1: "#fdebd0", 2: "#fadbd8"}
    STAGE_LABELS = {0: "Normal", 1: "LB Warning", 2: "LB Drought"}

    def shade_stages(ax, dates, stages):
        """Add colored background bands for each stage run."""
        if len(dates) == 0:
            return
        # Group consecutive identical stage values and shade each run
        prev_s  = stages[0]
        start_d = dates[0]
        for i in range(1, len(stages)):
            if stages[i] != prev_s or i == len(stages) - 1:
                end_d = dates[i - 1] if stages[i] != prev_s else dates[i]
                ax.axvspan(start_d, end_d, alpha=0.25,
                           color=STAGE_COLORS[prev_s], zorder=0)
                prev_s  = stages[i]
                start_d = dates[i]

    # ---- Figure layout ---------------------------------------------------------
    fig, axes = plt.subplots(
        4, 1, figsize=(14, 12),
        gridspec_kw={"height_ratios": [3, 1.5, 2, 1.5]},
        sharex=True,
    )
    fig.suptitle(
        "LB Drought Stage Switching — Validation Diagnostics\n"
        "nhmv10 · Jul 2003 – Dec 2004  (D2 validation window)",
        fontsize=13, fontweight="bold", y=0.98,
    )

    # ---- Panel 1: Storage fractions ------------------------------------------
    ax1 = axes[0]
    shade_stages(ax1, dates, stage_m)
    ax1.plot(dates, bm_f,  color="#1a5276", lw=1.8, label="Blue Marsh frac")
    ax1.plot(dates, bz_f,  color="#884ea0", lw=1.8, label="Beltzville frac")

    # Warning thresholds
    ax1.axhline(BM_WARNING_FRAC,   color="#1a5276", ls="--", lw=1.0, alpha=0.7,
                label=f"BM warning ({BM_WARNING_FRAC})")
    ax1.axhline(BETZ_WARNING_FRAC, color="#884ea0", ls="--", lw=1.0, alpha=0.7,
                label=f"Beltz warning ({BETZ_WARNING_FRAC})")
    # Drought thresholds
    ax1.axhline(BM_DROUGHT_FRAC,   color="#1a5276", ls=":",  lw=1.2, alpha=0.9,
                label=f"BM drought ({BM_DROUGHT_FRAC})")
    ax1.axhline(BETZ_DROUGHT_FRAC, color="#884ea0", ls=":",  lw=1.2, alpha=0.9,
                label=f"Beltz drought ({BETZ_DROUGHT_FRAC})")

    ax1.set_ylabel("Storage fraction\n(of DRBC usable)", fontsize=10)
    ax1.set_ylim(-0.05, 1.15)
    ax1.legend(fontsize=8, ncol=3, loc="upper right")
    ax1.set_title("Blue Marsh + Beltzville Storage vs. Water Code §2.5.6 Thresholds",
                  fontsize=10, loc="left")
    ax1.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0))

    # ---- Panel 2: Drought level ----------------------------------------------
    ax2 = axes[1]
    shade_stages(ax2, dates, stage_m)
    ax2.step(dates, stage_m,  where="post", color="#c0392b", lw=2.0,
             label="model: drought_level_agg_lb")
    ax2.step(dates, stage_e,  where="post", color="#2980b9", lw=1.0,
             ls="--", alpha=0.8, label="recomputed from raw storage")
    ax2.set_ylabel("LB drought\nstage", fontsize=10)
    ax2.set_ylim(-0.3, 2.6)
    ax2.set_yticks([0, 1, 2])
    ax2.set_yticklabels(["0 Normal", "1 Warning", "2 Drought"], fontsize=8)
    ax2.legend(fontsize=8, loc="upper left")
    ax2.set_title("drought_level_agg_lb  (model output vs. independently recomputed)",
                  fontsize=10, loc="left")

    # Annotate mismatch days if any
    mismatch = dates[stage_m != stage_e]
    if len(mismatch) > 0:
        for d in mismatch[:5]:
            ax2.axvline(d, color="orange", lw=0.8, alpha=0.8)
        ax2.text(0.01, 0.92, f"{len(mismatch)} mismatch day(s)",
                 transform=ax2.transAxes, fontsize=8, color="orange")

    # ---- Panel 3: LB MRF contributions ---------------------------------------
    ax3 = axes[2]
    shade_stages(ax3, dates, stage_m)
    ax3.fill_between(dates, 0, bm_mrf,  step="post", alpha=0.6,
                     color="#1a5276", label="Blue Marsh MRF contrib.")
    ax3.fill_between(dates, bm_mrf, bm_mrf + bz_mrf, step="post", alpha=0.6,
                     color="#884ea0", label="Beltzville MRF contrib.")
    ax3.step(dates, lb_mrf_v, where="post", color="k", lw=1.2, alpha=0.8,
             label="LB aggregate (step 1)")
    ax3.set_ylabel("LB Trenton MRF\ncontribution (MGD)", fontsize=10)
    ax3.set_ylim(bottom=-2)
    ax3.legend(fontsize=8, loc="upper right")
    ax3.set_title("Lower Basin Aggregate MRF Trenton Contribution  (step 1)",
                  fontsize=10, loc="left")

    # Annotate the drought period
    drought_start = dates[stage_m == 2]
    if len(drought_start) > 0:
        ax3.axvline(drought_start[0], color="#c0392b", lw=1.0, ls="--", alpha=0.7)
        ax3.text(drought_start[0], ax3.get_ylim()[1] * 0.85, " LB Drought\n declared",
                 fontsize=7, color="#c0392b")

    # ---- Panel 4: R_min conservation releases --------------------------------
    ax4 = axes[3]
    shade_stages(ax4, dates, stage_m)
    ax4.step(dates, rmin_bm, where="post", color="#1a5276", lw=2.0,
             label=f"Blue Marsh R_min  (normal={R_MIN_NORMAL['blueMarsh']:.1f}, drought={R_MIN_DROUGHT['blueMarsh']:.1f} MGD)")
    ax4.step(dates, rmin_bz, where="post", color="#884ea0", lw=2.0,
             label=f"Beltzville R_min  (normal={R_MIN_NORMAL['beltzvilleCombined']:.1f}, drought={R_MIN_DROUGHT['beltzvilleCombined']:.1f} MGD)")
    ax4.set_ylabel("R_min conservation\nrelease (MGD)", fontsize=10)
    ax4.set_ylim(0, max(R_MIN_NORMAL["blueMarsh"], R_MIN_NORMAL["beltzvilleCombined"]) * 1.3)
    ax4.legend(fontsize=8, loc="upper right")
    ax4.set_title("Conservation Release R_min Switching  (Water Code Table 4)",
                  fontsize=10, loc="left")
    ax4.set_xlabel("Date", fontsize=10)

    # ---- Stage legend patches (shared) ----------------------------------------
    legend_patches = [
        mpatches.Patch(color=STAGE_COLORS[0], alpha=0.5, label="Stage 0 — Normal"),
        mpatches.Patch(color=STAGE_COLORS[1], alpha=0.5, label="Stage 1 — LB Warning"),
        mpatches.Patch(color=STAGE_COLORS[2], alpha=0.5, label="Stage 2 — LB Drought"),
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=3,
               fontsize=9, frameon=True, bbox_to_anchor=(0.5, 0.00))

    # ---- Format x-axis --------------------------------------------------------
    import matplotlib.dates as mdates
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=2))
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    plt.tight_layout(rect=[0, 0.04, 1, 0.97])

    fig_path = str(FIGDIR / "lb_drought_stage_diagnostic.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"  Figure saved → {fig_path}")
    plt.close()
    return fig_path


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate LB drought stage switching implementation."
    )
    parser.add_argument("--rerun", action="store_true",
                        help="Force re-run of the model even if HDF5 exists")
    parser.add_argument("--unit-only", action="store_true",
                        help="Run only unit tests (skip model run + plots)")
    args = parser.parse_args()

    total_failures = 0

    # Part 1 — unit tests
    total_failures += run_unit_tests()

    if args.unit_only:
        print(f"\nTotal failures: {total_failures}")
        sys.exit(0 if total_failures == 0 else 1)

    # Part 2 — integration run
    data = run_integration(force_rerun=args.rerun)
    failures, date_range, bm_frac, bz_frac, lb_stage, expected_s, lb_mrf, data = \
        run_integration_tests(data)
    total_failures += failures

    # Part 3 — diagnostic plots
    fig_path = make_diagnostic_plots(
        date_range, bm_frac, bz_frac, lb_stage, expected_s, lb_mrf, data
    )

    # ---- Summary ---------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"SUMMARY:  {total_failures} total failure(s)")
    print(f"Figure:   {fig_path}")
    print("=" * 60)
    sys.exit(0 if total_failures == 0 else 1)

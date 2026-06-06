"""
Validation script for ERQRelease — the 1954 Decree Excess Release Quantity obligation.

Three parts matching the LB drought stage validation structure:
  1. Unit tests  — pure-logic assertions, no Pywr model needed.
  2. Integration — build + run nhmv10 model (2001-10-01 to 2004-12-31) and
                   verify erq_release_nyc recorder against independently
                   simulated ERQ logic.
  3. Diagnostics — 5-panel figure saved to figures/erq_diagnostic.png.

Usage:
    cd ~/dissertation
    source venv/bin/activate
    python shared/lower_basin_ffmp_dev/validate_erq.py [--rerun] [--unit-only]

Decree grounding:
  Art. III-B-1(c): "a quantity of water equal to 83 per cent of the amount by
      which the estimated consumption during such year is less than the City's
      estimate of the continuous safe yield ... not less than 1665 m.g.d. after
      the Cannonsville reservoir is put into operation."
  Art. III-B-1(d): "at rates designed to release the entire quantity in 120 days.
      Commencing with the fifteenth day of June ... not later than the following
      March 15. The excess quantity ... shall in no event exceed 70 billion gallons."

ERQ constants:
    safe yield floor :  1,665 MGD  → 607,891 MG/yr (× 365.25)
    seasonal period  :  June 15 – March 15
    release schedule :  ERQ / 120 days
    annual cap       :  70,000 MG  (70 BG)
    default fraction :  0.83  ("83 per cent")

Key model finding (from baseline analysis):
    At typical pywrdrb NYC delivery (~545 MGD average), raw ERQ ≈ 339,000 MG —
    always above the 70 BG cap.  The cap dominates in all scenarios.
    erq_cap_mg (not erq_fraction) is the operationally meaningful Sobol parameter.
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
HERE   = pathlib.Path(__file__).parent
OUTDIR = HERE / "outputs"
FIGDIR = HERE / "figures"
OUTDIR.mkdir(exist_ok=True)
FIGDIR.mkdir(exist_ok=True)

ERQ_HDF5  = str(OUTDIR / "nhmv10_2001_2004_erq_validation.hdf5")
ERQ_JSON  = str(OUTDIR / "nhmv10_erq_validation_model.json")
LB_HDF5   = str(OUTDIR / "nhmv10_2001_2004_validation.hdf5")  # LB run (reuse delivery_nyc)

# ---------------------------------------------------------------------------
# Decree / class constants — mirror ERQRelease exactly
# ---------------------------------------------------------------------------
NYC_SAFE_YIELD_FLOOR_MGD : float = 1_665.0    # Art. III-B-1(c)
SEASONAL_DAYS             : int   = 120        # Art. III-B-1(d)
MAX_ERQ_MG                : float = 70_000.0   # Art. III-B-1(d): 70 BG
SEASON_START              : tuple = (6, 15)    # Art. III-B-1(d): June 15
SEASON_END                : tuple = (3, 15)    # Art. III-B-1(d): March 15
DEFAULT_ERQ_FRACTION      : float = 0.83       # Art. III-B-1(c): "83 per cent"
NYC_ASSUMED_INIT_MGD      : float = 800.0      # Decree Art. III-A-3 allotment

# Derived
NYC_SAFE_YIELD_ANNUAL_MG  : float = NYC_SAFE_YIELD_FLOOR_MGD * 365.25
NYC_ASSUMED_INIT_MG       : float = NYC_ASSUMED_INIT_MGD * 365.25


# ===========================================================================
# Pure-logic helpers  (mirror ERQRelease.value() / after())
# ===========================================================================

def _in_seasonal_period(month: int, day: int) -> bool:
    """
    True during the Art. III-B-1(d) seasonal period: June 15 – March 15.
    Wraps across the calendar year-end.
    """
    if month > 6 or (month == 6 and day >= 15):    # June 15 – Dec 31
        return True
    if month < 3 or (month == 3 and day <= 15):    # Jan 1 – March 15
        return True
    return False


def _compute_erq(
    consumption_mg: float,
    erq_fraction: float = DEFAULT_ERQ_FRACTION,
    erq_cap_mg: float   = MAX_ERQ_MG,
) -> float:
    """
    Compute annual ERQ from consumption (MG) for one scenario.

    Art. III-B-1(c): ERQ = erq_fraction × max(0, safe_yield_annual - consumption)
    Art. III-B-1(d): cap at erq_cap_mg (70 BG baseline)
    """
    raw = erq_fraction * max(0.0, NYC_SAFE_YIELD_ANNUAL_MG - consumption_mg)
    return min(raw, erq_cap_mg)


def _simulate_erq(
    date_range:    pd.DatetimeIndex,
    nyc_delivery:  pd.Series,
    erq_fraction:  float = DEFAULT_ERQ_FRACTION,
    erq_cap_mg:    float = MAX_ERQ_MG,
) -> tuple:
    """
    Simulate ERQRelease over a full date range.  Mirrors the combined
    value() + after() logic of ERQRelease for a single scenario.

    Returns
    -------
    erq_release   : pd.Series   daily ERQ release from all NYC reservoirs (MGD)
    erq_remaining : pd.Series   remaining annual ERQ balance at end of each day (MG)
    erq_annual    : pd.Series   annual ERQ target (MG), updated each June 1
    """
    # Initial conditions — Art. III-B-1(c); see ERQRelease.setup()
    initial_erq  = _compute_erq(NYC_ASSUMED_INIT_MG, erq_fraction, erq_cap_mg)
    erq_remaining = initial_erq
    erq_daily_rate = initial_erq / SEASONAL_DAYS
    current_year_consumption = 0.0
    current_erq_target = initial_erq

    releases   = []
    remainings = []
    annuals    = []

    for date, nyc_div in zip(date_range, nyc_delivery):
        m, d = date.month, date.day

        # --- value() phase ---
        if _in_seasonal_period(m, d) and erq_remaining > 0.0:
            release = min(erq_daily_rate, erq_remaining)
        else:
            release = 0.0
        releases.append(release)
        annuals.append(current_erq_target)

        # --- after() phase ---
        erq_remaining             = max(0.0, erq_remaining - release)
        current_year_consumption += float(nyc_div)

        # June 1: recompute ERQ and reset annual accumulator
        if m == 6 and d == 1:
            new_erq = _compute_erq(current_year_consumption, erq_fraction, erq_cap_mg)
            erq_remaining           = new_erq
            erq_daily_rate          = new_erq / SEASONAL_DAYS if new_erq > 0.0 else 0.0
            current_erq_target      = new_erq
            current_year_consumption = 0.0

        remainings.append(erq_remaining)

    return (
        pd.Series(releases,   index=date_range, name="erq_release_mgd"),
        pd.Series(remainings, index=date_range, name="erq_remaining_mg"),
        pd.Series(annuals,    index=date_range, name="erq_annual_mg"),
    )


# ===========================================================================
# PART 1  —  UNIT TESTS  (pure logic, no Pywr)
# ===========================================================================

def run_unit_tests() -> int:
    """
    Unit tests for ERQ computation, seasonal period, and bank tracking.
    Returns number of failures.
    """
    print("=" * 60)
    print("PART 1 — UNIT TESTS")
    print("=" * 60)

    failures = 0

    def check(desc, got, expected):
        nonlocal failures
        ok = (got == expected) if not isinstance(expected, float) else abs(got - expected) < 1e-6
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{status}]  {desc}")
        if not ok:
            print(f"           expected {expected!r}, got {got!r}")

    def check_near(desc, got, expected, tol=0.5):
        """Floating-point check with tolerance."""
        nonlocal failures
        ok = abs(got - expected) <= tol
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"  [{status}]  {desc}")
        if not ok:
            print(f"           expected ≈ {expected:.3f} (±{tol}), got {got:.3f}")

    # ---- Seasonal period boundary checks ------------------------------------
    print("\n-- Art. III-B-1(d): seasonal period June 15 – March 15 --")
    # Exactly as cited in the Decree
    check("Jun 14 — NOT in season (releases start Jun 15)",
          _in_seasonal_period(6, 14), False)
    check("Jun 15 — first day of seasonal period (Art. III-B-1(d): 'fifteenth day of June')",
          _in_seasonal_period(6, 15), True)
    check("Sep 30 — in season",
          _in_seasonal_period(9, 30), True)
    check("Dec 31 — in season (period spans year-end)",
          _in_seasonal_period(12, 31), True)
    check("Jan 1  — in season",
          _in_seasonal_period(1, 1), True)
    check("Mar 15 — last day of season (Art. III-B-1(d): 'not later than March 15')",
          _in_seasonal_period(3, 15), True)
    check("Mar 16 — NOT in season",
          _in_seasonal_period(3, 16), False)
    check("May 15 — NOT in season (off-season gap Mar 16 – Jun 14)",
          _in_seasonal_period(5, 15), False)

    # ---- Art. III-B-1(c): ERQ computation ------------------------------------
    print("\n-- Art. III-B-1(c): ERQ = 0.83 × max(0, safe_yield - consumption) --")

    # Key reference: safe_yield_annual = 1665 × 365.25 = 607,891 MG
    safe = NYC_SAFE_YIELD_ANNUAL_MG
    check_near(f"Safe yield annual = 1665 × 365.25 = {safe:.0f} MG",
               safe, 608_141.25, tol=1.0)

    # Typical NYC delivery in pywrdrb is ~545 MGD avg → 199,041 MG/yr
    # Raw ERQ = 0.83 × (607,891 - 199,041) = 339,500 MG  >> 70,000 cap
    consumption_typical_mg = 545.0 * 365.25
    erq_typical = _compute_erq(consumption_typical_mg)
    check("Typical NYC consumption (545 MGD avg): cap binds, ERQ = 70,000 MG",
          erq_typical == MAX_ERQ_MG, True)

    # Decree allotment: 800 MGD → raw ERQ = 0.83 × 315,691 = 262,023 MG >> cap
    consumption_allotment_mg = 800.0 * 365.25
    erq_allotment = _compute_erq(consumption_allotment_mg)
    check("Decree allotment (800 MGD): cap binds, ERQ = 70,000 MG",
          erq_allotment == MAX_ERQ_MG, True)

    # Consumption = safe yield → ERQ = 0 (no surplus to release)
    erq_zero = _compute_erq(safe)
    check("Consumption = safe yield (1665 MGD): ERQ = 0",
          erq_zero == 0.0, True)

    # Consumption above safe yield → ERQ = 0 (no surplus)
    erq_above = _compute_erq(safe + 5000)
    check("Consumption > safe yield: ERQ = 0",
          erq_above == 0.0, True)

    # Critical threshold: raw ERQ equals cap when consumption achieves:
    # 0.83 × (607891 - C) = 70000 → C = 607891 - 84337 = 523554 MG = 1433 MGD
    threshold_mgd = (safe - MAX_ERQ_MG / DEFAULT_ERQ_FRACTION) / 365.25
    check_near("Cap-binding threshold consumption ≈ 1433 MGD",
               threshold_mgd, 1433.0, tol=2.0)

    # Just above threshold (1440 MGD) → cap does NOT bind (1440 > 1434 threshold)
    # raw = 0.83 × (608141 - 525960) = 0.83 × 82181 = 68,210 MG < 70,000 cap
    erq_above_thresh = _compute_erq(1440.0 * 365.25)
    check("Consumption 1440 MGD (above ~1434 MGD threshold): cap does NOT bind, raw < 70,000 MG",
          erq_above_thresh < MAX_ERQ_MG, True)

    # Just below threshold: consumption at 1400 MGD
    # raw = 0.83 × (607891 - 511350) = 0.83 × 96541 = 80,129 MG > cap
    erq_near = _compute_erq(1400.0 * 365.25)
    check("Consumption 1400 MGD (above ~1433 threshold): cap still binds",
          erq_near == MAX_ERQ_MG, True)

    # consumption = 1500 MGD: raw = 0.83 × (607891 - 547875) = 0.83 × 60016 = 49,813 MG < cap
    consumption_1500_mg = 1500.0 * 365.25
    erq_1500 = _compute_erq(consumption_1500_mg)
    expected_1500 = DEFAULT_ERQ_FRACTION * max(0, NYC_SAFE_YIELD_ANNUAL_MG - consumption_1500_mg)
    check_near(f"Consumption 1500 MGD: raw ERQ = {expected_1500:.0f} MG < cap (cap does NOT bind)",
               erq_1500, expected_1500, tol=1.0)
    check("Consumption 1500 MGD: returned ERQ < cap",
          erq_1500 < MAX_ERQ_MG, True)

    # ---- Art. III-B-1(d): daily rate and 120-day schedule -------------------
    print("\n-- Art. III-B-1(d): daily rate = ERQ / 120 days --")

    daily_at_cap = MAX_ERQ_MG / SEASONAL_DAYS
    check_near(f"Daily rate at cap (70,000 / 120) = {daily_at_cap:.2f} MGD",
               daily_at_cap, 583.33, tol=0.1)

    # Exhaustion after 120 days at daily_rate
    days_to_exhaust = MAX_ERQ_MG / daily_at_cap
    check_near("ERQ exhausted after exactly 120 days at daily rate",
               days_to_exhaust, 120.0, tol=0.01)

    # Seasonal exhaustion date: June 15 + 120 days ≈ October 13
    from datetime import date, timedelta
    season_start = date(2024, 6, 15)
    exhaustion_date = season_start + timedelta(days=119)  # 0-indexed
    check("Seasonal exhaustion date: June 15 + 120 days ≈ Oct 12–13",
          exhaustion_date.month in [10], True)

    # ---- Annual cap sensitivity: varying erq_cap_mg -------------------------
    print("\n-- erq_cap_mg sensitivity: Art. III-B-1(d) cap is the binding parameter --")

    for cap_bg, expected_rate in [(50, 416.67), (70, 583.33), (100, 833.33)]:
        cap_mg   = cap_bg * 1000.0
        erq_test = _compute_erq(consumption_typical_mg, erq_cap_mg=cap_mg)
        rate     = erq_test / SEASONAL_DAYS
        check_near(f"Cap = {cap_bg} BG ({cap_mg:.0f} MG): daily rate = {expected_rate:.2f} MGD",
                   rate, expected_rate, tol=0.5)

    # Varying erq_fraction has no effect when cap binds (typical conditions)
    for frac in [0.65, 0.75, 0.83, 0.90, 1.00]:
        erq_frac = _compute_erq(consumption_typical_mg, erq_fraction=frac)
        check(f"erq_fraction={frac:.2f} at 545 MGD consumption: cap still binds (ERQ=70,000 MG)",
              erq_frac == MAX_ERQ_MG, True)

    # ---- ERQ bank drawdown simulation (one seasonal period) -----------------
    print("\n-- Seasonal bank drawdown simulation (120-day period) --")

    # Simulate 200 days: 30 off-season, then Jun 15 start, 120 days, then off
    sim_dates = pd.date_range("2024-05-16", periods=200, freq="D")
    nyc_div_const = pd.Series(545.0, index=sim_dates)  # constant 545 MGD

    releases_sim, remaining_sim, annual_sim = _simulate_erq(
        sim_dates, nyc_div_const
    )

    # Before Jun 15: no releases
    pre_season = releases_sim[sim_dates < pd.Timestamp("2024-06-15")]
    check("No ERQ release before Jun 15 (off-season)",
          (pre_season == 0.0).all(), True)

    # Jun 15: first release
    jun15 = pd.Timestamp("2024-06-15")
    if jun15 in releases_sim.index:
        check_near("Jun 15: first release = daily_rate ≈ 583.3 MGD",
                   float(releases_sim.loc[jun15]), 583.33, tol=1.0)

    # After exhaustion (≥120 days after Jun 15 = after Oct 13): no more releases
    oct15 = pd.Timestamp("2024-10-14")
    if oct15 in releases_sim.index:
        post_exhaust = releases_sim[releases_sim.index >= oct15]
        if len(post_exhaust) > 0:
            check("Release = 0 after bank exhaustion (> 120 days)",
                  float(post_exhaust.iloc[0]) < 1.0, True)

    # ERQ remaining reaches 0 within season
    in_season = remaining_sim[(remaining_sim.index >= pd.Timestamp("2024-06-15")) &
                               (remaining_sim.index <= pd.Timestamp("2024-10-20"))]
    if len(in_season) > 0:
        check("ERQ remaining reaches 0 within season",
              float(in_season.min()) < 1.0, True)

    # ---- Class attribute and import checks ----------------------------------
    print("\n-- ERQRelease class attributes and Pywr registration --")
    try:
        from pywrdrb.parameters.banks import ERQRelease

        check("ERQRelease importable from pywrdrb.parameters.banks", True, True)
        check("NYC_SAFE_YIELD_FLOOR_MGD == 1665.0",
              ERQRelease.NYC_SAFE_YIELD_FLOOR_MGD, 1665.0)
        check("SEASONAL_DAYS == 120",
              ERQRelease.SEASONAL_DAYS, 120)
        check("MAX_ERQ_MG == 70000.0",
              ERQRelease.MAX_ERQ_MG, 70_000.0)
        check("SEASON_START == (6, 15)",
              ERQRelease.SEASON_START, (6, 15))
        check("SEASON_END == (3, 15)",
              ERQRelease.SEASON_END, (3, 15))
        check("DEFAULT_ERQ_FRACTION == 0.83",
              ERQRelease.DEFAULT_ERQ_FRACTION, 0.83)

        # Pywr registry
        from pywr.parameters import parameter_registry
        in_registry = "erqrelease" in parameter_registry
        check("ERQRelease in Pywr parameter registry (key='erqrelease')",
              in_registry, True)

    except Exception as e:
        failures += 1
        print(f"  [FAIL]  import/registry check: {e}")

    print(f"\nUnit tests: {failures} failure(s)\n")
    return failures


# ===========================================================================
# PART 2  —  INTEGRATION RUN
# ===========================================================================

def run_integration(force_rerun: bool = False) -> dict:
    """
    Build and run nhmv10 model (2001-10-01 to 2004-12-31) with ERQRelease wired.
    Saves a separate HDF5 to outputs/nhmv10_2001_2004_erq_validation.hdf5.
    Returns raw dict from hdf5_to_dict.
    """
    print("=" * 60)
    print("PART 2 — INTEGRATION RUN  (nhmv10 2001-10-01 → 2004-12-31, with ERQRelease)")
    print("=" * 60)

    import pywrdrb
    from pywrdrb import hdf5_to_dict

    if os.path.exists(ERQ_HDF5) and not force_rerun:
        print(f"  HDF5 already exists — loading {ERQ_HDF5}")
        print("  (pass --rerun to regenerate)")
        data = hdf5_to_dict(ERQ_HDF5)
        return data

    print("  Building nhmv10 model with ERQRelease …")
    mb = pywrdrb.ModelBuilder(
        inflow_type="nhmv10",
        start_date="2001-10-01",
        end_date="2004-12-31",
    )
    mb.make_model()
    mb.write_model(ERQ_JSON)
    print(f"  Model JSON written → {ERQ_JSON}")

    # Verify ERQ parameter is present in model_dict
    if "erq_release_nyc" not in mb.model_dict.get("parameters", {}):
        raise RuntimeError(
            "erq_release_nyc not found in model_dict — "
            "add_parameter_erq_releases() may not be wired in model_builder.py"
        )
    print("  ✓ erq_release_nyc present in model_dict")

    model    = pywrdrb.Model.load(ERQ_JSON)
    recorder = pywrdrb.OutputRecorder(
        model=model,
        output_filename=ERQ_HDF5,
        parameters=[p for p in model.parameters if p.name],
    )
    print("  Running simulation …")
    stats = model.run()
    print(f"  Simulation complete.  Steps: {stats}")

    data = hdf5_to_dict(ERQ_HDF5)
    print(f"  HDF5 saved → {ERQ_HDF5}")
    return data


def run_integration_tests(data: dict) -> tuple:
    """
    Verify erq_release_nyc signals are correct given the seasonal period,
    annual cap, and NYC delivery from the model.  Returns (failures, ...).
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

    def check_near(desc, got, expected, tol=0.5, detail=""):
        nonlocal failures
        ok = abs(got - expected) <= tol
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        line = f"  [{status}]  {desc}"
        if detail:
            line += f"\n           {detail}"
        print(line)
        if not ok:
            print(f"           expected ≈{expected:.3f} ±{tol}, got {got:.3f}")

    # --- Build time index ---
    T          = np.array(data.get("erq_release_nyc",
                                    data.get("delivery_nyc", [[0]]))).shape[0]
    date_range = pd.date_range("2001-10-01", periods=T, freq="D")

    def ts(key):
        arr = np.array(data[key])
        return arr[:, 0] if arr.ndim == 2 else arr

    # --- Presence checks ---
    check("erq_release_nyc present in HDF5 output",
          "erq_release_nyc" in data)
    check("delivery_nyc present in HDF5 output",
          "delivery_nyc" in data)
    check("link_delTrenton present in HDF5 output",
          "link_delTrenton" in data)

    if "erq_release_nyc" not in data:
        print("  Cannot proceed without erq_release_nyc — aborting integration tests")
        return failures, date_range, None, None, None, None

    erq_rel  = pd.Series(ts("erq_release_nyc"), index=date_range)
    nyc_del  = pd.Series(ts("delivery_nyc"),     index=date_range)
    trenton  = pd.Series(ts("link_delTrenton"),  index=date_range)

    # --- Seasonal period: zero outside Jun 15 – Mar 15 ----------------------
    off_season_mask = pd.Series(
        [not _in_seasonal_period(d.month, d.day) for d in date_range],
        index=date_range,
        dtype=bool,
    )
    max_off_season = float(erq_rel[off_season_mask].max())
    check("ERQ release = 0 outside seasonal period (Mar 16 – Jun 14)",
          max_off_season < 0.01,
          f"max off-season release = {max_off_season:.4f} MGD")

    # --- In-season: positive releases, daily rate ≈ ERQ/120 ------------------
    in_season_mask = ~off_season_mask
    in_season_erq  = erq_rel[in_season_mask]

    # Expect releases during the first seasonal period (Jun 15 – Oct ~13, 2002)
    first_season_mask = (
        (date_range >= "2002-06-15") & (date_range <= "2002-10-15")
    )
    erq_first_season = erq_rel[first_season_mask]
    n_positive_first = (erq_first_season > 1.0).sum()
    check("ERQ release > 0 during first seasonal period (Jun 15 – Oct 15, 2002)",
          n_positive_first > 50,
          f"days with ERQ > 1 MGD in first season: {n_positive_first}")

    if n_positive_first > 0:
        median_rate = float(erq_first_season[erq_first_season > 1.0].median())
        check_near("Median in-season daily rate ≈ 583 MGD (= 70,000 / 120)",
                   median_rate, MAX_ERQ_MG / SEASONAL_DAYS, tol=50.0,
                   detail=f"median observed = {median_rate:.1f} MGD")

    # --- Annual exhaustion: releases stop before March 15 -------------------
    # By ~Oct 13 (120 days from Jun 15) the bank should be exhausted
    oct13_2002 = pd.Timestamp("2002-10-14")
    nov01_2002 = pd.Timestamp("2002-11-01")
    if nov01_2002 in erq_rel.index:
        nov_release = float(erq_rel.loc[nov01_2002])
        check("ERQ release = 0 by Nov 1 (bank exhausted after ~120 days)",
              nov_release < 1.0,
              f"release on Nov 1 2002 = {nov_release:.2f} MGD")

    # --- Annual cycle: new ERQ restarts Jun 15 of each year -----------------
    jun15_2003 = pd.Timestamp("2003-06-15")
    if jun15_2003 in erq_rel.index:
        rate_2003 = float(erq_rel.loc[jun15_2003])
        check_near("New seasonal cycle begins Jun 15 2003 (release > 0)",
                   rate_2003, MAX_ERQ_MG / SEASONAL_DAYS, tol=100.0,
                   detail=f"Jun 15 2003 release = {rate_2003:.1f} MGD")

    # --- Recompute expected ERQ from simulated delivery and compare ----------
    print("\n  Verifying: recomputing ERQ from delivery_nyc time series …")
    erq_sim, remaining_sim, annual_sim = _simulate_erq(date_range, nyc_del)

    n_match   = (np.abs(erq_rel.values - erq_sim.values) < 1.0).sum()
    pct_match = 100.0 * n_match / T
    check(f"Model erq_release_nyc matches pure-Python simulation ≥ 95% of days",
          pct_match >= 95.0,
          f"match: {n_match}/{T} ({pct_match:.2f}%)")

    # --- Downstream benefit: ERQ adds to Trenton flow during season ----------
    trenton_in  = trenton[first_season_mask]
    erq_in      = erq_rel[first_season_mask]
    if len(trenton_in) > 10:
        avg_trenton_in_season  = float(trenton_in.mean())
        avg_erq_contribution   = float(erq_in.mean())
        pct_erq_of_trenton     = 100.0 * avg_erq_contribution / avg_trenton_in_season
        print(f"\n  --- ERQ downstream contribution (first season 2002) ---")
        print(f"  Avg Trenton flow in season : {avg_trenton_in_season:.1f} MGD")
        print(f"  Avg ERQ contribution       : {avg_erq_contribution:.1f} MGD")
        print(f"  ERQ as % of Trenton flow   : {pct_erq_of_trenton:.1f}%")
        check("ERQ contributes > 0% to Trenton flow in season",
              pct_erq_of_trenton > 0.0,
              f"ERQ = {avg_erq_contribution:.1f} MGD = {pct_erq_of_trenton:.1f}% of Trenton")

    print(f"\nIntegration tests: {failures} failure(s)")
    return failures, date_range, erq_rel, nyc_del, trenton, erq_sim, remaining_sim, annual_sim


# ===========================================================================
# PART 3  —  DIAGNOSTIC PLOTS
# ===========================================================================

def make_diagnostic_plots(
    date_range, erq_model, nyc_del, trenton, erq_sim, remaining_sim, annual_sim
):
    """
    5-panel diagnostic figure: figures/erq_diagnostic.png

    Panel 1: NYC annual delivery vs safe yield floor — shows cap always binds
    Panel 2: erq_release_nyc daily timeseries — seasonal on/off pattern
    Panel 3: ERQ bank balance (remaining MG) — drawdown and annual reset
    Panel 4: erq_cap_mg sensitivity — daily rate at 50/70/100 BG caps
    Panel 5: Trenton flow with ERQ contribution highlighted
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import matplotlib.dates as mdates
    import matplotlib.ticker as ticker

    print("\n" + "=" * 60)
    print("PART 3 — DIAGNOSTIC PLOTS")
    print("=" * 60)

    # Focus window for panels 2-5: 2001-10-01 to 2004-12-31 (full run)
    STAGE_COLORS = {
        "season":     "#d6eaf8",   # light blue — seasonal period
        "offseason":  "#fdfefe",   # white — off-season
        "cap":        "#fadbd8",   # light red — cap bound
    }

    def shade_season(ax, date_range):
        """Shade June 15 – March 15 seasonal periods."""
        in_season = np.array([_in_seasonal_period(d.month, d.day) for d in date_range])
        i = 0
        while i < len(date_range):
            if in_season[i]:
                j = i
                while j < len(date_range) and in_season[j]:
                    j += 1
                ax.axvspan(date_range[i], date_range[min(j, len(date_range)-1)],
                           alpha=0.18, color=STAGE_COLORS["season"], zorder=0)
                i = j
            else:
                i += 1

    fig, axes = plt.subplots(
        5, 1,
        figsize=(15, 16),
        gridspec_kw={"height_ratios": [2, 2, 2, 1.5, 2]},
        sharex=False,   # panels 1 differs (annual bar chart)
    )
    fig.suptitle(
        "ERQ (Excess Release Quantity) — Implementation Diagnostics\n"
        "1954 Decree Art. III-B-1(c)-(d)  ·  nhmv10 · Oct 2001 – Dec 2004",
        fontsize=13, fontweight="bold", y=0.995,
    )

    # =========================================================================
    # Panel 1: Annual NYC delivery vs safe yield — bar chart
    # =========================================================================
    ax1 = axes[0]

    # Compute annual consumption from nyc_del
    nyc_annual = nyc_del.resample("YE").sum() / 365.25   # convert MG/yr → avg MGD
    years = [str(y.year) for y in nyc_annual.index]

    # Also compute raw and capped ERQ
    raw_erq_mgd   = []
    capped_erq_mgd = []
    for yr_idx in nyc_annual.index:
        consumption_mg = float(nyc_del[str(yr_idx.year)].sum())
        raw  = DEFAULT_ERQ_FRACTION * max(0, NYC_SAFE_YIELD_ANNUAL_MG - consumption_mg)
        cap  = min(raw, MAX_ERQ_MG)
        # Convert to MGD for comparison
        raw_erq_mgd.append(raw / 365.25)
        capped_erq_mgd.append(cap / SEASONAL_DAYS)  # daily rate during season

    x = np.arange(len(years))
    w = 0.3

    bars1 = ax1.bar(x - w, nyc_annual.values,   width=w, color="#2980b9", alpha=0.8,
                    label="NYC annual delivery (MGD avg)")
    bars2 = ax1.bar(x,     raw_erq_mgd,          width=w, color="#e74c3c", alpha=0.5,
                    label="Raw ERQ rate (MGD avg)")  # rarely visible — off-chart
    bars3 = ax1.bar(x + w, capped_erq_mgd,       width=w, color="#27ae60", alpha=0.8,
                    label=f"Capped ERQ daily rate (ERQ/{SEASONAL_DAYS} days, MGD)")

    ax1.axhline(NYC_SAFE_YIELD_FLOOR_MGD, color="#c0392b", ls="--", lw=1.5,
                label=f"Safe yield floor ({NYC_SAFE_YIELD_FLOOR_MGD:.0f} MGD, Art. III-B-1(c))")
    ax1.axhline(MAX_ERQ_MG / SEASONAL_DAYS, color="#27ae60", ls=":",  lw=1.2,
                label=f"Baseline ERQ daily rate ({MAX_ERQ_MG/SEASONAL_DAYS:.0f} MGD = 70 BG / 120 d)")

    ax1.set_xticks(x)
    ax1.set_xticklabels(years, fontsize=9)
    ax1.set_ylabel("MGD", fontsize=10)
    ax1.set_title(
        "Annual NYC Delivery vs. Safe Yield Floor — ERQ Cap Always Binds\n"
        "Art. III-B-1(c): ERQ = 0.83 × max(0, 1665 MGD × 365 − consumption) → always > 70 BG cap",
        fontsize=9, loc="left",
    )
    ax1.legend(fontsize=8, loc="upper right")
    ax1.set_ylim(0, NYC_SAFE_YIELD_FLOOR_MGD * 1.2)

    # Annotate "cap binds" on each bar
    for i, (raw, cap) in enumerate(zip(raw_erq_mgd, capped_erq_mgd)):
        if raw > NYC_SAFE_YIELD_FLOOR_MGD:
            ax1.text(i, cap + 10, "cap\nbinds", ha="center", fontsize=6,
                     color="#c0392b", fontweight="bold")

    # =========================================================================
    # Panel 2: Daily ERQ release timeseries
    # =========================================================================
    ax2 = axes[1]
    shade_season(ax2, date_range)

    if erq_model is not None:
        ax2.step(date_range, erq_model.values, where="post",
                 color="#2980b9", lw=1.5, label="erq_release_nyc (model)")
    ax2.step(date_range, erq_sim.values, where="post",
             color="#c0392b", lw=1.0, ls="--", alpha=0.8,
             label="ERQ simulated from delivery_nyc (pure Python)")

    ax2.axhline(MAX_ERQ_MG / SEASONAL_DAYS, color="#27ae60", ls=":", lw=1.2,
                label=f"Decree rate = 70,000 MG / 120 d = {MAX_ERQ_MG/SEASONAL_DAYS:.1f} MGD")

    ax2.set_ylabel("ERQ release\n(MGD, all NYC)", fontsize=10)
    ax2.set_ylim(-20, MAX_ERQ_MG / SEASONAL_DAYS * 1.5)
    ax2.legend(fontsize=8, loc="upper right")
    ax2.set_title(
        "erq_release_nyc Daily Series  (blue shading = Art. III-B-1(d) seasonal period June 15 – Mar 15)",
        fontsize=9, loc="left",
    )

    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # =========================================================================
    # Panel 3: ERQ bank balance (remaining)
    # =========================================================================
    ax3 = axes[2]
    shade_season(ax3, date_range)

    ax3.fill_between(date_range, 0, remaining_sim.values,
                     step="post", alpha=0.5, color="#2980b9",
                     label="ERQ remaining balance (MG)")
    ax3.axhline(MAX_ERQ_MG, color="#c0392b", ls="--", lw=1.2,
                label=f"Annual cap = {MAX_ERQ_MG:,.0f} MG (70 BG, Art. III-B-1(d))")
    ax3.axhline(0, color="k", lw=0.5)

    ax3.set_ylabel("ERQ remaining\nbalance (MG)", fontsize=10)
    ax3.set_ylim(-2000, MAX_ERQ_MG * 1.25)
    ax3.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}k"))
    ax3.legend(fontsize=8, loc="upper right")
    ax3.set_title(
        "Annual ERQ Bank Balance — Drawdown Jun 15 → Exhaustion ~Oct 13, Reset Jun 1",
        fontsize=9, loc="left",
    )

    # Annotate annual resets (June 1)
    for yr in range(2002, 2005):
        reset_date = pd.Timestamp(f"{yr}-06-01")
        if reset_date in remaining_sim.index:
            ax3.axvline(reset_date, color="#27ae60", lw=0.8, ls=":", alpha=0.7)
            ax3.text(reset_date, MAX_ERQ_MG * 0.9, f"Jun 1\n{yr}\nreset",
                     fontsize=6.5, color="#27ae60", ha="center")

    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # =========================================================================
    # Panel 4: erq_cap_mg sensitivity  — static comparison (no model run)
    # =========================================================================
    ax4 = axes[3]

    cap_scenarios  = [50_000, 70_000, 100_000]
    cap_labels     = ["50 BG (− 29%)", "70 BG (Decree baseline)", "100 BG (+ 43%)"]
    cap_colors     = ["#e74c3c", "#2980b9", "#27ae60"]
    cap_linestyles = ["--", "-", ":"]

    # Build a synthetic seasonal period to show daily rate vs remaining
    seasonal_days = np.arange(0, 140)
    for cap_mg, label, color, ls in zip(cap_scenarios, cap_labels, cap_colors, cap_linestyles):
        daily_rate   = cap_mg / SEASONAL_DAYS
        remaining_pct = np.maximum(0, 100.0 * (1.0 - seasonal_days / SEASONAL_DAYS))
        ax4.plot(seasonal_days, remaining_pct, color=color, lw=2.0, ls=ls,
                 label=f"{label}  →  {daily_rate:.0f} MGD/day")

    ax4.axvline(SEASONAL_DAYS, color="k", lw=0.8, ls="--", alpha=0.5)
    ax4.text(SEASONAL_DAYS + 1, 50, "Day 120\n(Oct 13)", fontsize=7)

    ax4.set_xlabel("Days since Jun 15", fontsize=10)
    ax4.set_ylabel("ERQ remaining (%)", fontsize=10)
    ax4.set_xlim(0, 140)
    ax4.set_ylim(-5, 115)
    ax4.yaxis.set_major_formatter(ticker.PercentFormatter())
    ax4.legend(fontsize=8, loc="upper right")
    ax4.set_title(
        "erq_cap_mg Sensitivity — Key Sobol Parameter (erq_fraction is flat at typical NYC consumption)\n"
        "Art. III-B-1(d): cap of 70 BG is the binding term, not the 0.83 fraction",
        fontsize=9, loc="left",
    )

    # =========================================================================
    # Panel 5: Trenton flow with ERQ highlighted
    # =========================================================================
    ax5 = axes[4]
    shade_season(ax5, date_range)

    if trenton is not None:
        base_trenton = trenton - (erq_sim / 3.0)   # rough: 1/3 to each reservoir, travel ~2-4 d
        base_trenton = base_trenton.clip(lower=0)

        ax5.fill_between(date_range, 0, base_trenton.values,
                         step="post", alpha=0.5, color="#7f8c8d",
                         label="Trenton flow (excl. ERQ contribution)")
        ax5.fill_between(date_range, base_trenton.values, trenton.values,
                         step="post", alpha=0.7, color="#2980b9",
                         label="ERQ contribution (≈ 1/3 per reservoir, ~4 d travel)")

    ax5.axhline(1938.95, color="#c0392b", ls="--", lw=1.2,
                label="Trenton MRF baseline (1938.95 MGD)")
    ax5.set_ylabel("Del Trenton flow\n(MGD)", fontsize=10)
    ax5.set_ylim(bottom=0)
    ax5.legend(fontsize=8, loc="upper right")
    ax5.set_title(
        "Delaware River at Trenton — ERQ Contribution to Downstream Flow\n"
        "Art. III-B-1(d): ERQ released 'in addition to the quantity required to maintain the minimum basic rate'",
        fontsize=9, loc="left",
    )

    ax5.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    ax5.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))

    # =========================================================================
    # Legend patches for seasonal shading
    # =========================================================================
    legend_patches = [
        mpatches.Patch(color=STAGE_COLORS["season"], alpha=0.5,
                       label="Seasonal period: June 15 – March 15  (Art. III-B-1(d))"),
        mpatches.Patch(color="white", alpha=0.5,
                       label="Off-season: March 16 – June 14  (no ERQ release)"),
    ]
    fig.legend(handles=legend_patches, loc="lower center", ncol=2,
               fontsize=9, frameon=True, bbox_to_anchor=(0.5, 0.00))

    plt.tight_layout(rect=[0, 0.03, 1, 0.995])

    fig_path = str(FIGDIR / "erq_diagnostic.png")
    plt.savefig(fig_path, dpi=150, bbox_inches="tight")
    print(f"  Figure saved → {fig_path}")
    plt.close()
    return fig_path


# ===========================================================================
# MAIN
# ===========================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="Validate ERQRelease implementation (1954 Decree Art. III-B-1(c)-(d))."
    )
    parser.add_argument("--rerun",     action="store_true",
                        help="Force re-run of the integration model even if HDF5 exists")
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
    result = run_integration_tests(data)
    failures        = result[0]
    date_range      = result[1]
    erq_model       = result[2]
    nyc_del         = result[3]
    trenton         = result[4]
    erq_sim         = result[5]
    remaining_sim   = result[6]
    annual_sim      = result[7]
    total_failures += failures

    # Part 3 — diagnostic plots
    fig_path = make_diagnostic_plots(
        date_range, erq_model, nyc_del, trenton,
        erq_sim, remaining_sim, annual_sim,
    )

    # ---- Summary -------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"SUMMARY:  {total_failures} total failure(s)")
    print(f"Figure:   {fig_path}")
    print("=" * 60)

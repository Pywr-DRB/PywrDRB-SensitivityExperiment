"""
D4 Sobol Sensitivity Analysis — experiment configuration.

All tunable constants for the sensitivity design live here.
Change N_SOBOL_BASE or PARAMETERS here; everything else picks up automatically.

Design
------
SALib Saltelli sampling: N_SOBOL_BASE * (2 * k + 2) total model evaluations,
where k = len(PARAMETERS).

Sweep history
-------------
Sweep 1 (complete, 2026-06-02):
    k=6 (alpha_betz, alpha_bm, m_lb, tau_recovery, q_nj_warning, ierq_max_bg)
    N=1024 → TOTAL_RUNS = 14,336
    Status: COMPLETE. Effectively k=3 active (m_lb, q_nj_warning, ierq_max_bg
    were placeholders — no injection). tau_recovery near-zero effect empirically.

Sweep 2 (complete, 2026-06-03):
    k=7 (adds erq_cap_mg — 1954 Decree Art. III-B-1(d) cap)
    N=1024 → TOTAL_RUNS = 16,384
    Status: COMPLETE (7,812/16,384 as of last check — verify before using).
    Effectively k=4 active (adds erq_cap_mg; other 3 still placeholders).

Sweep 3 (this config — 2026-06-03):
    k=6 ALL ACTIVE: alpha_betz, alpha_bm, m_lb, ierq_max_bg, erq_cap_mg, q_nj_warning
    Drops: tau_recovery (empirically near-zero in sweeps 1+2)
    N=1024 → TOTAL_RUNS = 14,336
    Rationale: framework diagnostic (rq3_experimental_framework_check.py) showed
    tau_recovery has negligible marginal effect; m_lb, ierq_max_bg, q_nj_warning
    are now fully wired (2026-06-03); erq_cap_mg carried from sweep 2.
    To submit:
        python sensitivity/sobol_design.py --outdir results/sobol_sweep3
        bash slurm/batch_submit_sobol.sh --sweep3
"""

# ---------------------------------------------------------------------------
# SALib design
# ---------------------------------------------------------------------------

N_SOBOL_BASE: int = 1024          # Base sample count N; total = N*(2k+2)
                                   # Reduce to 512 if committee endorses (D4-3)

# Representative Amestoy subset for Sobol (reduces total runs)
# Selected by matching streamflow distribution moments to the full 1000-member ensemble.
SOBOL_ENSEMBLE_SUBSET: int = 50   # members; see Steinschneider & Brown (2013)

# ---------------------------------------------------------------------------
# Parameters — bounds define the Saltelli sampling space
# Each entry: (lower_bound, upper_bound)
# Baseline values are in the "baseline" key — used for the reference run.
# ---------------------------------------------------------------------------

PARAMETERS: dict = {
    # LB warning thresholds (§2.5.6.C — Elev. 615/283 m.s.l.)
    # ACTIVE — wired via LowerBasinDroughtLevel kwargs
    "alpha_betz_warning": {
        "baseline": 0.737,
        "bounds":   [0.64, 0.84],
        "label":    "Beltzville Warning Frac (α_BW)",
        "decree":   "FFMP §2.5.6.C; Water Code §2.5.6.C",
        "rq":       "RQ2",
        "status":   "ACTIVE",
    },
    "alpha_bm_warning": {
        "baseline": 0.689,
        "bounds":   [0.59, 0.79],
        "label":    "Blue Marsh Warning Frac (α_BMW)",
        "decree":   "FFMP §2.5.6.C",
        "rq":       "RQ2",
        "status":   "ACTIVE",
    },
    # LB max MRF contribution multiplier
    # ACTIVE — wired via _inject_lb_cap_multiplier() → cap_multiplier kwarg
    "m_lb": {
        "baseline": 1.0,
        "bounds":   [0.75, 1.25],
        "label":    "LB Max MRF Multiplier (m_LB)",
        "decree":   "FFMP §2.5.5 Table 3; Water Code §2.5.3",
        "rq":       "RQ2; RQ3 (PA-NYC redistribution)",
        "status":   "ACTIVE",
    },
    # IERQ annual ceiling
    # ACTIVE — wired via max_bank_volume kwarg on IERQRelease_step1 (2026-06-03)
    "ierq_max_bg": {
        "baseline": 6.09,
        "bounds":   [4.0, 9.0],
        "label":    "IERQ Annual Ceiling BG/yr (I_max)",
        "decree":   "Art. VII; FFMP §2.c.i",
        "rq":       "RQ2; RQ3 (potential win-win: NYC reliability up, others neutral)",
        "status":   "ACTIVE",
    },
    # ERQ seasonal cap — 1954 Decree Art. III-B-1(d)
    # ACTIVE — wired via erq_cap_mg on ERQRelease parameter (sweep 2+)
    "erq_cap_mg": {
        "baseline": 70_000.0,
        "bounds":   [50_000.0, 100_000.0],
        "label":    "ERQ Seasonal Cap MG (C_ERQ)",
        "decree":   "1954 Decree Art. III-B-1(d)",
        "rq":       "RQ2; RQ3",
        "status":   "ACTIVE",
    },
    # NJ warning delivery cap
    # ACTIVE — wired via lb_level1_factor_delivery_nj model_dict patch (2026-06-03)
    "q_nj_warning": {
        "baseline": 70.0,
        "bounds":   [55.0, 85.0],
        "label":    "NJ Warning Cap MGD (Q_NJ_W)",
        "decree":   "FFMP §2.5.6.C.1",
        "rq":       "RQ2; RQ3 (NJ party — direct cap on NJ diversion)",
        "status":   "ACTIVE",
    },
}

# Convenience lists for SALib
PARAM_NAMES  = list(PARAMETERS.keys())
PARAM_BOUNDS = [v["bounds"] for v in PARAMETERS.values()]
K            = len(PARAMETERS)
TOTAL_RUNS   = N_SOBOL_BASE * (2 * K + 2)

# ---------------------------------------------------------------------------
# Output metrics targeted by sensitivity analysis
# ---------------------------------------------------------------------------

TARGET_METRICS: list[str] = [
    "de_reliability",
    "de_vulnerability",
    "nyc_ierq_exhaustion_days",
    "pa_depletion_days",
    "nj_lb_restriction_days",
    "ny_reliability",
]

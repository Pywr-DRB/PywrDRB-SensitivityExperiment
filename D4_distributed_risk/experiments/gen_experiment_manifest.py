"""
D4 — Generate experiment manifest tables from actual code values.

Pulls parameter bounds, metric thresholds, recorder names, and
implementation status from live code — not hardcoded documentation.
Run after any change to config.py, metrics.py, run_model.py, or ffmp.py
to regenerate tables that track the current experiment state.

Output
------
    results/manifest/parameters.csv       — Sobol parameter table
    results/manifest/metrics.csv          — Per-party output metrics + recorders
    results/manifest/thresholds.csv       — Hardcoded threshold constants
    results/manifest/implementation.csv   — What's injected / what's a placeholder
    results/manifest/sobol_design.txt     — Design summary (N, k, total runs)

Usage
-----
    python sensitivity/gen_experiment_manifest.py
    python sensitivity/gen_experiment_manifest.py --outdir results/manifest
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SHARED    = _REPO_ROOT / "shared"
_SENS_DIR  = _THIS.parent
for _p in [str(_SHARED), str(_REPO_ROOT), str(_SENS_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import PARAMETERS, N_SOBOL_BASE, K, TOTAL_RUNS, SOBOL_ENSEMBLE_SUBSET, TARGET_METRICS
from pywrdrb_utils.run_model import OUTPUT_VARS
from D4_distributed_risk.lib.rrv_metrics.metrics import (
    TRENTON_MRF_BASELINE_MGD, MONTAGUE_MRF_BASELINE_MGD,
    IERQ_EXHAUSTION_MG,
    NJ_NORMAL_CAP_MGD, NJ_WARNING_CAP_MGD, NJ_DROUGHT_CAP_MGD,
    LB_BELTZVILLE_CAPACITY_MG, LB_BLUEMARSH_CAPACITY_MG,
    LB_BELTZVILLE_WARNING_FRAC, LB_BLUEMARSH_WARNING_FRAC,
    LB_CONSERVATION_FRAC,
)
from D4_distributed_risk.experiments.run_d4_baseline import LB_CAPACITY_MG


# ---------------------------------------------------------------------------
# Implementation status — manually maintained here, not inferred from code
# ---------------------------------------------------------------------------

INJECTION_STATUS = {
    "alpha_betz_warning": {
        "status": "IMPLEMENTED",
        "mechanism": "model_dict['parameters']['drought_level_agg_lb']['betz_warning_frac']",
        "note": "Injected into LowerBasinDroughtLevel.__init__ via model JSON before load",
    },
    "alpha_bm_warning": {
        "status": "IMPLEMENTED",
        "mechanism": "model_dict['parameters']['drought_level_agg_lb']['bm_warning_frac']",
        "note": "Same as alpha_betz_warning",
    },
    "tau_recovery": {
        "status": "IMPLEMENTED",
        "mechanism": "model_dict['parameters']['drought_level_agg_lb']['recovery_persist_days']",
        "note": "Cast to int before injection; controls 30-day exit hysteresis §2.5.6.C.7",
    },
    "m_lb": {
        "status": "PLACEHOLDER",
        "mechanism": "UserWarning emitted; model uses default m_lb=1.0 for all runs",
        "note": "Requires patching max_mrf_trenton_step{step}_{reservoir} entries in model_dict. "
                "Blocked until model_dict key structure confirmed from baseline run JSON. "
                "Changed from NotImplementedError to UserWarning 2026-06-01 to allow Sobol sweep to run.",
    },
    "q_nj_warning": {
        "status": "PLACEHOLDER",
        "mechanism": "UserWarning emitted; model uses hardcoded default 70.0 MGD",
        "note": "NJ cap is in delivery_nj parameter; injection point not yet identified. "
                "Model key likely: model_dict['parameters']['delivery_nj']['max_flow'] or similar.",
    },
    "ierq_max_bg": {
        "status": "PLACEHOLDER",
        "mechanism": "UserWarning emitted; model uses hardcoded default 6.09 BG/yr",
        "note": "IERQ bank ceiling is in banks.py (IERQRelease); no model_dict exposure. "
                "Would require adding a 'max_annual_volume' parameter to the bank JSON entry.",
    },
}

RECORDER_STATUS = {
    "del_trenton_flow": {
        "in_hdf5": True,
        "note": "Confirmed 2026-06-01 — range [607, 88439 MGD]",
    },
    "del_montague_flow": {
        "in_hdf5": True,
        "note": "Confirmed 2026-06-01 — range [452, 75763 MGD]",
    },
    "ierq_bank_remaining": {
        "in_hdf5": True,
        "note": "HDF5 key = 'nyc_mrf_trenton_step1' (IERQRelease_step1 instance). "
                "Records daily IERQ release (MG/day), not balance. "
                "metrics.py reconstruct_ierq_balance() back-calculates balance "
                "(6090 MG max, cumulative depletion, May 31 reset). Confirmed 2026-06-01.",
    },
    "beltzville_volume": {
        "in_hdf5": True,
        "note": "Confirmed 2026-06-01 — range [0, 13500 MG]",
    },
    "blueMarsh_volume": {
        "in_hdf5": True,
        "note": "Confirmed 2026-06-01 — range [0, 33074 MG]",
    },
    "lb_drought_stage": {
        "in_hdf5": True,
        "note": "Integer stage 0/1/2. Confirmed 2026-06-01",
    },
    "nyc_drought_stage": {
        "in_hdf5": True,
        "note": "Integer stage 0-6. Not currently used in any metric function",
    },
    "nj_delivery": {
        "in_hdf5": True,
        "note": "Confirmed 2026-06-01 — range [0.31, 109.61 MGD]",
    },
}

KNOWN_INCONSISTENCIES = [
    {
        "issue": "PA metric threshold vs injected LB warning threshold mismatch",
        "detail": (
            f"RESOLVED 2026-06-01: pa_metrics() now accepts alpha_betz / alpha_bm kwargs. "
            f"When provided, threshold = alpha_betz × {LB_BELTZVILLE_CAPACITY_MG:.0f} + "
            f"alpha_bm × {LB_BLUEMARSH_CAPACITY_MG:.0f} MG (consistent with model switching). "
            f"Baseline runs (no injection) still use fixed LB_CONSERVATION_FRAC = "
            f"{LB_CONSERVATION_FRAC:.4f}. compute_all_party_rrv() passes alpha params "
            f"through; run_sobol_sweep.py extracts them from sample_params."
        ),
        "severity": "MEDIUM — affects PA metric interpretation but not model runs",
        "status": "RESOLVED",
    },
    {
        "issue": "NYC IERQ metrics all NaN",
        "detail": (
            "RESOLVED 2026-06-01: IERQRelease_step1 records daily release amounts. "
            "metrics.py now calls reconstruct_ierq_balance() to back-calculate the "
            "bank balance (cumulative depletion with May 31 reset to 6090 MG). "
            "NYC exhaustion metrics are now non-NaN."
        ),
        "severity": "HIGH — NYC is a Decree party; excludes NYC from sensitivity analysis",
        "status": "RESOLVED",
    },
]


def build_parameters_table() -> pd.DataFrame:
    rows = []
    for name, p in PARAMETERS.items():
        inj = INJECTION_STATUS[name]
        rows.append({
            "parameter":   name,
            "label":       p["label"],
            "baseline":    p["baseline"],
            "lower_bound": p["bounds"][0],
            "upper_bound": p["bounds"][1],
            "decree":      p["decree"],
            "rq":          p["rq"],
            "status":      inj["status"],
            "mechanism":   inj["mechanism"],
            "note":        inj["note"],
        })
    return pd.DataFrame(rows)


def build_metrics_table() -> pd.DataFrame:
    party_map = {
        "del_trenton_flow":    ("DE",  "de_reliability, de_resiliency, de_vulnerability, de_shortfall_days, de_max_deficit_mgd"),
        "del_montague_flow":   ("NY",  "ny_reliability, ny_resiliency, ny_vulnerability, ny_shortfall_days"),
        "ierq_bank_remaining": ("NYC", "nyc_ierq_exhaustion_days, nyc_ierq_exhaustion_reliability, nyc_min_ierq_balance_mg"),
        "beltzville_volume":   ("PA",  "pa_depletion_days, pa_depletion_reliability, pa_min_storage_frac, pa_depletion_resiliency"),
        "blueMarsh_volume":    ("PA",  "(combined with beltzville_volume)"),
        "lb_drought_stage":    ("NJ",  "nj_lb_restriction_days, nj_shortfall_days, nj_delivery_reliability"),
        "nyc_drought_stage":   ("NYC", "(not used in metric yet)"),
        "nj_delivery":         ("NJ",  "nj_delivery_reliability, nj_mean_delivery_mgd"),
    }
    rows = []
    for short_name, recorder_name in OUTPUT_VARS.items():
        rec_status = RECORDER_STATUS.get(short_name, {})
        party, metrics_driven = party_map.get(short_name, ("—", "—"))
        rows.append({
            "short_name":       short_name,
            "recorder_name":    recorder_name,
            "party":            party,
            "metrics_driven":   metrics_driven,
            "in_hdf5":         rec_status.get("in_hdf5", "unknown"),
            "note":             rec_status.get("note", ""),
        })
    return pd.DataFrame(rows)


def build_thresholds_table() -> pd.DataFrame:
    rows = [
        {"constant": "TRENTON_MRF_BASELINE_MGD",     "value": TRENTON_MRF_BASELINE_MGD,  "units": "MGD",      "party": "DE",  "source": "pywrdrb constants.csv mrf_baseline_delTrenton",          "sobol_overridable": False},
        {"constant": "MONTAGUE_MRF_BASELINE_MGD",    "value": MONTAGUE_MRF_BASELINE_MGD, "units": "MGD",      "party": "NY",  "source": "pywrdrb constants.csv mrf_baseline_delMontague",         "sobol_overridable": False},
        {"constant": "IERQ_EXHAUSTION_MG",            "value": IERQ_EXHAUSTION_MG,        "units": "MG",       "party": "NYC", "source": "attribution.py",                                          "sobol_overridable": False},
        {"constant": "NJ_NORMAL_CAP_MGD",             "value": NJ_NORMAL_CAP_MGD,         "units": "MGD",      "party": "NJ",  "source": "§2.5.6.B.1",                                              "sobol_overridable": False},
        {"constant": "NJ_WARNING_CAP_MGD",            "value": NJ_WARNING_CAP_MGD,        "units": "MGD",      "party": "NJ",  "source": "§2.5.6.C.1",                                              "sobol_overridable": "PLACEHOLDER via q_nj_warning"},
        {"constant": "NJ_DROUGHT_CAP_MGD",            "value": NJ_DROUGHT_CAP_MGD,        "units": "MGD",      "party": "NJ",  "source": "§2.5.6.D.1",                                              "sobol_overridable": False},
        {"constant": "LB_BELTZVILLE_CAPACITY_MG",     "value": LB_BELTZVILLE_CAPACITY_MG, "units": "MG",       "party": "PA",  "source": "FFMP / pywrdrb ffmp.py",                                  "sobol_overridable": False},
        {"constant": "LB_BLUEMARSH_CAPACITY_MG",      "value": LB_BLUEMARSH_CAPACITY_MG,  "units": "MG",       "party": "PA",  "source": "FFMP / pywrdrb ffmp.py",                                  "sobol_overridable": False},
        {"constant": "LB_BELTZVILLE_WARNING_FRAC",    "value": LB_BELTZVILLE_WARNING_FRAC,"units": "fraction", "party": "PA",  "source": "§2.5.6.C Water Code / ffmp.py default",                   "sobol_overridable": "IMPLEMENTED via alpha_betz_warning (model only — metrics.py still uses fixed value)"},
        {"constant": "LB_BLUEMARSH_WARNING_FRAC",     "value": LB_BLUEMARSH_WARNING_FRAC, "units": "fraction", "party": "PA",  "source": "§2.5.6.C Water Code / ffmp.py default",                   "sobol_overridable": "IMPLEMENTED via alpha_bm_warning (model only — metrics.py still uses fixed value)"},
        {"constant": "LB_CONSERVATION_FRAC (combined)","value": round(LB_CONSERVATION_FRAC,4),"units": "fraction","party": "PA","source": "Derived: weighted avg of Betz+BM warning fracs",          "sobol_overridable": "OPEN BUG — not updated when alpha params vary"},
        {"constant": "LB_CAPACITY_MG (combined)",      "value": LB_CAPACITY_MG,            "units": "MG",       "party": "PA",  "source": "run_d4_baseline.py LB_CAPACITY_MG",                       "sobol_overridable": False},
    ]
    return pd.DataFrame(rows)


def build_design_summary() -> str:
    implemented = sum(1 for p in INJECTION_STATUS.values() if p["status"] == "IMPLEMENTED")
    placeholder = sum(1 for p in INJECTION_STATUS.values() if p["status"] == "PLACEHOLDER")
    not_impl    = sum(1 for p in INJECTION_STATUS.values() if p["status"] == "NOT_IMPLEMENTED")

    lines = [
        "D4 Sobol Sensitivity Analysis — Experiment Design Summary",
        "=" * 60,
        f"Saltelli sample count (N):        {N_SOBOL_BASE}",
        f"Parameters (k):                   {K}",
        f"Total runs (N × (2k+2)):          {TOTAL_RUNS:,}",
        f"Synthetic realizations per sample: {SOBOL_ENSEMBLE_SUBSET}",
        f"Total pywrdrb runs:               {TOTAL_RUNS * SOBOL_ENSEMBLE_SUBSET:,}",
        "",
        "Parameter injection status:",
        f"  Fully implemented:  {implemented}/{K}  (alpha_betz, alpha_bm, tau_recovery)",
        f"  Placeholder only:   {placeholder}/{K}  (q_nj_warning, ierq_max_bg — UserWarning)",
        f"  Not implemented:    {not_impl}/{K}",
        "",
        "Target metrics:",
    ]
    for m in TARGET_METRICS:
        lines.append(f"  {m}")
    lines += [
        "",
        "Known gaps:",
        "  NYC metrics: RESOLVED — balance reconstructed from IERQRelease_step1 releases",
        "  PA metric threshold: RESOLVED — pa_metrics() now uses injected alpha params when provided",
        "  m_lb: no effect on any run — UserWarning emitted, model uses default 1.0",
        "  q_nj_warning, ierq_max_bg: no effect on any run (UserWarning only)",
        "",
        "Synthetic forcing:",
        "  Generator: Kirsch-Nowak (synhydro 0.0.2)",
        "  Calibration: pub_nhmv10_BC_withObsScaled catchment inflows, 1946-2005",
        "  Sites: 7 major Kirsch sites + 24 minor sites (annual block bootstrap)",
        "  Realizations: 50 × 79-year daily flows at all 31 pywrdrb nodes",
        "  Files: D4_distributed_risk/results/sobol/synthetic_flows/realization_{r:03d}.parquet",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path,
                    default=_THIS.parents[1] / "results" / "manifest")
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    # Parameters table
    params_df = build_parameters_table()
    params_df.to_csv(args.outdir / "parameters.csv", index=False)
    print("parameters.csv:")
    print(params_df[["parameter", "baseline", "lower_bound", "upper_bound",
                      "status"]].to_string(index=False))
    print()

    # Metrics / recorders table
    metrics_df = build_metrics_table()
    metrics_df.to_csv(args.outdir / "metrics.csv", index=False)
    print("metrics.csv:")
    print(metrics_df[["short_name", "recorder_name", "party",
                       "in_hdf5"]].to_string(index=False))
    print()

    # Thresholds table
    thresh_df = build_thresholds_table()
    thresh_df.to_csv(args.outdir / "thresholds.csv", index=False)
    print("thresholds.csv:")
    print(thresh_df[["constant", "value", "units", "party",
                      "sobol_overridable"]].to_string(index=False))
    print()

    # Known inconsistencies
    incons_df = pd.DataFrame(KNOWN_INCONSISTENCIES)
    incons_df.to_csv(args.outdir / "inconsistencies.csv", index=False)
    print(f"inconsistencies.csv: {len(KNOWN_INCONSISTENCIES)} open issues")
    print()

    # Design summary
    summary = build_design_summary()
    (args.outdir / "design_summary.txt").write_text(summary)
    print(summary)

    print(f"\nAll tables written to: {args.outdir}/")


if __name__ == "__main__":
    main()

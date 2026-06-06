"""
D4 Sweep 3 — Comprehensive end-to-end smoke test.

Readiness criteria (must all pass before production rerun):
  1. All 6 parameters change outputs (non-zero sensitivity)
  2. Regime metrics appear and fractions sum to 1
  3. Asymmetry metrics appear with all three weight schemes
  4. No unexpected NaNs in core metrics
  5. Valid regime labels only (0, 1, 2, 3)
  6. Output has expected columns
  7. Regime fractions sum to 1.0 within 1e-6
  8. Regime-conditioned RRV is NaN only when n_days < 30
  9. Injection is verified: each parameter at extreme → different output

Usage
-----
    cd ~/dissertation
    module load python/3.11.5 && source venv/bin/activate
    python D4_distributed_risk/sensitivity/smoke_test_sweep3.py
"""

from __future__ import annotations
import sys, pathlib, json
sys.path.insert(0, "shared"); sys.path.insert(0, ".")

import numpy as np
import pandas as pd

from pywrdrb_utils.run_model import run_single
from D4_distributed_risk.lib.rrv_metrics.metrics import compute_all_party_rrv
from D4_distributed_risk.experiments.run_d4_baseline import LB_CAPACITY_MG
import pywrdrb

PASS = "✅ PASS"
FAIL = "❌ FAIL"
results = []

def check(name: str, condition: bool, detail: str = ""):
    status = PASS if condition else FAIL
    results.append((name, status, detail))
    print(f"  {status}  {name}" + (f"  [{detail}]" if detail else ""))
    return condition

# ---------------------------------------------------------------------------
# Load observed flows for injection tests
# ---------------------------------------------------------------------------
pn = pywrdrb.get_pn_config()
flow_csv = pathlib.Path(pn["flows/pub_nhmv10_BC_withObsScaled"]) / "catchment_inflow_mgd.csv"
flow_df  = pd.read_csv(flow_csv, index_col=0, parse_dates=True)

SYN_FLOWS = pathlib.Path("D4_distributed_risk/results/sobol_sweep3/synthetic_flows")
SAMPLES   = pd.read_csv("D4_distributed_risk/results/sobol_sweep3/sobol_samples.csv", index_col=0)

print("\n=== D4 Sweep 3 End-to-End Smoke Test ===\n")

# ---------------------------------------------------------------------------
# Step 1 — Baseline run with observed flows
# ---------------------------------------------------------------------------
print("[1] Baseline run (observed flows) ...")
out_base = run_single(flow_df=flow_df, inflow_type="pub_nhmv10_BC_withObsScaled", cleanup=True)
m_base = compute_all_party_rrv(out_base, lb_capacity_mg=LB_CAPACITY_MG)

# ---------------------------------------------------------------------------
# Step 2 — Check output columns
# ---------------------------------------------------------------------------
print("\n[2] Column checks ...")

REQUIRED_PARTY = [
    "de_reliability", "de_resiliency", "de_vulnerability",
    "nyc_ierq_exhaustion_reliability", "nyc_min_ierq_balance_mg",
    "pa_depletion_reliability", "pa_depletion_resiliency",
    "nj_delivery_reliability", "nj_lb_restriction_days",
    "ny_reliability", "ny_resiliency",
]
REQUIRED_REGIME = [
    "n_days_regime_normal", "n_days_regime_nyc", "n_days_regime_lb", "n_days_regime_co",
    "regime_frac_normal", "regime_frac_nyc_limited", "regime_frac_lb_limited", "regime_frac_co_limited",
    "regime_first", "regime_n_transitions",
    "regime_n_episodes_nyc", "regime_n_episodes_lb", "regime_n_episodes_co",
    "regime_mean_persist_nyc", "regime_mean_persist_lb", "regime_mean_persist_co",
    "regime_max_persist_nyc", "regime_max_persist_lb", "regime_max_persist_co",
    "regime_nyc_before_lb",
]
REQUIRED_RCRRV = [
    "rcrrv_nyc_n_days", "rcrrv_lb_n_days", "rcrrv_co_n_days",
    "rcrrv_nyc_de_reliability", "rcrrv_lb_de_reliability", "rcrrv_co_de_reliability",
]
REQUIRED_ASYMMETRY = [
    "asym_reliability_equal", "asym_reliability_obligation", "asym_reliability_unweighted",
    "asym_gini_reliability", "asym_max_min_gap",
    "worst_party", "best_party", "r_bar_equal", "r_bar_obligation",
    "asym_contrib_de", "asym_contrib_nyc", "asym_contrib_pa", "asym_contrib_nj", "asym_contrib_ny",
]

for col in REQUIRED_PARTY:
    check(f"party metric: {col}", col in m_base)
for col in REQUIRED_REGIME:
    check(f"regime metric: {col}", col in m_base)
for col in REQUIRED_RCRRV:
    check(f"regime-conditioned RRV: {col}", col in m_base)
for col in REQUIRED_ASYMMETRY:
    check(f"asymmetry metric: {col}", col in m_base)

# ---------------------------------------------------------------------------
# Step 3 — Regime fraction integrity
# ---------------------------------------------------------------------------
print("\n[3] Regime fraction integrity ...")
frac_sum = (m_base.get("regime_frac_normal", np.nan) +
            m_base.get("regime_frac_nyc_limited", np.nan) +
            m_base.get("regime_frac_lb_limited", np.nan) +
            m_base.get("regime_frac_co_limited", np.nan))
check("Regime fractions sum to 1.0", abs(frac_sum - 1.0) < 1e-6,
      f"sum={frac_sum:.8f}")

for key in ["regime_frac_normal","regime_frac_nyc_limited","regime_frac_lb_limited","regime_frac_co_limited"]:
    v = m_base.get(key, -1)
    check(f"{key} in [0,1]", 0.0 <= v <= 1.0, f"{v:.4f}")

check("regime_first in {0,1,2,3}", m_base.get("regime_first") in {0,1,2,3},
      f"={m_base.get('regime_first')}")

# ---------------------------------------------------------------------------
# Step 4 — NaN audit (core metrics must not be NaN)
# ---------------------------------------------------------------------------
print("\n[4] NaN audit ...")
nan_keys = [k for k in REQUIRED_PARTY if np.isnan(m_base.get(k, np.nan))]
check("No NaN in core party metrics", len(nan_keys) == 0,
      f"NaN in: {nan_keys}" if nan_keys else "")

# Regime-conditioned NaN rule: NaN only when n_days < 30
for regime in ["nyc", "lb", "co"]:
    n = m_base.get(f"rcrrv_{regime}_n_days", 0)
    rel = m_base.get(f"rcrrv_{regime}_de_reliability", "MISSING")
    if n < 30:
        check(f"rcrrv_{regime}_de_reliability is NaN when n_days={n}<30",
              np.isnan(rel) if isinstance(rel, float) else True)
    else:
        check(f"rcrrv_{regime}_de_reliability is numeric when n_days={n}>=30",
              isinstance(rel, float) and not np.isnan(rel), f"={rel:.4f}" if isinstance(rel, float) else str(rel))

# ---------------------------------------------------------------------------
# Step 5 — Parameter injection verification
# ---------------------------------------------------------------------------
print("\n[5] Parameter injection — all 6 parameters produce different outputs ...")

INJECTION_TESTS = [
    ("alpha_betz_warning", 0.64,  0.84,  "pa_depletion_reliability"),
    ("alpha_bm_warning",   0.59,  0.79,  "pa_depletion_reliability"),
    ("m_lb",               0.75,  1.25,  "pa_depletion_reliability"),
    ("ierq_max_bg",        4.0,   9.0,   "nyc_ierq_exhaustion_reliability"),
    ("erq_cap_mg",         50000, 100000,"nyc_ierq_exhaustion_reliability"),
    ("q_nj_warning",       55.0,  85.0,  "nj_delivery_reliability"),
]

for param, lo, hi, metric in INJECTION_TESTS:
    out_lo = run_single(flow_df=flow_df, inflow_type="pub_nhmv10_BC_withObsScaled",
                        sensitivity_params={param: lo}, cleanup=True)
    out_hi = run_single(flow_df=flow_df, inflow_type="pub_nhmv10_BC_withObsScaled",
                        sensitivity_params={param: hi}, cleanup=True)
    m_lo = compute_all_party_rrv(out_lo, lb_capacity_mg=LB_CAPACITY_MG)
    m_hi = compute_all_party_rrv(out_hi, lb_capacity_mg=LB_CAPACITY_MG)
    v_lo = m_lo.get(metric, np.nan)
    v_hi = m_hi.get(metric, np.nan)
    different = abs(v_lo - v_hi) > 1e-6
    check(f"{param} changes {metric}",
          different, f"lo={v_lo:.5f} hi={v_hi:.5f} Δ={abs(v_lo-v_hi):.5f}")

# ---------------------------------------------------------------------------
# Step 6 — Asymmetry metric sanity
# ---------------------------------------------------------------------------
print("\n[6] Asymmetry metric sanity ...")
check("asym_reliability_equal >= 0",
      m_base.get("asym_reliability_equal", -1) >= 0,
      f"={m_base.get('asym_reliability_equal', 'MISSING'):.5f}")
check("asym_gini_reliability in [0,1]",
      0 <= m_base.get("asym_gini_reliability", -1) <= 1,
      f"={m_base.get('asym_gini_reliability', 'MISSING'):.5f}")
check("asym_contrib sum ≈ asym_reliability_obligation",
      abs(sum(m_base.get(f"asym_contrib_{p}", 0)
              for p in ["de","nyc","pa","nj","ny"])
          - m_base.get("asym_reliability_obligation", np.nan)) < 1e-6)
check("worst_party is valid",
      m_base.get("worst_party") in {"DE","NYC","PA","NJ","NY"},
      f"={m_base.get('worst_party')}")

# ---------------------------------------------------------------------------
# Step 7 — Quick Sobol task test (1 sample × 2 synthetic realizations)
# ---------------------------------------------------------------------------
print("\n[7] Full sweep task smoke test (sample 0, 2 realizations) ...")
from D4_distributed_risk.experiments.run_sobol_sweep import run_one_sobol_task
params = SAMPLES.iloc[0].to_dict()
result = run_one_sobol_task(
    sample_id=0,
    sample_params=params,
    syn_flows_dir=SYN_FLOWS,
    n_realizations=2,
    outdir=pathlib.Path("/tmp/sweep3_final_smoke"),
    n_workers=2,
)
check("All tasks status=ok", (result["status"] == "ok").all(),
      str(result["status"].value_counts().to_dict()))
check("Regime fracs in output", "regime_frac_normal" in result.columns)
check("Asymmetry in output", "asym_reliability_equal" in result.columns)
check("No NaN in de_reliability", result["de_reliability"].notna().all())
check("regime_frac sum ~1 per row",
      ((result[["regime_frac_normal","regime_frac_nyc_limited",
                "regime_frac_lb_limited","regime_frac_co_limited"]].sum(axis=1) - 1.0).abs() < 1e-4).all())

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print("\n" + "="*60)
n_pass = sum(1 for _, s, _ in results if s == PASS)
n_fail = sum(1 for _, s, _ in results if s == FAIL)
print(f"RESULTS: {n_pass} passed, {n_fail} failed of {len(results)} checks")
if n_fail == 0:
    print("\n🟢 ALL CHECKS PASSED — Sweep 3 is ready for production submission.")
else:
    print("\n🔴 FAILURES DETECTED — fix before submitting sweep 3.")
    for name, status, detail in results:
        if status == FAIL:
            print(f"   FAIL: {name}  [{detail}]")

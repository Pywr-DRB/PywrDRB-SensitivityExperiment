"""
Shared path and style constants for all D4 publication figures.
Import this at the top of every figure script.
"""
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

# ---------------------------------------------------------------------------
# Repository root and canonical data paths
# ---------------------------------------------------------------------------
REPO   = Path(__file__).resolve().parents[4]
D4     = REPO / "D4_distributed_risk"
FIGS   = D4 / "figures" / "publication"

# Sweep 3 is the canonical sweep for publication
SWEEP  = D4 / "results" / "sobol_sweep3"
BASE   = D4 / "results" / "baseline"

PATHS = {
    # Baseline 1000-member RRV summary (reaggregated with regime + asymmetry metrics)
    "rrv_summary":          BASE / "rrv_summary.parquet",
    # Sobol sweep 3 outputs
    "sobol_mean_metrics":   SWEEP / "sobol_mean_metrics.parquet",
    "sobol_indices":        SWEEP / "sobol_indices.parquet",
    "sobol_S2":             SWEEP / "sobol_S2.parquet",
    "sobol_samples":        SWEEP / "sobol_samples.csv",
    "sobol_design":         SWEEP / "sobol_design.json",
    "generation_log":       SWEEP / "synthetic_flows" / "generation_log.csv",
    "task_outputs":         SWEEP / "task_outputs",
    # Validation
    "pub_metrics":          D4 / "figures" / "pub_validation_metrics.json",
    "stage2_summary":       BASE / "stage2_days_summary.csv",
}

# ---------------------------------------------------------------------------
# Party definitions
# ---------------------------------------------------------------------------
PARTIES = ["DE", "NYC", "PA", "NJ", "NY"]

PARTY_LABELS = {
    "DE":  "Delaware\n(Trenton)",
    "NYC": "New York City\n(IERQ/ERQ)",
    "PA":  "Pennsylvania\n(LB Storage)",
    "NJ":  "New Jersey\n(Diversions)",
    "NY":  "New York State\n(Montague)",
}

PARTY_COLORS = {
    "DE":  "#2166ac",
    "NYC": "#f4a582",
    "PA":  "#4dac26",
    "NJ":  "#d01c8b",
    "NY":  "#7b3294",
}

# Obligation weights (WEIGHTS_OBLIGATION from metrics.py)
OBLIGATION_WEIGHTS = {
    "DE": 0.28, "NYC": 0.25, "PA": 0.20, "NJ": 0.15, "NY": 0.12,
}

# Primary metric per party
PARTY_RELIABILITY = {
    "DE":  "de_reliability",
    "NYC": "nyc_ierq_exhaustion_reliability",
    "PA":  "pa_depletion_reliability",
    "NJ":  "nj_delivery_reliability",
    "NY":  "ny_reliability",
}
PARTY_RESILIENCY = {
    "DE":  "de_resiliency",
    "NYC": "nyc_ierq_exhaustion_reliability",
    "PA":  "pa_depletion_resiliency",
    "NJ":  "nj_delivery_reliability",
    "NY":  "ny_resiliency",
}
PARTY_VULNERABILITY = {
    "DE":  "de_vulnerability",
    "NYC": "nyc_min_ierq_balance_mg",
    "PA":  "pa_min_storage_frac",
    "NJ":  "nj_lb_restriction_days",
    "NY":  "ny_vulnerability",
}

# Sobol parameter labels
PARAM_LABELS = {
    "alpha_betz_warning": r"$\alpha_{BW}$\nBeltzville Warning",
    "alpha_bm_warning":   r"$\alpha_{BMW}$\nBlue Marsh Warning",
    "m_lb":               r"$m_{LB}$\nLB MRF Multiplier",
    "ierq_max_bg":        r"$I_{max}$\nIERQ Ceiling",
    "erq_cap_mg":         r"$C_{ERQ}$\nERQ Cap",
    "q_nj_warning":       r"$Q_{NJ,W}$\nNJ Warning Cap",
    "tau_recovery":       r"$\tau_R$\nRecovery Days",
}

REGIME_COLORS = {
    "normal":      "#d0e8d0",
    "NYC-limited": "#f4a582",
    "LB-limited":  "#92c5de",
    "co-limited":  "#ca0020",
}

# ---------------------------------------------------------------------------
# Shared matplotlib style
# ---------------------------------------------------------------------------
def set_style():
    mpl.rcParams.update({
        "font.family":       "sans-serif",
        "font.size":         10,
        "axes.titlesize":    11,
        "axes.labelsize":    10,
        "xtick.labelsize":   8,
        "ytick.labelsize":   8,
        "legend.fontsize":   8,
        "figure.dpi":        150,
        "savefig.dpi":       300,
        "savefig.bbox":      "tight",
        "axes.spines.top":   False,
        "axes.spines.right": False,
        "axes.grid":         True,
        "grid.alpha":        0.25,
        "grid.linewidth":    0.5,
    })

# Dissertation Implementation Plan
**Marilyn Smith | Cornell EWRS | Reed Research Group**  
**Updated:** 2026-05-26  

---

## Gates
| Gate | Date | Requirement |
|------|------|-------------|
| GATE 1 | **May 30** | Committee written direction sign-off |
| GATE 2 | **June 27** | Core figure set → Pat confirms viability |
| GATE 3 | **August 1** | Extension petition filed (HARD deadline) |
| GATE 4 | **December 1** | A-exam (contingent on extension) |

**Scott's recommendation (email 2026-05-26):** D4 as Paper 1 → D1 follows naturally. D4 is most model-ready; stochastic ensemble may strengthen D4 (decide at Gate 1).

---

## Compute + Package Inventory

### Dissertation venv (`dissertation/venv/`, Python 3.11.5)
| Package | Version | Role |
|---------|---------|------|
| `pywrdrb` | 2.1.0b0 | DRB water management model (editable install) |
| `pywr` | 1.27.4 | Pywr simulation engine |
| `scipy` | 1.15.3 | LHS (`scipy.stats.qmc`), statistics, optimization |
| `scikit-learn` | 1.8.0 | Dimensionality reduction, clustering (PCA, k-means), regression |
| `statsmodels` | 0.14.6 | Time series, regression diagnostics |
| `numpy` | 2.4.6 | Array operations |
| `pandas` | 3.0.3 | Tabular I/O and time series |
| `matplotlib` | 3.10.9 | Plotting |
| `h5py` | 3.16.0 | HDF5 I/O for large ensemble output |
| `mpi4py` | 4.1.2 | MPI parallelism across SLURM tasks |
| `joblib` | 1.5.3 | Shared-memory parallelism within node |
| `torch` | 2.12.0 | Neural networks (D3 inference option) |
| `hydroeval` | 0.1.0 | NSE, KGE metrics for streamflow validation |

### To install (one-time `pip install` into dissertation venv)
| Package | Version | Purpose | Status |
|---------|---------|---------|--------|
| `SALib` | 1.5.2 | Sobol sensitivity + Morris screening — **INSTALLED** | ✓ |
| `Rhodium` | 1.3.0 | Installed; **not used for D4 RQ3** (tradeoff analysis replaces PRIM) | optional |
| `synhydro` | latest | Kirsch-Nowak generator (already in SEE venv) | install when needed |
| `seaborn` | latest | Statistical figure styling | install when needed |

### SEE stochastic experiment venv (`D1_decision_scaling/stochastic_experiment/`)
Contains: `synhydro`, `mpi4py`, `pywrdrb`. Use directly for generator development or `pip install synhydro` into dissertation venv.

### Cluster resources
- SLURM on `cbsuecco` cluster, up to ~100 cores
- SLURM template in `D1_decision_scaling/stochastic_experiment/`

---

## Available Data Inventory

### Streamflow
| Dataset | Path | Dates | Notes |
|---------|------|-------|-------|
| `nhmv10` | `pywrdrb/data/flows/_hydro_model_flow_output/streamflow_nhmv10_mgd.csv` | 1980-10-01 to 2016-09-30 | NHM hydrologic model; used for baseline runs |
| `pub_nhmv10_BC_withObsScaled` | `pywrdrb/data/flows/pub_nhmv10_BC_withObsScaled/` | 1945–2023 | Extended record; best for long-period ensemble |
| `nwmv21` | `pywrdrb/data/flows/_hydro_model_flow_output/streamflow_nwmv21_mgd.csv` | — | NWM v2.1 alternative |
| USGS daily observed | `pywrdrb/data/observations/_raw/streamflow_daily_usgs_mgd.csv` | — | For validation |
| CMIP6 (72 GCMs) | `~/Research/CMIP6_multimodel_streamflow/pywrdrb/inputs/` | 2020-2099 | SSP2-4.5, SSP3-7.0, others; diversions + gage flows + inflows |

### Reservoir / storage
| Dataset | Source | Notes |
|---------|--------|-------|
| USGS water levels (4 reservoirs) | `~/Research/rs_policy_observability/data/raw/` | Blue Marsh, Beltzville, F.E. Walter, Prompton |
| Storage ensembles | `~/Research/rs_policy_observability/data/processed/storage_ensemble_<reservoir>.csv` | USACE + curve libraries |

### Synthetic ensemble
| Dataset | Source | Status |
|---------|--------|--------|
| Amestoy 1000-member reconstruction | Zenodo (TBD — download required) | NOT YET DOWNLOADED |
| Kirsch-Nowak synthetic traces | Generate from `pub_nhmv10_BC_withObsScaled` | Use `synhydro.KirschGenerator` |

---

## Direction 4 — Drought Risk Distribution Across Multi-Party Allocation Systems
**STATUS: PAPER 1 — Execute now. Committee most positive. No external dependencies.**

### Generalized Framing (for publication)
> Institutional allocation rules in shared river basins were designed under stationarity assumptions, yet they implicitly distribute hydrologic drought risk heterogeneously across parties with different storage assets, geographic positions, and operational mandates. This paper quantifies that distribution, identifies the regime conditions under which each subsystem becomes the binding constraint on collective water delivery, and shows how the relative depth of risk shifts under hydrologic variability.

**The DRB is the study system, not the subject.** The subject is: *how do fixed multi-party rules distribute stochastic risk, and which institutional parameters most amplify asymmetry?*

**Distinguishes from prior work:** Hashimoto 1982 introduced RRV but applied it to single systems. Brown 2012, Herman et al. 2015 extended to multi-objective tradeoffs. This paper extends to multi-party systems where each party has its own performance metric, and risk distribution across parties emerges from institutional rules rather than design choices.

---

### Research Questions

**RQ1:** How are hydrologic drought risks distributed across parties in a multi-party shared river compact, and is risk distribution proportional to each party's institutional obligations?

**RQ2:** Which institutional operating-rule parameters most influence each party's risk (Sobol S1/ST), and do sensitivity rankings differ across parties?

**RQ3:** When institutional parameters are varied within DRBC-feasible ranges, when do changes **jointly improve** all parties versus **redistribute** risk across parties — and how does that structure depend on **failure regime** and **parameter interactions** (Sobol S2)? *Methods: tradeoff classification (A), regime-stratified response (B), S2 interaction summary (C) — not PRIM.*

---

### Experimental Plan

#### Step 0 — Party-to-Subsystem Mapping *(no code, do this week)*
**File:** `D4_distributed_risk/party_mapping/decree_party_node_mapping.md` *(draft exists — fill TODO items)*

Read 1954 Decree Articles III–IV + Water Code §2.5.3. Confirm exact flow targets per party. Finalize Pywr-DRB node-to-party mapping.

**CONFIRMED: Full five-party framing for Paper 1.**
| Party | Primary interest | Pywr-DRB node | Metric |
|-------|----------------|---------------|--------|
| DE | Trenton flow reliability | `delTrenton` recorder | Reliability / Vulnerability / Resilience of daily flow ≥ TFO |
| NYC | Diversion availability + IERQ access | `banks.py → IERQRelease_step1`, `drought_level_agg_nyc` | IERQ exhaustion day-of-year; diversion reliability |
| PA | LB reservoir conservation pool | `reservoir_blueMarsh`, `reservoir_beltzvilleCombined` | Storage depletion rate; days below warning threshold |
| NJ | Diversion restriction protection | NYC diversion parameter + FFMP triggers | Diversion restriction days (days NYC diversions curtailed) |
| NY | Montague flow reliability | `delMontague` recorder | Reliability of daily flow ≥ Montague target |

**River Master reports TODO:** Extract drought stage dates and IERQ usage tables from PDFs — provides observed validation baseline for regime attribution.

---

#### Step 1 — Two-Tier Ensemble Strategy *(confirmed)*

**CONFIRMED: Amestoy = baseline risk distribution; Kirsch-Nowak = sensitivity traces. Both needed, different roles.**

**Tier 1 — Amestoy 1000-member reconstruction (baseline RQ1/RQ2)**
- Purpose: Establish per-party RRV distributions and regime attribution under historical climate variability. Pre-built, peer-reviewed, spatially correlated, preserves observed drought clustering. Directly feeds D4 RQ1 and RQ2.
- Action: Download from Zenodo immediately. Verify column names match `pywrdrb_nodes_to_generate` in SEE config.
- Format expected: one CSV or HDF5 per member, DatetimeIndex, columns = pywrdrb gage node IDs
- If Amestoy under-samples severe multi-year droughts (≥3 years), supplement with Herman Qsynth generator targeted to severity — see flowchart note.

**Tier 2 — Kirsch-Nowak synthetic traces (sensitivity RQ3)**
- Purpose: Perturbed traces for institutional sensitivity analysis. Allows targeted exploration of tails (e.g., extended droughts that stress the LB system) and parameter space coverage independent of historical record.
- Fit generator from `pub_nhmv10_BC_withObsScaled` (1945–2023 baseline — longer record than nhmv10).
- Generates independent traces that are not constrained to historical sequence.
```python
# install: pip install git+https://github.com/TrevorJA/SynHydro.git
from synhydro.methods.generation.nonparametric.kirsch import KirschGenerator
from synhydro.methods.disaggregation.temporal.nowak import NowakDisaggregator
gen = KirschGenerator(annual_flows_df)   # multisite lag-1 VAR on annual flows
traces = gen.generate(n_realizations=500, n_years=30)
daily = NowakDisaggregator(hist_annual, hist_daily).disaggregate(traces)
```
- Reference: Kirsch et al. (2013) WRR; Nowak et al. (2010) WRR

**Tier 0 — pub_nhmv10_BC_withObsScaled directly (pipeline development only)**
- 79-year single trace spanning 1960s, 1999, 2002 droughts. Use during code development before Amestoy download is complete. NOT for published results.

---

#### Step 2 — Extend Baseline Metrics *(~2 days coding)*
**File to create:** `D4_distributed_risk/rrv_metrics/baseline_metrics.py`

Build on `pywrdrb/post/metrics.py` (`calculate_reliability()`, `calculate_vulnerability()`). Add:

```python
# PA metric — LB storage depletion days
def lb_storage_depletion_fraction(storage_df, bm_usable=7450, betz_usable=13500,
                                  warning_frac_bm=0.689, warning_frac_betz=0.737):
    """
    Fraction of days LB storage (blueMarsh + beltzville) is below warning thresholds.
    Returns per-reservoir fractions and combined flag (Water Code §2.5.5).
    
    Packages: numpy, pandas
    """
    bm_frac = storage_df['reservoir_blueMarsh'] / bm_usable
    betz_frac = storage_df['reservoir_beltzvilleCombined'] / betz_usable
    below_warning = (bm_frac < warning_frac_bm) | (betz_frac < warning_frac_betz)
    return {
        'bm_depletion_frac': (bm_frac < warning_frac_bm).mean(),
        'betz_depletion_frac': (betz_frac < warning_frac_betz).mean(),
        'lb_warning_days_frac': below_warning.mean(),
    }

# NYC metric — IERQ exhaustion  
def ierq_exhaustion_day(ierq_remaining_series):
    """
    Day-of-water-year when IERQ bank first reaches zero.
    Returns NaN if bank never exhausted in that year.
    
    Packages: pandas, numpy
    """
    # Group by water year, find first zero-crossing
    ...

# NJ/NY metric — Montague/Trenton reliability already in pywrdrb post/metrics.py
# Extend with: days-below-threshold decomposition by water year (drought year vs. normal)
def reliability_by_year(flow_df, node, target_mgd):
    """Per-water-year Trenton/Montague reliability. Packages: pandas."""
    ...
```

**CONFIRMED: Report all three RRV metrics for every party.** The model already has the infrastructure; no reason to report less.
- `Reliability` — fraction of days performance ≥ target. Primary comparison to DRBC 95% standard.
- `Vulnerability` — mean magnitude of deficit given failure. Captures severity, not just frequency.
- `Resilience` — probability of recovering in the next timestep. Captures duration/persistence.

All three are computed per party, per ensemble member, per water year. Storage in HDF5 (per-run timeseries → compute metrics in post). See `pywrdrb/post/metrics.py` for existing `calculate_reliability()` and `calculate_vulnerability()` — add `calculate_resilience()` alongside.

Note: PA and NJ do not have a "flow target" — their metrics are storage-based and restriction-count-based respectively. Storage-pool fraction replaces the flow threshold for the RRV calculation for those parties.

---

#### Step 3 — Regime Attribution *(core D4 analysis)*
**File:** `D4_distributed_risk/rrv_metrics/regime_attribution.py`

For each ensemble member × water year, classify:
```python
def classify_regime(ierq_remaining_ts, lb_storage_ts, 
                    trenton_failure_ts,
                    bm_usable=7450, betz_usable=13500):
    """
    For each drought event (Trenton failure period):
    - NYC-Limited: IERQ bank exhausted BEFORE LB storage below warning (by lag_days)
    - LB-Limited: LB storage below drought threshold BEFORE or WITHOUT IERQ exhaustion
    - Co-Limited: both bind within lag_days window
    - External: failure with no constraint binding (pure hydrology)
    
    Returns: DataFrame with columns [start_date, end_date, regime, severity_mgd]
    Packages: numpy, pandas
    """
    lag_days = 14  # ⚡ DECISION: appropriate lag for LB-to-Trenton routing
    ...
```

⚡ **DECISION: Attribution lag window (0, 7, 14, 30 days)?**
- Physical basis: Blue Marsh is ~3 days from Trenton; Beltzville ~5 days.
- Recommendation: Use 14-day window as default (covers routing + decision lag); test sensitivity.

The `drought_level_agg_lb` parameter (now implemented) feeds directly into this — LB drought stage 2 (both reservoirs below drought thresholds for 3 consecutive days) is the operational signal for LB-Limited regime.

---

#### Step 4 — Baseline Ensemble Run
**File:** `D4_distributed_risk/experiments/run_d4_baseline.py` *(scaffold exists)*

```python
# Run pywrdrb across ensemble members
import pywrdrb
from joblib import Parallel, delayed  # for shared-memory parallelism within node
# OR: mpi4py for SLURM multi-node
# Collect: Trenton flow, Montague flow, LB storage, IERQ remaining, diversion records

# Per-run output: dict → HDF5 via h5py
# Key: use pywrdrb OutputRecorder which auto-records named parameters
```

**Compute plan:**
- Single-run wall time for pywrdrb (30-year): ~2–5 min (estimate from SEE runs)
- 1000 members × 5 min = ~83 CPU-hours → 83 cores for 1 hour on SLURM
- Feasible. Use SEE's `00_run_baseline_simulations.py` as template for SLURM submission.

**Output format:**
```
D4_distributed_risk/rrv_metrics/results/
├── ensemble_trenton_reliability.csv     # shape (1000,) — per-member annual reliability
├── ensemble_regime_attribution.csv      # shape (1000, n_years) — regime per year
├── ensemble_lb_storage.h5               # full storage timeseries (large)
└── ensemble_ierq_remaining.h5           # full IERQ timeseries
```

---

#### Step 5 — Institutional sensitivity (RQ2) + tradeoff analysis (RQ3)

**CONFIRMED: Sobol variance decomposition (RQ2). RQ3 uses post-processing on the same ensemble — not PRIM** (committee: PRIM not peer-review eligible as primary method).

**Step 5a — Sobol variance decomposition (RQ2)**

Implemented in `D4_distributed_risk/lib/sensitivity/sobol_design.py`, `run_sobol_sweep.py`, `sobol_analysis.py`.  
N = 1,024, k = 6–7 parameters → 14,336–16,384 Saltelli samples × 50 Kirsch-Nowak realizations.

Outputs: `sobol_indices.parquet` (S1, ST), `sobol_S2.parquet` (pairwise interactions), `sobol_mean_metrics.parquet`.

**Step 5b — RQ3 institutional tradeoff analysis (Options A, B, C)**

**File:** `D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py`

| Option | Question | Method | Output |
|--------|----------|--------|--------|
| **A** | Win-win vs redistribution vs lose-lose | Per Saltelli sample: Δreliability vs baseline reference task; classify each of 50 realizations; bootstrap CIs; 5×5 correlation of party deltas | `tradeoff_sample_summary.csv`, `tradeoff_delta_corr_5x5.csv` |
| **B** | Regime-dependent policy leverage | Binned mean metrics vs m_LB, I_max, erq_cap_mg, faceted by `overall_regime` (or documented proxy) | `regime_stratified_response.csv` |
| **C** | Asymmetric cross-party interactions | Top Sobol S2 pairs per party metric; ST_DE / ST_NJ asymmetry table | `sobol_s2_top_interactions.csv`, `sobol_party_asymmetry_ST.csv` |

```bash
python D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py \
    --task-dir  D4_distributed_risk/results/sobol/task_outputs \
    --sobol-dir D4_distributed_risk/results/sobol \
    --baseline  D4_distributed_risk/results/baseline/rrv_summary.csv \
    --outdir    D4_distributed_risk/results/rq3
```

**Prerequisites for defensible RQ3:** full parameter injection in `run_model.py` (m_LB, Q_NJ_W, I_max, erq_cap_mg); baseline `rrv_summary` with `overall_regime`; `sobol_analysis.py` with S2 enabled.

**Compute plan for Step 5:**
- Sobol sweep: ~24 hrs SLURM (already designed)
- RQ3 post-processing: <30 min CPU, no additional Pywr runs

---

#### Step 6 — Figures *(Gate 2 target: June 27)*
**File:** `D4_distributed_risk/figures/` — target 11–13 figures total

**RQ1 — Risk distribution across parties (Figures 1–5)**

1. **Per-party RRV table figure** — 5 parties × 3 metrics (R/R/V). Rows = parties ranked by vulnerability. Columns = metric. Color scale within each column. This is the lead figure; shows the asymmetry immediately. One panel per metric, or combined heat table.

2. **Per-party reliability exceedance curves** — P(annual reliability < x) for all 5 parties on one plot, ensemble distribution shown as shaded bands. Makes the distributional spread visible, not just the central tendency. X-axis: reliability fraction 0–1; Y-axis: exceedance probability.

3. **Vulnerability distribution by party** — violin or box plots of shortfall severity (MGD below target given failure) across 1000-member ensemble, one violin per party. Shows severity asymmetry: DE and NY have flow-based vulnerability; PA/NJ have storage/restriction-based. Different y-axes or normalized.

4. **Risk asymmetry index** — bar chart: each party's normalized vulnerability relative to their fractional share of basin obligation (e.g., NYC = 800 MGD/total demand). Bars above 1.0 = over-burdened relative to obligation; below 1.0 = under-burdened. Core RQ1 answer.

5. **Failure temporal clustering** — calendar heatmap or timeline: which water years (across ensemble) produce simultaneous failures for multiple parties? Color intensity = number of parties failing in that year. Shows whether failures are correlated (systemic) or independent.

**RQ2 — Regime attribution (Figures 6–9)**

6. **Regime attribution decomposition** — stacked bar chart: fraction of drought-failure years classified as NYC-Limited / LB-Limited / Co-Limited / External, across full 1000-member ensemble. Main RQ2 answer. One bar per party (DE, NYC, PA, NJ, NY) showing which regime drives their failures.

7. **Regime phase portrait** — scatter: x = IERQ remaining (fraction of 6.09 BG), y = combined LB storage fraction (of usable pool), color = Trenton shortfall severity (MGD). Points from all ensemble days where Trenton flow < TFO. Lines showing the NYC-Limited / LB-Limited threshold. Shows the operational landscape of failure.

8. **IERQ exhaustion timing distribution** — box plots of IERQ exhaustion day-of-water-year, conditioned on regime (NYC-Limited vs LB-Limited vs no-exhaustion). Shows whether NYC-Limited events cluster early or late in the water year.

9. **Storage co-evolution composite** — composite time series: median + 25th/75th percentile of LB storage and IERQ remaining during NYC-Limited events (N events averaged) vs LB-Limited events (N events averaged). Two panels showing the characteristic trajectory of each regime type leading up to and during Trenton failure.

**RQ2 — Sobol sensitivity (Figures 10–11)**

10. **Sobol indices bar chart** — S1 and ST per parameter, faceted by party metric (RQ2).

11. **Per-party sensitivity tornado** — largest ST per party; asymmetric leverage across DE/NJ/NYC/PA/NY.

**RQ3 — Institutional tradeoff (Figures 12–13)**

12. **Tradeoff occupancy + Δreliability correlation** — stacked bars of win-win / redistribution / lose-lose fractions (Option A); 5×5 heatmap of party Δreliability correlations across samples; optional DE vs NJ scatter colored by class.

13. **Regime-stratified response + S2 interactions** — binned DE reliability vs m_LB (and erq_cap_mg) in three regime panels (Option B); heatmap or table of top S2 pairs for opposing party metrics (Option C).

---

### Literature Connections

| Paper | Connection to D4 |
|-------|----------------|
| Hashimoto et al. (1982) *WRR* | RRV framework — the foundational metric. D4 *applies* this to multi-party systems for the first time. Cite as methodological basis. |
| Brown et al. (2012) *NCC* | Decision scaling for robustness — similar philosophical framing (performance under deep uncertainty), but Brown focused on physical climate, D4 focuses on institutional parameters |
| Herman et al. (2015) *WRR* | Many-objective robustness — establishes that "robustness" depends on whose risk you measure. D4 extends this to compact parties under fixed rules (no optimization) |
| Borgomeo et al. (2016) *WRR* | Stochastic drought risk in water resource systems — closest methodological precedent for ensemble-based risk quantification |
| Giuliani & Castelletti (2016) *HESS* | Cooperative vs noncooperative regime in shared basins — D4's "NYC-Limited vs LB-Limited" regime decomposition parallels their cooperative / non-cooperative framing |
| Zeff et al. (2016) *JWRPM* | Multi-utility planning under climate variability — establishes that planning separately vs jointly changes risk distribution |
| Turner et al. (2020) *EF* | Decision scaling for multi-sector systems — relevant to D4 sensitivity analysis framing |
| Steinschneider & Brown (2013) *WRR* | Nonstationary SWG for climate risk — generator foundation; Kirsch-Nowak is the DRB implementation |
| Kirsch et al. (2013) *WRR* | Multisite lag-1 VAR generator — Tier 2 ensemble method |
| Nowak et al. (2010) *WRR* | Annual-to-daily disaggregation — paired with Kirsch for daily traces |
| Amestoy et al. (2026) *Zenodo* | 1000-member DRB reconstruction — Tier 1 baseline ensemble |
| Gold et al. (2019) *EF* | Cooperative stability / joint feasibility — conceptual framing for RQ3 tradeoff classes (win-win vs redistribution), not PRIM boxes |
| Saltelli et al. (2010) *ESWA* | Variance-based sensitivity analysis (Sobol) — methodological reference for sensitivity step |
| Razavi & Gupta (2015) *WRR* | Sensitivity analysis review — positions Sobol indices within sensitivity methods landscape |
| NJ v. NY (1954) Supreme Court Decree | Primary institutional source — Article III (flow targets), Article VII (NYC diversion rights) |
| DRBC Water Code §2.5 | Operational rules for FFMP, LB contributions, IERQ. Primary regulatory source. |
| DRBC River Master Annual Reports | Observed IERQ usage + drought stage dates — validation baseline for regime attribution |

---

## Direction 1 — Failure Surface Mapping Under Compounding Stressors
**STATUS: PAPER 2 — Execute after D4 Gate 2. Scott confirmed this follows naturally.**

### Generalized Framing (for publication)
> Water management systems face compounding stressors: climate-driven changes to both flow availability and downstream demand targets simultaneously shift the failure surface. This paper maps the boundary between acceptable and unacceptable performance across a multi-dimensional scenario space and attributes failures to upstream diversion-based versus downstream storage-based subsystems, providing a diagnostic that cannot be obtained from single-stressor analysis.

**Distinguishes from prior work:** Herman et al. (2015) and others map robustness across climate scenarios. This paper explicitly attributes failure to institutional subsystems (who is responsible?) rather than just characterizing when failure occurs. The SLR-driven TFO increase creates a coupled stressor that existing decision scaling literature has not treated.

---

### Research Questions

**RQ1:** Across the joint space of streamflow variability and sea-level-driven flow target increases, where is the boundary of acceptable system performance, and how does it shift across target levels?

**RQ2:** Within the failure region, what fraction of failures are attributable to upstream diversion-side exhaustion versus downstream storage-side depletion?

**RQ3:** How does the probability mass of realizations within the failure region change under CMIP6 projected streamflow, and does attribution shift systematically with warming level?

---

### Experimental Plan

#### Step 0 — Generator Decision *(blocked on Scott)*

⚡ **DECISION: Kirsch-Nowak (streamflow space) vs PRMS/climate (weather/hydrology space)?**
- **Streamflow space (recommended by Scott):** Kirsch-Nowak generates synthetic DRB flows directly. Fast, well-validated for DRB (SEE project). CMIP6 enters only for probability weighting of the failure surface cells (Step 3), not as generator input.
  - Generator code: `synhydro.KirschGenerator` (SEE venv; install into dissertation venv)
  - Reference: Kirsch et al. (2013) WRR + Nowak et al. (2010) WRR
- **Weather/hydrology space:** Weather generator → NHM/PRMS → DRB flows. Physically consistent but adds 2–4 weeks of pipeline work and NHM uncertainty.

⚡ **DECISION: Realization selection (Steinschneider 2015)?**
- Full sweep: 50 mean-shift × 5 variance levels × 4 SLR levels = 1,000 cells × N realizations/cell
- With realization selection (Steinschneider & Brown 2013): select ~10–20 representative realizations per cell from a larger ensemble, reducing compute by ~10×
- Ask Scott: "Is realization selection from Steinschneider 2015 applicable here, or does the attribution analysis require full trace coverage?"

⚡ **DECISION: Streamflow metric for CMIP6 probability weighting (Step 3)?**
- Option A: NYC aggregate inflow (Cannonsville + Pepacton + Neversink combined)
- Option B: Montague flow (integrates whole upper basin)
- Option C: Both (2D kernel density for weighting)
- Ask Scott at Gate 1 meeting.

---

#### Step 1 — Scenario Space Definition

**Three axes:**
```
Axis 1: Streamflow signal (Kirsch-Nowak)
  - Mean annual flow shift: -50%, -30%, -10%, 0%, +10%, +30%, +50% of historical mean
    (7 levels; map to climate "wet"/"dry" narratives)
  - Flow variance scaling: 0.5×, 1.0×, 1.5×, 2.0×, 2.5× (5 levels)
  - → 35 streamflow cells × N realizations per cell (N=50 suggested)

Axis 2: TFO level (SLR-driven)
  - Baseline TFO: current DRBC standard
  - TFO+3%: corresponds to ~0.3m SLR (DRBC 2025-6)
  - TFO+6%: ~0.5m SLR
  - TFO+10%: ~0.8m SLR
  - → 4 levels

Axis 3: LB initial storage (drought entry condition)
  - 100%, 75%, 50%, 25%, 10% of max usable (5 levels)
  - → Determines how quickly LB-Limited regime is triggered
```

Total cells: 35 × 4 × 5 = 700 cells × 50 realizations = 35,000 runs.  
With realization selection: 700 × 10 = 7,000 runs. Feasible on cluster (~580 CPU-hours at 5 min/run).

**File:** `D1_decision_scaling/experiments/scenario_space.py`
```python
import numpy as np
import pandas as pd

mean_shifts = np.array([-0.50, -0.30, -0.10, 0.0, 0.10, 0.30, 0.50])
var_scales  = np.array([0.5, 1.0, 1.5, 2.0, 2.5])
tfo_levels  = np.array([1.00, 1.03, 1.06, 1.10])  # multiplier on baseline TFO
lb_inits    = np.array([1.00, 0.75, 0.50, 0.25, 0.10])

# Build full factorial grid
import itertools
cells = list(itertools.product(mean_shifts, var_scales, tfo_levels, lb_inits))
scenario_df = pd.DataFrame(cells, columns=['mean_shift','var_scale','tfo_mult','lb_init_frac'])
# 700 rows
```

---

#### Step 2 — Streamflow Generator

**File:** `D1_decision_scaling/generator/generate_synthetic_flows.py`

```python
# Install: pip install git+https://github.com/TrevorJA/SynHydro.git
from synhydro.methods.generation.nonparametric.kirsch import KirschGenerator
from synhydro.methods.disaggregation.temporal.nowak import NowakDisaggregator
from methods.load import load_baseline_historical_flow  # from SEE stochastic_experiment

# Step 1: Load historical annual flows (pub_nhmv10_BC_withObsScaled, 1945-2023)
hist_annual = load_baseline_historical_flow('pub_nhmv10_BC_withObsScaled')

# Step 2: Fit generator on unperturbed historical
generator = KirschGenerator()
generator.fit(hist_annual)

# Step 3: Generate perturbed ensemble — mean shift applied to annual totals
def generate_perturbed_ensemble(mean_shift, var_scale, n_realizations=50, n_years=30):
    """
    Generate synthetic annual flows with prescribed mean and variance perturbation.
    Returns: pd.DataFrame of shape (n_years*n_realizations, n_nodes)
    """
    perturbed_annual = generator.generate(n_realizations, n_years)
    # Apply perturbation: scale mean and variance
    perturbed_annual = perturbed_annual * (1 + mean_shift)  # mean shift
    # var_scale: adjust deviations from mean
    mean_val = perturbed_annual.mean(axis=0)
    perturbed_annual = mean_val + (perturbed_annual - mean_val) * var_scale
    return perturbed_annual

# Step 4: Disaggregate annual → daily via Nowak
disagg = NowakDisaggregator(hist_annual, historical_daily_flows)
daily_synthetic = disagg.disaggregate(perturbed_annual)
```

**Validation:** Check that generator reproduces historical statistics (mean, variance, lag-1 autocorrelation, cross-correlation across nodes). Use `hydroeval` for streamflow metric comparison.

---

#### Step 3 — Failure Surface Sweep

**File:** `D1_decision_scaling/experiments/run_failure_surface_sweep.py`

Performance criteria (per cell — ANY crossing = failure):
```python
TRENTON_RELIABILITY_THRESHOLD = 0.95      # fraction of days
TRENTON_SHORTFALL_SEVERITY_MGD = 100.0   # MGD below TFO
SHORTFALL_CONSECUTIVE_DAYS = 10          # days
LB_CONSERVATION_POOL_FRAC = 0.5          # fraction of usable pool

def is_failure(trenton_flow, tfo_target, lb_storage_bm, lb_storage_betz):
    reliability = (trenton_flow >= tfo_target).mean()
    shortfall = tfo_target - trenton_flow
    max_consecutive = max_consecutive_below(trenton_flow, tfo_target, SHORTFALL_CONSECUTIVE_DAYS)
    lb_combined = lb_storage_bm + lb_storage_betz
    lb_frac = lb_combined / (7450 + 13500)  # blueMarsh + beltzville usable
    return (reliability < TRENTON_RELIABILITY_THRESHOLD or
            max_consecutive >= SHORTFALL_CONSECUTIVE_DAYS or
            lb_frac.min() < LB_CONSERVATION_POOL_FRAC)
```

⚡ **DECISION: Performance criterion thresholds**
- 95% Trenton reliability is the historical DRBC standard — use this as baseline
- Shortfall severity: 100 MGD for 10 days is a judgment call — ask Scott what threshold represents operationally significant failure

**Attribution per failing cell:** reuse `regime_attribution.py` from D4.

---

#### Step 4 — CMIP6 Probability Weighting

**Data:** `~/Research/CMIP6_multimodel_streamflow/pywrdrb/inputs/` (72 folders, all generated)

```python
# Script: D1_decision_scaling/scenario_extraction/extract_cmip6_cell_weights.py
# (already exists — run once SLURM job 245199 completes)

# For each GCM scenario: compute the streamflow metric (mean shift, variance)
# Project onto scenario space grid → assign each GCM to nearest cell
# Cell probability weight = number of GCM realizations in that cell / total

import xarray as xr  # ⚡ INSTALL NEEDED: pip install xarray
# OR: use pandas to load CSV gage_flow_mgd.csv files from each of 72 GCM folders

def compute_gcm_streamflow_stats(gcm_folder):
    """Compute mean shift and variance from GCM streamflow vs historical baseline."""
    gcm_flows = pd.read_csv(gcm_folder / 'gage_flow_mgd.csv', index_col=0, parse_dates=True)
    hist_mean = hist_annual.mean()
    gcm_mean = gcm_flows.resample('YE').sum().mean()  # annual mean
    mean_shift = (gcm_mean - hist_mean) / hist_mean
    # ... variance similarly
    return mean_shift, var_ratio
```

⚡ **DECISION: xarray vs pandas for CMIP6 loading?**
- xarray preferred for NetCDF; but if data is already in CSV format (which it appears to be from `gage_flow_mgd.csv`), pandas is sufficient. Check one folder to confirm format.

---

#### Step 5 — Figures *(11–12 target)*

**Failure surface characterization (Figures 1–4)**

1. **Failure surface heatmap — baseline** — x: mean annual flow shift (7 levels), y: TFO multiplier (4 SLR levels), color: Trenton annual reliability. One panel per LB initial storage level (5 panels or 2×3 grid). The signature figure of the paper.

2. **Failure surface heatmap — regime attribution** — same x/y axes, color: fraction of failing cells that are NYC-Limited (warm) vs LB-Limited (cool). Gray = no failure. Shows the spatial structure of attribution across the scenario space. Novel relative to existing decision scaling literature.

3. **Failure boundary shift** — line plot: for each SLR level, the mean-flow-shift value at which reliability drops below 0.95. X-axis: LB initial storage fraction; Y-axis: critical mean-shift value. Shows how LB pre-positioning moves the failure boundary.

4. **Shortfall severity surface** — same axes as Fig. 1 but color = mean annual shortfall volume (MG) in failing cells. Severity, not frequency.

**CMIP6 probability weighting (Figures 5–7)**

5. **GCM projection scatter on failure surface** — scatter of 72 CMIP6 projections projected onto the (mean shift, variance) axes. Color by SSP. Failure region overlaid. Shows which fraction of the CMIP6 ensemble already sits within the failure region.

6. **Probability-weighted failure surface** — same heatmap as Fig. 1 but cells weighted by CMIP6 probability mass (kernel density estimate). Shows where risk is concentrated given actual climate projections.

7. **Attribution shift under warming** — bar chart: NYC-Limited vs LB-Limited fraction of failures, grouped by SSP (SSP2-4.5, SSP3-7.0). Shows whether warming systematically shifts which subsystem fails first.

**Regime dynamics (Figures 8–10)**

8. **IERQ exhaustion timing by TFO level** — box plots of IERQ exhaustion day-of-water-year, faceted by TFO multiplier. Shows that higher SLR/TFO demands earlier IERQ exhaustion, shifting regime toward NYC-Limited.

9. **LB storage trajectory conditional on regime** — composite plot: median LB storage trajectory in the 30 days before Trenton failure, split by regime. NYC-Limited events: LB still has storage but IERQ gone. LB-Limited events: LB depleted but IERQ may remain.

10. **Cross-direction figure: D1 ↔ D4 link** — scatter: D4 per-party vulnerability (x) vs D1 failure probability at equivalent streamflow condition (y). One point per GCM scenario. Shows that D4 risk distribution and D1 failure surface are consistent and complementary findings.

**Scenario space validation (Figures 11–12)**

11. **Generator validation** — multi-panel: synthetic ensemble statistics vs historical (pub_nhmv10_BC_withObsScaled). Mean, variance, lag-1 autocorrelation, cross-correlation matrix for key nodes. Demonstrates generator fidelity before failure surface results.

12. **Robustness to realization count** — failure surface convergence: failure fraction per cell as function of number of realizations (1, 5, 10, 25, 50). Shows that N=50 per cell is sufficient for stable estimates.

---

### Literature Connections

| Paper | Connection to D1 |
|-------|----------------|
| Brown et al. (2012) *NCC* | Decision scaling framework — D1 extends to multi-party attribution |
| Herman et al. (2015) *WRR* | Multi-objective robustness with scenario discovery — methodology basis for failure surface mapping |
| Steinschneider & Brown (2013) *WRR* | Nonstationary SWG for climate risk — realization selection method |
| Kirsch et al. (2013) *WRR* | Kirsch-Nowak generator — cite as streamflow generator method |
| Nowak et al. (2010) *WRR* | Nowak disaggregation — cite alongside Kirsch |
| Turner et al. (2020) *EF* | Decision scaling for multi-sector systems in DRB — closest existing paper; D1 extends with attribution |
| Kopp et al. (2014) *ASLR* | Regional SLR projections — provides physical basis for TFO-level axis |
| DRBC (2025-6) | TFO increase under SLR — primary regulatory source for Axis 2 |
| Giuliani et al. (2015) | Many-objective design under deep uncertainty — frames the multi-party attribution contribution |

---

## Direction 2 — Flood-Drought Operational Conflict in Dual-Use Reservoirs
**STATUS: PAPER 3. Highest external risk. Execute in parallel, do not prioritize over D4/D1.**

### Generalized Framing (for publication)
> Dual-purpose reservoirs designed for both flood control and water supply storage create a fundamental operational conflict: flood season releases that protect downstream communities deplete the storage available for subsequent drought augmentation. This paper quantifies that conflict using an empirical case study and evaluates the magnitude of tradeoff under alternative pre-storm release protocols.

---

### Research Questions

**RQ1:** What fraction of post-flood storage depletion in dual-use reservoirs is attributable to mandatory flood-season release mandates versus background hydrologic variability?

**RQ2:** Under what pre-storm forecast conditions and storm magnitudes does pre-event drawdown improve the post-flood augmentation capacity enough to justify the reliability risk during the drawdown period?

**RQ3:** Is the flood-drought conflict more severe in reservoir systems governed by fixed seasonal operating bands or adaptive forecast-informed protocols?

---

### Experimental Plan

**HEC-ResSim PR-73 is publicly available for download — no CENAP request needed (confirmed 2026-05-26).**

External data access risk removed. Remaining question is data extraction:
- Download model files → inventory: config only vs. saved run results (DSS output files)
- If results included: directly extract 2004 storage + release time series for Beltzville, Blue Marsh, F.E. Walter, Prompton
- If config only: install HEC-ResSim (free USACE software), run the 2004 simulation, extract output
- HEC-ResSim release functions and pool zone elevations will be in the project files regardless — these validate Pywr-DRB's operational assumptions

⚡ **DECISION: Framing A vs B still pending committee sign-off.** Data access is no longer the gating factor.

#### Decision Tree: Framing A vs B

⚡ **DECISION: Which framing? (pending committee feedback, Gate 1)**

**Framing A — Empirical (requires CENAP)**
1. Validate 2004 event in HEC-ResSim (USACE operational model)
2. Build counterfactual: same storm, different pre-storm storage level
3. Quantify: storage shortfall 90 days post-storm, Trenton contributions Oct–Dec 2004
4. Requires: F.E. Walter + Prompton in Pywr-DRB (Gap 2 — 2–4 weeks additional work)

**Framing B — FIRO reframe (no CENAP needed)**
1. Load HEFS ensemble forecasts for Sept 2004 storm window (NWS HEFS archive, publicly available)
2. Implement pre-storm drawdown rule: if P(5-day peak flow > threshold) > α, draw down to target
3. Sweep: α threshold (0.1 to 0.9) × drawdown target (5% to 30% below full pool)
4. Metric: post-storm storage recovery (days to conservation pool) vs. pre-drawdown shortfall
5. **Immediately executable using Beltzville + Blue Marsh only**

```python
# Framing B implementation
# Packages: pywrdrb, scipy, pandas, numpy, matplotlib
# Data: HEFS forecasts (download from NWS), pywrdrb nhmv10 2004 flows

def pre_storm_drawdown_rule(forecast_ensemble, alpha=0.3, drawdown_target_frac=0.85):
    """
    If P(5-day peak > flood trigger) > alpha, reduce storage to drawdown_target_frac.
    Returns: boolean trigger, target storage level
    """
    peak_5day = forecast_ensemble.rolling(5).max().max(axis=1)
    p_exceed = (peak_5day > FLOOD_TRIGGER_MGD).mean()
    trigger = p_exceed > alpha
    return trigger, drawdown_target_frac if trigger else 1.0
```

---

### Figures *(11–12 target)*

**Empirical 2004 case (Figures 1–4, Framing A)**

1. **Blue Marsh + Beltzville storage trajectory 2004** — daily storage fraction from Jul to Dec 2004. Mark the Sept 2004 storm date, peak fill, drawdown to 12% by Dec 6. Observed vs Pywr-DRB modeled. Shows the physical phenomenon driving D2.

2. **Trenton contributions Oct–Dec 2004** — LB MRF contributions timeseries. With and without LB drought stage switching in Pywr-DRB. Confirms the model now reproduces the observed zero-contribution period.

3. **HEC-ResSim vs Pywr-DRB operational comparison** — if CENAP data arrives: side-by-side release schedules for Blue Marsh and Beltzville, Sept–Dec 2004. Bar chart by week. Shows how USACE operations (HEC-ResSim) vs DRBC model assumptions (Pywr-DRB) diverge.

4. **Counterfactual storage trajectory** — actual 2004 operations vs counterfactual (e.g., no mandatory flood release, store to flood pool capacity). Storage trajectories diverge post-storm. Area between curves = flood-control cost in drought capacity.

**FIRO analysis (Figures 5–8, Framing B)**

5. **Pre-storm drawdown sweep** — 2D heatmap: x = probability threshold α, y = drawdown target (% of conservation pool). Color = post-storm storage recovery time (days to return to conservation pool). Identifies the threshold combinations that most improve post-storm capacity.

6. **HEFS forecast reliability** — reliability diagram for HEFS 5-day peak flow forecasts for the 2004 storm. Shows forecast calibration — underpins the pre-drawdown protocol's decision-making quality.

7. **Tradeoff frontier: pre-storm reliability vs post-storm augmentation** — Pareto scatter: x = days during drawdown period when storage is below conservation pool (reliability cost), y = days saved in post-storm recovery (benefit). Each point = one (α, target) combination. Identifies the operationally feasible frontier.

8. **Regime map for FIRO protocol** — calendar: which storm events in nhmv10 record would trigger the pre-drawdown protocol? How many are followed by significant drought periods? Contextualizes 2004 within the historical frequency of flood-drought sequences.

**Generalization (Figures 9–12)**

9. **Cross-event comparison** — 2004 vs 1955 Hurricane Diane vs 1999 Floyd vs 2011 Irene: post-storm storage trajectories and Trenton contribution capacity. Shows 2004 is the worst-case but not unique.

10. **Flood pool vs conservation pool tradeoff diagram** — schematic: fractional storage allocation by function (dead pool, conservation pool, flood pool, surcharge). Annotate Water Code limits and USACE flood targets. Useful for methods/context section.

11. **Seasonal conditioning** — scatter: storm peak flow vs pre-storm storage level, color = subsequent drought period (days below conservation pool). Shows that late-season storms (Aug–Sept) have highest conflict potential — supports 2004 as representative.

12. **F.E. Walter supplemental** *(if Gap 2 implemented)*: same trajectory analysis as Figs 1–4 for F.E. Walter. Shows whether F.E. Walter amplifies or absorbs the conflict.

---

### Literature Connections

| Paper | Connection to D2 |
|-------|----------------|
| Naz et al. (2018) *ERC* | Flood-drought tradeoff framing in reservoir operations |
| Schweppe et al. (2023) | FIRO protocol evaluation — directly relevant to Framing B |
| Delaney et al. (2020) *WRR* | FIRO economic benefits in California — analogous case; cite for FIRO precedent |
| Koren et al. (2014) | HEFS forecast uncertainty — relevant to pre-drawdown probability threshold |
| USACE ER 1110-2-240 | Operational band guidelines for dual-use reservoirs — primary regulatory source |
| Battaglia & Steinschneider (2021) | Pywr-DRB operational validation — closest prior paper using this model |
| Vogel et al. (1999) *JWRPM* | Storage-yield-reliability analysis — foundational reference for conservation pool capacity framing |

---

## Direction 3 — Satellite Observability and Policy Inference
**STATUS: PAPER 4 or standalone. Most independent. No LB drought dependency.**

### Generalized Framing (for publication)
> Operational rule inference from remotely sensed storage observations introduces structured uncertainty into water management models. This paper characterizes how satellite measurement error propagates through the inference chain — from storage estimation to operating rule identification to downstream water delivery reliability — and quantifies the minimum observation quality required to improve upon standard model assumptions.

---

### Research Questions

**RQ1:** How does satellite storage measurement error (cloud bias, AE curve uncertainty, retrieval noise) propagate through operating rule inference to uncertainty in downstream water delivery reliability?

**RQ2:** Below what observation quality threshold (signal-to-noise ratio, record length) does satellite-inferred rule accuracy degrade below the prior (no satellite data) baseline?

**RQ3:** Is there a systematic difference in inference quality between seasonal rule formats (STARFIT) and functional rule formats (RBF), and which is more robust to realistic satellite noise?

---

### Experimental Plan

⚡ **CRITICAL DECISION (committee, Gate 1): FSM oracle approach endorsed?**
Without oracle sign-off, cannot begin Step 1.

#### Step 0 — Oracle Design
**File:** `D3_satellite_observability/oracle/fsm_oracle.py` *(scaffold exists)*

Recommended: FSM oracle (zero fitted parameters; institutionally grounded from Water Code §2.5.5)
```python
class LowerBasinFSMOracle:
    """5 storage bins × 4 seasons = 20-state lookup. Release = f(bin, season)."""
    BINS = [0.0, 0.20, 0.40, 0.689, 0.80, 1.0]  # fractions of usable storage
    SEASONS = ['DJF', 'MAM', 'JJA', 'SON']
    # Lookup: populated from Water Code §2.5.5 priority staging table
    # + conservation releases Table 4
```

#### Step 1 — Uncertainty Propagation Chain
**File:** `D3_satellite_observability/uncertainty_chain/`

```
satellite_error_model.py     — AR(1) cloud bias (Langhorst 2024); Gaussian AE curve noise
  → storage_ensemble.py      — 500 draws per reservoir
    → rule_inference.py      — STARFIT (parametric) + RBF (nonparametric) per draw
      → pywrdrb_simulate.py  — each inferred rule → pywrdrb run
        → trenton_impact.py  — uncertainty envelope on Trenton shortfall probability
```

**Key implementation detail from Langhorst (2024):** Cloud bias is temporally autocorrelated + correlated with precipitation. Model as AR(1):
```python
# Cloud bias: NOT Gaussian white noise
# sigma_cloud = f(precip_anomaly)  # Langhorst parameterization
# rho_cloud = 0.7  # AR(1) autocorrelation (from Langhorst Fig. 3)
cloud_bias = np.zeros(n_days)
for t in range(1, n_days):
    cloud_bias[t] = rho_cloud * cloud_bias[t-1] + sigma_cloud(precip[t]) * rng.normal()
```

⚡ **DECISION: RBF vs STARFIT vs neural network for rule inference?**
- **STARFIT (parametric):** Sine-curve seasonal patterns. Reference: Turner et al. (2021). Fewer parameters, interpretable. `torch` available if neural net extension needed.
- **RBF (nonparametric):** Radial basis functions. From SYSEN6170 project code. More flexible but requires more data.
- **LSTM/neural net:** Available via `torch` in dissertation venv. Overkill for this paper; better fit for D4 extension.
- SYSEN6170 finding: RBF most robust under degradation. Start with STARFIT + RBF; use SYSEN6170 code directly.

#### Step 2 — Data Sources
- SARAH-CONUS surface area: Texas Data Repository (Yadav et al. 2024 GRL) — download required
- GRDL / 3D-LAKES bathymetric curves — download required
- SWOT data: set up at `~/Research/rs_policy_observability/` — check acquisition status
- DAHITI: `~/Research/rs_policy_observability/` — check acquisition status

---

### Figures *(11–12 target)*

**Uncertainty propagation (Figures 1–5)**

1. **Satellite error model characterization** — three panels: (a) cloud bias time series with AR(1) fit, (b) autocorrelation function vs lag days, (c) cloud bias standard deviation as function of precipitation anomaly. Demonstrates Langhorst (2024) parameterization is reproduced correctly.

2. **Storage ensemble spread** — for each of 3 reservoir archetypes (F.E. Walter, Beltzville/Blue Marsh, Nockamixon): violin plots of daily storage estimate spread across 500 satellite-uncertainty draws, at key drought periods. Shows how observability class determines storage uncertainty.

3. **Inferred rule ensemble** — scatter of 500 STARFIT parameter draws (amplitude vs phase vs baseline) for one reservoir. Each draw = one inferred seasonal operating rule from one storage estimate. Shows how storage uncertainty propagates to rule uncertainty.

4. **Simulated release uncertainty** — ensemble of 500 simulated release time series vs FSM oracle "truth." Shaded band = 5th–95th percentile. Shows when in the season release uncertainty is largest (typically drought transitions).

5. **Trenton uncertainty envelope** — Trenton shortfall probability distribution across 500 propagated draws. Compare: (a) FSM oracle, (b) STARFIT ensemble, (c) RBF ensemble. Shows how inference method choice affects downstream uncertainty width.

**Observability thresholds (Figures 6–9)**

6. **NSE degradation curve** (extended SYSEN6170 figure) — x: noise level (σ/signal ratio), y: NSE of inferred vs true operating rule. Two lines: STARFIT and RBF. Shaded region = noise range expected from SARAH satellite. Crosses the "baseline prior" at a specific threshold — that's the publishable result.

7. **Record length vs inference quality** — x: years of satellite record, y: STARFIT/RBF NSE. Convergence curves. Identifies minimum record length for useful inference.

8. **Observability class comparison** — 3-panel: F.E. Walter (SWOT track), Beltzville/Blue Marsh (SARAH-CONUS), Nockamixon (no data). For each: NSE vs noise level, colored by data source. Shows whether SWOT gives actionable advantage over SARAH.

9. **Value-of-information figure** — bar chart: Trenton shortfall probability under (a) fully-extrapolated assumption (no satellite), (b) satellite-inferred STARFIT, (c) satellite-inferred RBF, (d) FSM oracle. Error bars from ensemble spread. Shows whether satellite observation improves reliability estimates.

**Spatial and policy context (Figures 10–12)**

10. **DRB observability map** — map of DRB showing reservoir locations, data source for each (SWOT ground track coverage, SARAH pixel coverage, in-situ gauge), and model assumption currently in pywrdrb. Provides spatial context for observability classes.

11. **Cloud bias seasonal pattern** — monthly mean cloud bias estimates for DRB latitude band from Langhorst (2024). Shows when in the year satellite storage estimates are most degraded (typically Nov–Mar). Maps directly to drought season timing.

12. **Inference method sensitivity** — heat table: STARFIT vs RBF inference quality (NSE) across record length × noise level. Shows the "observability envelope" — the parameter space where each method is useful.

---

## Decision Log

| Date | Decision | Options | Made by | Status |
|------|----------|---------|---------|--------|
| 2026-05-26 | Primary direction: D4 as Paper 1 | — | Scott (email) | **DECIDED** |
| 2026-05-26 | D4: Five-party framing for Paper 1 | — | MS | **DECIDED** |
| 2026-05-26 | D4: Two-tier ensemble (Amestoy baseline + Kirsch-Nowak traces) | — | MS | **DECIDED** |
| 2026-05-26 | D4: All three RRV metrics per party | — | MS | **DECIDED** |
| 2026-05-26 | D4: Sobol sensitivity (not LHC alone) | — | Pat feedback | **DECIDED** |
| 2026-06 | D4 RQ3: tradeoff (A) + regime-stratified (B) + Sobol S2 (C); **no PRIM** | — | Pat / committee | **DECIDED** |
| Pending | D4: Attribution lag window | 0 / 7 / 14 / 30 days | MS + judgment | Before Step 3 |
| Pending | D4: Gold et al. 2019 framing for RQ3 tradeoff classes (concept, not PRIM) | Cite concept only | Committee | Gate 1 |
| Pending | D1: Streamflow space confirmed (Kirsch vs PRMS) | Kirsch/Gosney | Scott | Gate 1 |
| Pending | D1: Realization selection | Steinschneider 2015 / full sweep | Scott | Gate 1 |
| Pending | D1: Streamflow metric for CMIP6 | NYC aggregate / Montague / both | Scott | Gate 1 |
| Pending | D1: Performance criterion thresholds | 95% reliability / other | Scott | Before sweep |
| Pending | D2: Framing A (empirical/CENAP) vs Framing B (FIRO) | A / B | Full committee | Gate 1 |
| Pending | D3: FSM oracle approach endorsed | FSM / other oracle | Committee | Gate 1 |
| Pending | D3: STARFIT vs RBF primary method | Both / one | MS + SYSEN6170 results | After oracle sign-off |

---

## Week-by-Week Schedule

### Now → May 30 (GATE 1 preparation)
| Task | Direction | Action |
|------|-----------|--------|
| Run `validate_lb_drought_stage.py` — confirm 33/33 tests pass | Shared | Code |
| Run `extract_cmip6_cell_weights.py` once SLURM 245199 completes | D1 | Runs |
| Fill `decree_party_node_mapping.md` TODO items | D4 | Writing |
| Write committee-ready 1-page D4 RQ summary (from RQs above) | D4 | Writing |
| **Send CENAP email** | D2 | Email — do today |
| Prepare Gate 1 questions (decision list above) | All | Prep |

### June 1–7 (post-Gate 1)
| Task | Direction | Action |
|------|-----------|--------|
| Download Amestoy ensemble from Zenodo OR validate Kirsch setup | D4 | Data/Code |
| Implement `baseline_metrics.py` — PA + NJ metrics (Step 2) | D4 | Code |
| Single-member test run through full D4 pipeline | D4 | Runs |
| If D1 confirmed: install synhydro, test Kirsch generator on nhmv10 | D1 | Code |

### June 8–14 (runs on GitHub target)
| Task | Direction | Action |
|------|-----------|--------|
| D4 ensemble run on SLURM (1000 members) | D4 | Runs |
| D4 regime attribution computation | D4 | Analysis |
| D1: generate scenario space + 35-cell test sweep | D1 | Code/Runs |

### June 15–27 (Gate 2 figure set)
| Task | Direction | Action |
|------|-----------|--------|
| D4: 6-figure draft → push to GitHub | D4 | Figures |
| D4 LHC sensitivity (if committee confirmed) | D4 | Runs |
| D1: full failure surface sweep on cluster | D1 | Runs |
| **Gate 2 (June 27): Core D4 figures → Pat review** | D4 | Meeting |

# Dissertation Implementation Plan
**Marilyn Smith | Cornell EWRS | Reed Research Group**  
Last updated: 2026-05-25

---

## Gates
| Gate | Date | Requirement |
|------|------|-------------|
| GATE 1 | **May 30** | Committee written direction sign-off |
| GATE 2 | **June 27** | Core figure set → Pat confirms viability |
| GATE 3 | **August 1** | Extension petition filed (HARD) |
| GATE 4 | **December 1** | A-exam (contingent on extension) |

---

## Workspace Layout
```
dissertation/
├── shared/lower_basin_ffmp_dev/   ← HIGHEST PRIORITY code task (D1/D2/D4 gated on this)
├── D1_decision_scaling/           ← Decision scaling for Trenton TFOs
├── D2_flood_drought/              ← Flood-drought operational conflict
├── D3_satellite_observability/    ← Satellite observability for policy inference
└── D4_cooperative_risk/           ← Cooperative risk attribution, 1954 Decree
```

**Model root:** `~/Research/PywrDRB_master/Pywr-DRB/`  
**Policy diagnostics:** `~/Projects/PywrDRB-PolicyDiagnostics/PywrDRB-PolicyDiagnostics/`  
**Remote sensing:** `~/Research/rs_policy_observability/` + `~/Projects/InfeRes/`

---

## SHARED CRITICAL PATH — `lower_basin_ffmp.py` Drought-Stage Switching

**File:** `~/Research/PywrDRB_master/Pywr-DRB/src/pywrdrb/parameters/lower_basin_ffmp.py`  
**Status:** PARTIAL. MRF contribution logic implemented. Missing:

### What needs to be implemented

**Gap 1 — Lower basin drought stage as independent state variable**  
Currently `get_current_usable_reservoirs()` checks only `drought_level_agg_nyc`. The lower basin has its own drought staging (Water Code §2.5.5) that is independent. When LB drought is in effect:
- Conservation releases switch from `conservation_releases` to `lower_basin_drought_conservation_releases` (dict already defined, never activated)
- Usable reservoirs expand based on LB priority staging, not NYC level

**Implementation steps:**
1. Add `drought_level_agg_lb` parameter load in `LowerBasinMaxMRFContribution.__init__()` and `load()`, mirroring how `drought_level_agg_nyc` is loaded
2. In `get_current_usable_reservoirs()`, add a check: if LB drought is active (`drought_level_lb >= threshold`), use `reservoirs_used_during_drought_conditions` and switch `self.R_min` to `lower_basin_drought_conservation_releases[self.reservoir]`
3. The `drought_level_agg_lb` parameter itself needs to be defined in `ffmp.py` — look at how `drought_level_agg_nyc` is constructed, replicate for LB storage levels
4. Test: run a validation scenario where LB storage is forced low → confirm reservoir activation matches Water Code §2.5.5 priority table

**Gap 2 — F.E. Walter and Prompton not in reservoir lists**  
`reservoirs_used_during_drought_conditions` only has beltzville, blueMarsh, nockamixon. F.E. Walter and Prompton are in the Water Code but require:
- Adding nodes to `drbc_lower_basin_reservoirs` list in `utils/lists.py`
- Adding them to `drbc_max_usable_storages`, `max_discharges`, `max_mrf_daily_contributions`, `lag_days_from_Trenton`, `conservation_releases`
- Adding routing into model_builder
- **Risk:** 2–4 weeks of model integration work — only required for D2. D1 and D4 can proceed without it.

**Recommended sequence:**
1. Implement Gap 1 (LB drought state variable) — ~1–2 days, unblocks D1/D4
2. Validate against Water Code §2.5.5 staging thresholds
3. Defer Gap 2 (F.E. Walter / Prompton) until D2 direction is confirmed

---

## Direction 4 — Cooperative Risk Attribution (START HERE)
**Status: Most model-ready. Pat most positive. No external dependencies.**  
**Recommended first direction to execute in parallel with committee deliberation.**

### What's already working
- `banks.py`: `IERQRelease_step1` — IERQ 6.09 BG/yr tracking ✓
- `post/metrics.py`: `calculate_reliability()`, `calculate_vulnerability()` ✓
- Trenton recorder in model_builder ✓
- Amestoy 1,000-member reconstruction: check Zenodo for download status

### Step-by-step implementation

**Step 0 (no code): Party-to-subsystem mapping document**  
Read: 1954 Decree Articles III–IV + Water Code §2.5.3  
Write: a 1–2 page document mapping each Decree party to a Pywr-DRB node.  
```
DE  → delTrenton recorder (Trenton flow reliability)
NYC → banks.py IERQ + drought_level_agg_nyc (diversion availability)
PA  → beltzvilleCombined + blueMarsh storage levels (conservation pool fraction)
NJ  → diversion restriction days (days NYC diversions curtailed)
NY  → Montague flow target reliability
```
Output: `dissertation/D4_cooperative_risk/party_mapping/decree_party_node_mapping.md`

**Step 1: Extend baseline_metrics.py with PA and NJ metrics**  
File to modify: `~/Projects/PywrDRB-PolicyDiagnostics/PywrDRB-PolicyDiagnostics/src/diagnostics/baseline_metrics.py`

PA metric — LB storage depletion rate:
```python
def calculate_lb_storage_depletion(storage_timeseries, conservation_pool_fraction=0.5):
    """Fraction of days LB storage (blueMarsh + beltzville) falls below conservation pool."""
    combined = storage_timeseries['blueMarsh'] + storage_timeseries['beltzvilleCombined']
    # conservation_pool_fraction of max usable (7450 + 13500 = 20950 MG)
    threshold = conservation_pool_fraction * 20950
    return np.sum(combined < threshold) / len(combined)
```

NJ metric — diversion restriction days:
```python
def calculate_nj_restriction_days(nyc_diversion_timeseries, nj_diversion_limit):
    """Fraction of days NJ diversion is curtailed below limit."""
    return np.sum(nyc_diversion_timeseries < nj_diversion_limit) / len(nyc_diversion_timeseries)
```
Both: ~50 lines each including docstrings and edge case handling.

**Step 2: Run D4 baseline with Amestoy 1,000-member ensemble**  
Script location: `dissertation/D4_cooperative_risk/rrv_metrics/run_d4_baseline.py`  
```python
# Pseudocode outline
import pywrdrb
# Load Amestoy 1000-member reconstruction (from Zenodo)
# Run Pywr-DRB with current DRBC rules across all 1000 members
# Extract per-party metrics: DE (Trenton reliability), NYC (IERQ exhaustion days),
#   PA (LB storage depletion rate), NJ (diversion restriction days), NY (Montague reliability)
# Decompose into NYC-limited vs LB-limited regimes:
#   NYC-limited: IERQ exhaustion precedes LB storage depletion
#   LB-limited: LB storage depletion precedes or without IERQ exhaustion
# Output: per-party RRV table + regime attribution
```
**Requires:** lower_basin_ffmp drought-stage switching (shared task above)

**Step 3: LHC sensitivity (pending committee decision on parameter ranges)**  
200–500 forward simulations across:
- Drought stage threshold ±10–20% (if committee confirms range)
- LB MRF cap ±15–30% (Water Code §2.5.3.B)
- LB activation sequencing lag 0–14 days
Apply PRIM (Scenario Discovery) — `platypus` or `rhodium` library on the cluster

**Step 4: Figure plan for D4**
1. Per-party RRV heatmap across 1000-member ensemble (Trenton reliability by year)
2. Regime attribution: NYC-limited vs LB-limited frequency over ensemble
3. Storage exceedance curves: blueMarsh + beltzville conservation pool fraction
4. LHC sensitivity tornado: which parameter drives per-party risk most
5. Timeline figure: 2002 drought reconstruction — IERQ exhaustion date vs LB depletion date

### D4 Pending committee decisions (block some steps, not Step 0–1)
- [ ] Endorse D4? (both collaborators flagged asymmetric representation concern)
- [ ] Five-party or two-subsystem for Paper 1?
- [ ] Parameter ranges confirmed?
- [ ] Trevor overlap check?

---

## Direction 1 — Decision Scaling for Trenton Flow Objectives

### What's already working
- `studies/paper1_trenton_target_poc/` has existing TFO sweep runs (+5% to +30% TFO above baseline)
- Trenton recorder in model_builder ✓
- IERQ tracking ✓
- Multiple hydrologic inputs already in Pywr-DRB (nhmv10, nwmv21, pub_nhmv10_BC_withObsScaled)

### Step-by-step implementation (pending committee generator decision)

**Before any code: Confirm with Scott**
- [ ] Climate space (weather gen → NHM) vs streamflow space (Kirsch/Gosney directly)
- [ ] Realization selection from Steinschneider (2015) applicable?
- [ ] Kirsch (standard VAR) or Gosney (inverse optimization)?

**Step 1: Streamflow generator (if streamflow space chosen)**  
Path: `dissertation/D1_decision_scaling/generator/`

*Kirsch generator:* Standard multisite VAR. Pat-approved. Well-documented.  
```
Key reference: Kirsch et al. (2013) — multisite lag-1 VAR  
Inputs: historical DRB streamflow at all Pywr-DRB nodes  
Outputs: N synthetic traces × (ΔQ, ΔVar) perturbation grid  
Perturbation axes: mean flow shift (e.g., ±50% in 10% steps) × variance scaling  
Daily resolution required — different from Turner 2014 (monthly)
```
*Gosney generator:* Inverse optimization to guarantee prescribed perturbation appears.  
Check if Gosney code exists in group repos before re-implementing.

**Step 2: Define the scenario space**
```
Axis 1: Streamflow (from generator): ~10 mean-shift levels × 5 variance levels = 50 cells
Axis 2: SLR → TFO level: 4 levels from DRBC 2025-6 table (baseline, 0.3m, 0.5m, 0.8m SLR → corresponding TFO MGD)
Axis 3: LB volume: 3–5 levels (% of conservation pool: 20%, 40%, 60%, 80%, 100%)
Total cells: 50 × 4 × 5 = 1,000 cells (before realization selection)
```
**If realization selection applies:** reduce from ~20,000 traces to ~200–500 representative.

**Step 3: Pywr-DRB failure surface sweep**  
Script: `dissertation/D1_decision_scaling/experiments/run_failure_surface_sweep.py`

Performance criteria per cell (ANY crossing = failure):
- Trenton reliability < threshold (e.g., <95%)
- Shortfall severity > threshold (e.g., >100 MGD for >10 consecutive days)
- LB storage < conservation pool in drought period

Attribution per failing cell:
```python
# NYC-limited: IERQ bank exhausted before LB storage hits conservation pool
# LB-limited: LB storage depleted before or without IERQ exhaustion
# Determine by comparing timestep of first IERQ exhaustion vs first LB depletion
```
**Requires:** lower_basin_ffmp drought-stage switching (shared task)

**Step 4: GCM probability weighting**  
Load Trevor's CMIP6 `gage_flow_mgd.csv` from `~/DRB_reservoir_observations_package/`  
(Confirm this is the 7-GCM SSP2-4.5 dataset — check column headers)  
Project each GCM onto the scenario space → count GCMs in each cell → probability weight

**Step 5: Figure plan for D1**
1. Failure surface heatmap: (mean flow shift × SLR level), color = Trenton reliability
2. Attribution map: same axes, color = fraction of failures that are NYC-limited vs LB-limited
3. GCM overlay: same failure surface with CMIP6 projection clouds
4. IERQ exhaustion timing: box plots of IERQ exhaustion day-of-year across ensemble
5. SLR threshold figure: robustness R vs SLR level (line plot)

### D1 Existing useful work
The `paper1_trenton_target_poc` study already tests +5% to +30% TFO above baseline — this is essentially one slice of the D1 scenario space (Axis 2, one streamflow condition). These figures are directly usable to communicate the existing foundation.

---

## Direction 3 — Satellite Observability for Policy Inference

### What's already working
- `~/Projects/InfeRes/` — satellite storage estimation pipeline
- `~/Research/rs_policy_observability/` — existing SWOT, DAHITI, observed data for DRB reservoirs
- `~/Research/SYSEN6170Project/CEE6400Project/` — Borg MOEA policy optimization framework (the proof-of-concept oracle and inference pipeline)
- Key SYSEN6170 result: RBF most robust under degradation; STARFIT NSE < 0.80 at T=10yr, σ=10%

### Step-by-step implementation

**Step 0 (immediate, no code): Confirm with Stefano**
- [ ] Has Stefano's group applied InfeRes to F.E. Walter, Beltzville, or Nockamixon?
- [ ] Can we share derived satellite-storage time series directly?

**Step 1: Oracle design (blocked until committee confirms FSM)**  
File: `dissertation/D3_satellite_observability/oracle/fsm_oracle.py`

Recommended: FSM oracle (~150 lines Python)
```python
class LowerBasinFSMOracle:
    """
    Finite-state machine oracle for DRB lower basin reservoir operations.
    Storage bins × season → deterministic release lookup.
    Zero fitted parameters. Institutionally grounded.
    """
    # State: (storage_bin, season) → release_fraction
    # e.g., 5 storage bins (0-20%, 20-40%, 40-60%, 60-80%, 80-100%) × 4 seasons
    # = 20-state lookup table
    # Release rule: based on Water Code §2.5.5 priority staging
    
    def __init__(self, storage_bins, seasonal_rules):
        self.lookup = {}  # populated from Water Code table
    
    def get_release(self, storage_fraction, month, conservation_release_mgd):
        season = self._month_to_season(month)
        bin_idx = self._storage_to_bin(storage_fraction)
        return self.lookup[(bin_idx, season)] * conservation_release_mgd
```
The FSM is the "ground truth" against which degraded satellite estimates are tested.

**Step 2: Uncertainty propagation chain**  
File: `dissertation/D3_satellite_observability/uncertainty_chain/`

```
generate_storage_ensemble.py    — 500 draws, adding cloud bias + AE curve error + retrieval noise
  → infer_operating_rules.py   — each draw → STARFIT, RBF inference (from SYSEN6170 code)
    → simulate_releases.py     — each inferred rule → Pywr-DRB 
      → compute_trenton_risk.py— uncertainty envelope on Trenton shortfall probability
```

Langhorst (2024) key insight: cloud bias is **temporally autocorrelated and correlated with precipitation** — NOT Gaussian. Implementation:
```python
# Cloud bias model: AR(1) residual process, correlated with precipitation signal
# sigma_cloud ~ f(precipitation) from Langhorst et al. (2024) parameterization
# This is critical — naive Gaussian noise will underestimate cloud bias impact
```

**Step 3: Reservoir archetypes for controlled experiment**  
Three reservoirs covering observability classes:
1. F.E. Walter — in-situ + SWOT (transition case, policy relevance)
2. Beltzville/Blue Marsh — data-limited (GRanD-derived in current model)
3. Nockamixon — no operational data (fully extrapolated baseline)

**Step 4: DRB translation (scope pending committee)**  
If required for Paper 1: couple inferred rules to Pywr-DRB → evaluate Trenton shortfall change for Nockamixon vs. fully-extrapolated assumption.  
If deferred to Paper 2: D3 Paper 1 ends at the uncertainty envelope on release simulations.

**Step 5: Figure plan for D3**
1. SYSEN6170 extended: RBF vs STARFIT NSE under degradation (record length × noise level heatmap)
2. Cloud bias model: autocorrelation function of satellite storage error vs precipitation
3. Uncertainty propagation funnel: storage uncertainty → rule uncertainty → Trenton risk uncertainty
4. Observability class comparison: three reservoir archetypes side-by-side
5. Value-of-information: Trenton risk estimate with vs without satellite (vs fully extrapolated)

---

## Direction 2 — Flood-Drought Operational Conflict

**Status: Highest external risk. Most committee uncertainty. Execute in parallel but do not prioritize over D4/D1.**

### Immediate actions (this week regardless of direction choice)
1. **Contact USACE CENAP now** — request HEC-ResSim PR-73 operational model files for the September 2004 event. IEPR confirmed by WEST Consultants (2012). Frame as academic collaboration with 2026 F.E. Walter Reevaluation Study context. This must happen immediately regardless of whether D2 is selected.
2. **Run targeted Pywr-DRB validation**: July–December 2004 period  
   - Check `lower_basin_mrf_contributions.csv` shows zero Trenton contributions Oct–Dec 2004 (already documented)
   - Goal: reproduce the mechanism in Pywr-DRB before committing to full experimental design

### Decision tree (pending committee feedback)
```
Committee says physical mechanism is defensible → Framing A (empirical)
  → HEC-ResSim counterfactual analysis (requires CENAP data)
  → Need: F.E. Walter + Prompton in Pywr-DRB (2–4 weeks)
  
Committee says "wet = not drought" critique holds → Framing B (FIRO reframe)
  → HEFS forecasts available publicly — no forecast development
  → Pre-storm drawdown protocol implementation
  → Scope: Beltzville + Blue Marsh only (immediately executable)
  
CENAP does not respond → Parallel effort: begin Framing B while waiting
```

### Step-by-step (Framing B, immediately executable)
File: `dissertation/D2_flood_drought/firo/`
1. Load HEFS forecast data for September 2004 storm window (available from NWS archive)
2. Implement pre-storm storage target: if P(flood event in 5 days) > threshold, draw down to target level
3. Compare actual 2004 release sequence vs FIRO counterfactual
4. Track post-storm storage trajectory → Trenton support capacity

---

## Week-by-Week Schedule (Phase 2, Gates 1→2)

### This week (May 25–30) — GATE 1 preparation
| Task | Direction | Type | Hours |
|------|-----------|------|-------|
| Submit party-to-subsystem mapping doc to committee | D4 | Writing | 4 |
| Contact USACE CENAP for HEC-ResSim files | D2 | Email | 1 |
| Literature framing for committee response | All | Reading | 8 |
| Begin LB drought-stage switching (Gap 1 only) | Shared | Code | 4 |

### Week of June 1–7 (post-GATE 1)
| Task | Direction | Type |
|------|-----------|------|
| Complete lower_basin_ffmp LB drought state variable | Shared | Code |
| Validate LB drought switching against Water Code §2.5.5 | Shared | Test |
| Extend baseline_metrics.py: PA + NJ metrics | D4 | Code |
| Download Amestoy 1000-member ensemble from Zenodo | D4 | Data |
| Begin D4 baseline run with 1000-member ensemble | D4 | Runs |

### Week of June 8–14 (target: runs on GitHub by June 13)
| Task | Direction | Type |
|------|-----------|------|
| D4 baseline simulations complete, push to GitHub | D4 | Runs |
| Begin per-party RRV computation | D4 | Analysis |
| If D1 chosen: implement Kirsch generator | D1 | Code |
| D3: FSM oracle implementation (if oracle confirmed) | D3 | Code |

### Week of June 15–20 (target: results dataset by June 20)
| Task | Direction | Type |
|------|-----------|------|
| D4: regime attribution (NYC-limited vs LB-limited) | D4 | Analysis |
| D4: LHC sensitivity sweep (pending committee ranges) | D4 | Runs |
| D1: failure surface sweep (if streamflow space confirmed) | D1 | Runs |

### Week of June 21–27 (GATE 2: Pat figure review)
| Task | Direction | Type |
|------|-----------|------|
| D4 core figure set: 5 figures to Pat | D4 | Figures |
| D1 failure surface figure set (if primary direction) | D1 | Figures |
| Pat written feedback → viability confirmation | — | Review |

---

## Decision Log

| Date | Decision | Made by |
|------|----------|---------|
| Pending | Primary dissertation direction | Full committee, May 30 |
| Pending | D1: climate vs streamflow space | Scott |
| Pending | D1: Kirsch vs Gosney | Scott/Pat |
| Pending | D1: realization selection applicable | Scott |
| Pending | D2: empirical vs FIRO framing | Full committee |
| Pending | D3: oracle family (FSM confirmed?) | Full committee |
| Pending | D4: five-party vs two-subsystem | Full committee |
| Pending | D4: LHC parameter ranges confirmed | Full committee |

---

## Immediate Next Steps (Today, May 25)

1. **Email USACE CENAP** — HEC-ResSim PR-73 model files for Sept 2004. Cannot wait for direction sign-off. Critical path for D2 and useful for D4 validation.

2. **Write party-to-subsystem mapping** — `dissertation/D4_cooperative_risk/party_mapping/decree_party_node_mapping.md`. Pure reading + writing, no code, shows committee D4 is moving.

3. **Read ffmp.py drought_level_agg_nyc construction** (~lines 400–540) to understand how to replicate for `drought_level_agg_lb`. This is the entry point for the lower_basin_ffmp Gap 1 implementation.

4. **Verify Amestoy CMIP6 data** — check `~/DRB_reservoir_observations_package/gage_flow_mgd.csv` column headers: is this the 7-GCM SSP2-4.5 data Trevor processed, or the observational record? The 1000-member reconstruction should be separately downloaded from Zenodo.

5. **Push paper1_trenton_target_poc figures** to a public GitHub branch — this is existing work that demonstrates forward progress for Gate 1 and is directly usable for D1 or D4 framing.

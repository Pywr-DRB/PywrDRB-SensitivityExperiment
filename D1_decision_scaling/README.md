# D1 — Decision Scaling: Trenton Flow Objectives Under SLR and Climate Change

## Research Questions

**Core:**  
What (streamflow, SLR, LB contribution) combinations push the joint NYC–LB system past its capacity to maintain Trenton flow objectives — and is the binding constraint NYC IERQ exhaustion or LB storage depletion?

**RQ1:** At what (streamflow, SLR) combinations does the system produce unacceptable Trenton shortfall frequency — and how does NYC IERQ exhaustion interact with LB storage depletion to produce failure?

**RQ2:** How does the failure surface expand as SLR motivates higher TFO levels — and at what SLR level does failure become widespread across the GCM-probable climate space?

**RQ3:** At what points on the failure surface can operational information (perfect foresight) still sustain TFO — and where is the system storage-limited regardless of information quality?

---

## Novelty — Why this hasn't been done

Five connected facts that create a gap in the literature:

1. **SLR raises salt risk** — SLR above ~0.5m drives chloride exceedances at Camden intakes (RM 98)
2. **DRBC 2025-6 responds** — raises Trenton flow targets to push salt front back, but doesn't ask if LB can deliver
3. **NYC IERQ is capped** — 6.09 BG/yr; once exhausted, all Trenton support falls on Beltzville and Blue Marsh
4. **LB storage is limited** — dual mandate: flood control AND drought augmentation on the same storage
5. **The gap** — Brown 2012 uses annual model; Turner 2014 uses monthly; no study has mapped when LB storage becomes the binding constraint as TFOs rise with SLR

My TFO is a 1954 Decree obligation — failure is legally actionable. Prior Decision Scaling studies (Brown 2012, Turner 2014, Steinschneider 2015) use (ΔP, ΔT) climate space and don't have IERQ banking or multi-party governance.

---

## Three-Step Experiment Design

### Step 1 — Build Failure Surface

**Scenario space (3 axes):**
| Axis | Variable | Range | Notes |
|---|---|---|---|
| Streamflow | Synthetic DRB flows | Dry → wet percentile | From generator (Path B) |
| SLR | Sea level rise | 0 → 1.5m | Maps to TFO level via DRBC 2025-6 |
| LB volume | LB contribution capacity | Min → institutional max | Pywr-DRB input parameter |

**Generator decision (Path B — streamflow space):**
- Kirsch: standard multisite VAR model — generates synthetic DRB flows directly
- Gosney: inverse optimization — guarantees prescribed streamflow perturbation in output
- **Pending Scott's input.** Generator only handles streamflow axis. SLR and LB volume are separate Pywr-DRB inputs.

**What the model does per cell:**
- Set SLR → look up DRBC 2025-6 TFO elevation → pass as Pywr-DRB parameter
- Set LB volume → institutional contribution cap → Pywr-DRB parameter
- Draw streamflow realizations from generator for that percentile
- Run Pywr-DRB v2 (daily, FFMP drought stage switching, IERQ banking)
- **FFMP drought stage switching required** — shared implementation blocker (see `shared/lower_basin_ffmp_dev/`)

**Realization selection:**
- Steinschneider 2015 approach could reduce compute by 10×
- Ask Scott before implementing

### Step 2 — Performance Criteria

Three simultaneous criteria (following Turner 2014):

| Criterion | Threshold | Notes |
|---|---|---|
| Trenton reliability | < acceptable shortfall frequency | Primary — legally mandated |
| Shortfall severity | > severity threshold | Magnitude × duration |
| LB storage | < conservation pool | Structural depletion |

**Cell fails when ANY criterion is crossed.**

**Attribution per cell:**
- NYC-limited: IERQ bank exhausted before LB storage depleted → NYC is the binding constraint
- LB-limited: LB storage below conservation pool while IERQ bank remains → LB is binding
- This decomposition has no prior analog in the literature (Melbourne/Turner has no IERQ; no prior study has this multi-party structure)

### Step 3 — GCM Probability Weighting

**CMIP6 data enters here only — NOT a generator substitute.**

For each CMIP6 projection (7 GCMs × 2 hydro models = 14, SSP245 2020-2059):
1. Extract streamflow condition (e.g. mean annual flow at Montague, or NYC inflow aggregate)
2. Map model-period condition → cell in failure surface streamflow axis
3. Count GCMs landing in each cell → probability weight

**Output:** "X% of CMIP6 projections place DRB in failure region by 2075"  
Does NOT block Steps 1+2. Build failure surface first, overlay GCM weights last.

**Script to write first:** `scenario_extraction/extract_cmip6_cell_weights.py`

---

## Key Design Decisions (open, ask Scott)

| Decision | Options | Status |
|---|---|---|
| Generator choice | Kirsch (VAR) vs Gosney (inverse opt) | Pending Scott |
| Scenario space | Streamflow space (Path B, recommended) vs climate space (Path A) | Path B — committee recommended |
| Realization selection | Full grid vs Steinschneider 2015 subset | Pending Scott |
| Streamflow metric for Step 3 | NYC aggregate inflow vs Montague flow vs other | Pending Scott |
| Number of scenario cells | TBD — function of compute budget | TBD |

---

## Separation from StochasticExploratoryExperiment (Trevor Amestoy)

SEE generates large ensembles to characterize **drought event frequency** under stationary vs climate-shifted flow regimes. D1 maps a **structured scenario grid** to find the **failure surface boundary** and attributes failure to IERQ vs LB constraints. Different question, different code.

The SEE code is in `stochastic_experiment/` as **read-only reference** — do not base D1 implementation on it.

---

## Implementation Status

| Component | Status | Blocker |
|---|---|---|
| CMIP6 data (all 72 folders, all files) | ✓ Complete (SLURM 245198, 245199) | — |
| FFMP LB drought stage switching | ✗ Not implemented | Shared blocker — see `shared/lower_basin_ffmp_dev/` |
| IERQ banking (`banks.py`) | ✓ Implemented | — |
| Generator setup | ✗ Not started | Pending Scott (Kirsch vs Gosney) |
| Failure surface sweep script | ✗ Not started | Needs generator + LB drought stage |
| Performance criteria evaluation | ✗ Not started | Needs model runs |
| CMIP6 cell weight extraction | ✗ Not started | Can write now — independent |

---

## Folder Structure

```
D1_decision_scaling/
├── README.md                          # This file
├── experiments/                       # Experiment run scripts (to build)
│   └── run_failure_surface_sweep.py  # Step 1+2: per-cell Pywr-DRB runs
├── scenario_extraction/               # Step 3 CMIP6 weighting (can start now)
│   └── extract_cmip6_cell_weights.py
├── performance/                       # Step 2 criteria
│   └── criteria.py
├── generator/                         # Step 1 streamflow generation (pending Scott)
├── figures/                           # Gitignored
└── stochastic_experiment/             # Reference only — Trevor Amestoy's SEE
```

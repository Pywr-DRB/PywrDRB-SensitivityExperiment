# StochasticExploratoryExperiment — Reference Copy
**Source:** `github.com/Pywr-DRB/StochasticExploratoryExperiment` (Trevor Amestoy)  
**Copied:** 2026-05-25 for reference only

> **IMPORTANT:** This is Trevor Amestoy's work-in-progress for a separate paper. Do NOT use this code as D1's implementation base — that would risk overlap with his study. This copy is here so the codebase can be read for design patterns, not reused.

---

## Why it's here (read-only reference)

The SEE shows one pattern for combining a stochastic generator with Pywr-DRB. Reading it clarifies:
- How `KirschGenerator` + `NowakDisaggregator` from the `synhydro` package work
- How the Kirsch generator's monthly means can be shifted (lines 160–200 of `methods/generate.py`)
- How MPI-parallel Pywr-DRB ensemble runs are structured
- How Hashimoto RRV and SSI drought metrics are calculated post-simulation

## What SEE does (Trevor's paper)

SEE generates large synthetic ensembles (2000 realizations) under stationary and climate-adjusted conditions, runs Pywr-DRB over the full ensemble, and characterizes drought event frequency and system vulnerability. It maps performance across **temporal variability** within fixed climate scenarios.

## How D1 differs — avoid overlap

| | SEE | D1 |
|---|---|---|
| **Question** | How often do severe droughts occur under stationary vs climate-adjusted flow regimes? | At what (streamflow, SLR, LB volume) combinations does the system fail to meet Trenton targets? |
| **Generator role** | Primary scenario variable — generate large ensemble in 2-3 climate states | One axis of a 3D scenario grid — streamflow condition |
| **CMIP6 role** | Input to climate shift (monthly % change to generator means) | Step 3 only — probability weight failure surface cells |
| **SLR** | Not a variable | Core axis — SLR → DRBC 2025-6 TFO elevation → Pywr-DRB input |
| **LB volume** | Not a variable | Core axis — LB contribution → institutional parameter |
| **Attribution** | Ensemble-level shortage statistics | Per-cell: NYC IERQ exhaustion vs LB storage depletion |
| **Governance** | Not addressed | 5-party 1954 Decree, IERQ banking, FFMP drought stages |

D1's novelty is specifically in the (SLR × streamflow × LB volume) failure surface, the IERQ exhaustion / LB depletion attribution decomposition, and the daily Pywr-DRB simulation with FFMP drought stage switching — none of which SEE addresses.

---

## Useful reference files

- `methods/generate.py:160–200` — how monthly climate shift is applied to Kirsch means
- `methods/config.py` — CONFIG_NAME output isolation pattern (useful pattern to replicate)
- `06_calculate_performance_metrics.py` — Hashimoto RRV implementation (can borrow the metric calculation, not the ensemble framework)
- `data/nyc_inflow_selected_scenarios_PRMS_2020_2059.csv` — format of monthly % change vectors from CMIP6

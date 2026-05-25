# D1 Stochastic Experiment — Source and Adaptation Notes
**Source:** `github.com/Pywr-DRB/StochasticExploratoryExperiment` (Trevor Amestoy)  
**Copied:** 2026-05-25

---

## What this is

The StochasticExploratoryExperiment (SEE) is the closest existing Pywr-DRB infrastructure to D1's Decision Scaling design. It uses the **Kirsch-Nowak** stochastic generator to produce large synthetic streamflow ensembles, then optionally applies **CMIP6-derived monthly climate shifts** to those ensembles before running Pywr-DRB.

---

## How CMIP6 connects to the Kirsch generator

The bridge is `data/nyc_inflow_selected_scenarios_PRMS_2020_2059.csv` — 12 monthly percentage change values (low / medium / high) derived from CMIP6 PRMS 2020-2059 projections.

Inside `01_generate_ensemble_sets.py`, when `type == 'climate_adjusted'`:
```python
# Shift the Kirsch generator's log-scale monthly means
new_mean_month.loc[:, site] = np.exp(baseline_monthly_mean.loc[:, site]) \
                              * (1 + np.array(monthly_prc_change) / 100.0)
kirsch_gen.mean_month = np.log(new_mean_month)
```

The generator then samples from these shifted distributions, producing synthetic flows that reflect a particular climate trajectory — without being tied to a single GCM realization.

**D1 will extend this:** instead of 2-3 discrete climate scenarios, D1 maps all 14 CMIP6 projections (7 GCMs × 2 hydro models, SSP245 2020-2059) to individual monthly shift vectors, explores the scenario space systematically for failure surface identification, then weights by GCM skill against historical.

---

## SEE workflow (what's here)

| Script | Role |
|---|---|
| `00_run_baseline_simulations.py` | Baseline Pywr-DRB run on historical flows |
| `01_generate_ensemble_sets.py` | MPI Kirsch-Nowak generation (2000 realizations / 20 sets) |
| `02_prep_pywrdrb_inputs.py` | Convert synthetic flows to pywrdrb inflow format |
| `03_run_pywrdrb_simulations.py` | MPI Pywr-DRB ensemble runs |
| `04_postprocess_data_mpi.py` | HDF5 → shortage / zone / contribution CSVs |
| `05_calculate_ssi_drought_metrics.py` | SSI-based drought identification |
| `06_calculate_performance_metrics.py` | Hashimoto RRV, annual metrics, event metrics |

Config in `methods/config.py`. Three dataset IDs: `stationary_ensemble`, `climate_adjusted_low`, `climate_adjusted_high`.

Key settings (from SEE config):
- `TOTAL_REALIZATIONS = 2000`, `N_REALIZATIONS_PER_ENSEMBLE_SET = 100`
- `START_DATE = '2030-01-01'`, `END_DATE = '2100-12-31'`
- `BASELINE_DATASET = 'pub_nhmv10_BC_withObsScaled'`
- `FLOW_PREDICTION_MODE = 'perfect_foresight'`

---

## What D1 needs beyond SEE

| Need | SEE | D1 |
|---|---|---|
| Climate scenarios | 2 discrete (low/high) | 14 CMIP6 projections + continuous scenario grid |
| Scenario space | Not mapped | Must identify failure surface (binary pass/fail across scenario grid) |
| GCM weighting | Not done | Bayesian / skill-weighted using SSP126 1980-2019 vs observed |
| Scenario period | 2030-2100 | Near-future (2020-2059), aligned with "by 2075" framing |
| Failure metric | Hashimoto RRV, shortage events | Same — already implemented |

---

## Key files to read next

- `methods/config.py` — all parameters centralized here
- `methods/generate.py` — Kirsch fitting + climate shift application (lines 160-200)
- `data/nyc_inflow_selected_scenarios_PRMS_2020_2059.csv` — template for D1 climate states

---

## D1 TODO: extracting monthly shifts from all 14 CMIP6 projections

The `data/` CSV has only 3 scenarios. D1 needs a script that:
1. Reads each of the 14 CMIP6 `gage_flow_mgd.csv` files (SSP245, 2020-2059)
2. Computes monthly mean flows per node
3. Computes % change vs `PRMS_RAPID_Daymet2019_1980_2019` baseline
4. Outputs one 12-value vector per GCM/hydro-model pair

This script belongs in `D1_decision_scaling/scenario_extraction/extract_cmip6_monthly_shifts.py`.

Ask Scott: should the monthly shift be computed from NYC aggregate inflow (cannonsville + pepacton + neversink) or Trenton gage flow?

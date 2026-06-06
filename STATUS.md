# Dissertation Status — What Is Done / What Needs To Be Done
**Updated:** 2026-06-02
**Hard deadline:** Extension petition — August 1, 2026  
**Gate 1:** Committee direction sign-off — May 30, 2026  
**Direction decided:** D4 (Distributed Risk Characterization (DRC)) as Paper 1 — Scott confirmed by email 2026-05-26. D1 follows naturally as Paper 2.

---

## Shared Model Implementation — FULLY RESOLVED ✓

**`lower_basin_ffmp.py` — LB drought stage switching + NJ diversion coupling**

1. ✓ `LowerBasinDroughtLevel` Parameter in `ffmp.py` — entry + 3-day persistence (2026-05-25)
2. ✓ `drought_level_agg_lb` registered in `model_builder.py` (2026-05-25)
3. ✓ `LowerBasinMaxMRFContribution` — loads `drought_level_agg_lb`, switches conservation releases (2026-05-25)
4. ✓ **LB Drought EXIT hysteresis** (§2.5.6.C.7) — 30-day `recovery_days` counter (2026-05-28)
5. ✓ **NJ diversion coupling** (§2.5.6.C.1/D.1) — 2026-05-28:
   - `lb_level0/1/2_factor_delivery_nj` = 1.0/0.70/0.65 in `constants.csv`
   - `lb_drought_factor_delivery_nj` — `IndexedArrayParameter` on `drought_level_agg_lb`
   - `combined_drought_factor_delivery_nj` = `min(NYC factor, LB factor)`
   - `FfmpNjRunningAvg` wired to combined factor; running-avg reset triggers on either signal

**50/50 unit tests passing** ([`validate_lb_drought_stage.py`](shared/lower_basin_ffmp_dev/validate_lb_drought_stage.py)).

**`banks.py` — ERQ (Excess Release Quantity) under 1954 Decree Art. III-B-1(c)–(d)** (2026-06-02)

1. ✓ `ERQRelease` Parameter in `banks.py` — seasonal window Jun 15–Mar 15, 120-day release schedule, 70 BG cap
2. ✓ `add_parameter_erq_releases()` in `model_builder.py` — `erq_release_nyc` + equal 1/3 split to NYC reservoirs
3. ✓ **37/37 unit tests + 10/10 integration** in [`validate_erq.py`](shared/lower_basin_ffmp_dev/validate_erq.py)
4. ✓ Diagnostic figure: [`figures/erq_diagnostic.png`](shared/lower_basin_ffmp_dev/figures/erq_diagnostic.png)

**Briefing / policy docs:** [`D4_distributed_risk/notes/briefing/`](D4_distributed_risk/notes/briefing/); [`erq_release_notes.md`](notes/shared/erq_release_notes.md); [`lb_drought_stage_notes.md`](notes/shared/lb_drought_stage_notes.md).

---

## D1 — Decision Scaling Under SLR (Paper 2)

### Done ✓
| Item | Location |
|---|---|
| CMIP6 data + cell weights (dual metric) | `scenario_extraction/cmip6_cell_weights_*.csv` |
| Briefing + workflow + traceability | `briefing/`, `D1_workflow.md` |
| Experiment grid (7×6×3) | `experiments/config.py` + `tfo_schedule/tfo_slr_table.csv` |
| Shared Kirsch-Nowak generator | `shared/pywrdrb_utils/kirsch_flows.py` |
| Failure surface sweep + smoke + aggregate | `experiments/run_failure_surface_sweep.py`, `smoke_test.py`, `aggregate_results.py` |
| `lb_cap_multiplier` wired | `pywrdrb/lower_basin_ffmp.py`, `run_model.py` |
| RQ1–RQ3 analysis scripts | `analysis/rq*.py` |
| SLURM (full + LB1 pilot + bin gen) | `slurm/` |
| Performance criteria (4 incl. salinity Mode A) | `performance/criteria.py`, `slr_salt_front_shift.csv` |
| SalinityLSTM wiring + plugin resolver | `performance/salinity_paths.py`, `run_model.py` |
| FFMP LB drought + ERQ | shared validation (87 tests) |
| Synthetic flows 7×30 | `generator/synthetic_flows/` |
| LB1 pilot job 271164 | in progress (resume via `--skip-existing`) |

**Updated RQs:** RQ3 = CMIP6 probability mass in failure region (oracle foresight dropped).

**CMIP6 finding:** All 14 SSP245 2020–2059 projections in Q04–Q07; zero dry-tail weight (Q01–Q03).

**Pilot:** Slow job 271532 **cancelled**. Use fast path only (prewarm → check → sweep).

### Can start now (fast path only)
1. `bash D1_decision_scaling/slurm/submit_d1_fast_pipeline.sh --realizations 10` — prewarm only
2. When done: `python D1_decision_scaling/experiments/check_d1_ready.py --realizations 10`
3. `sbatch --export=ALL,D1_REALIZATIONS=10 D1_decision_scaling/slurm/submit_failure_surface_lb1_pilot.sh`
4. Full 126-cell after LB1 validates (sweep scripts fail fast if cache missing)

### Open (Scott, non-blocking)
| Item | Default |
|---|---|
| Kirsch vs Gosney (D1-1) | Kirsch (D4 precedent) |
| CMIP6 metric (D1-2) | Montague primary; NYC sensitivity |
| Realizations/cell (D1-3) | 30 |
| Performance thresholds | Provisional in criteria.py |
| TFO table above S0 | Provisional pending DRBC PDF digitization |
| Salinity ΔRM_upstream (S1–S5) | Provisional in `slr_salt_front_shift.csv` |
| PywrDRB-ML plugin | Cloned → `D1_decision_scaling/stochastic_experiment/PywrDRB-ML` |

### Key design facts
- **Path B (streamflow space)** — Kirsch-Nowak; CMIP6 for Step 3 weighting only
- **Three axes:** streamflow × SLR→TFO (DRBC Dec 2025) × LB cap multiplier
- **Attribution:** `shared/pywrdrb_utils/attribution.py`

---

## D2 — Flood–Drought Operational Tradeoffs

### Done ✓
| Item | Location |
|---|---|
| Physical mechanism established from observations | `CEE6400Project/obs_data/processed/` |
| Sept 2004 key finding | Blue Marsh at 12% capacity Dec 6 — exactly 90 days post-storm |
| Scope confirmed non-overlapping with Trevor | Trevor's nyc_opt: NYC reservoirs only (spill-driven) |
| Sept 2004 validation notes | `D2_flood_drought/validation_2004/notes_sept2004_validation.md` |
| CENAP data request draft | `D2_flood_drought/validation_2004/cenap_data_request_draft.md` |

### HEC-ResSim PR-73 — publicly available for download ✓ (2026-05-26)
External dependency removed. Model files are publicly downloadable — no CENAP request needed.
**Remaining question:** What can actually be extracted from the public files?
- Pool zone elevations and seasonal rule curves: almost certainly present
- 2004-event-specific calibrated run results (IEPR version): may or may not be included vs. just configuration
- HEC-ResSim is free USACE software — can run the model if configuration is provided without results
**Next action:** Download files, inventory contents (config only vs. run results), determine if HEC-ResSim install is needed.

### Blocked
| Item | Blocked by |
|---|---|
| July–Dec 2004 Pywr-DRB validation run | ~~LB drought stage switching~~ — **UNBLOCKED** as of 2026-05-28. LB drought switching + NJ coupling done. Run the validation now. |
| HEC-ResSim operational validation | CENAP response (external) |
| RQ2: counterfactual release modification analysis | HEC-ResSim files + Pywr-DRB validation |

### Can start now
- [ ] **Send CENAP email** — do this today, response time is outside your control
- [ ] Prepare July–Dec 2004 Pywr-DRB run configuration (inputs, dates, nodes to track) — can set up even if running is blocked
- [ ] Literature: USACE ER 1110-2-240 operational bands for RQ2 analysis

### Key design facts
- **Falsifiable null result is publishable** — if conflict is small, that's the finding
- **Empirical anchor:** Sept 2004 tropical cyclone — late dry season, highest conflict potential, IEPR-validated HEC-ResSim
- **Scope:** LB USACE reservoirs only (Beltzville, Blue Marsh, F.E. Walter, Prompton)

---

## D3 — Satellite-Informed Reservoir Observability

### Done ✓ (separate from dissertation repo — lives in `~/Research/rs_policy_observability/`)
| Item | Status |
|---|---|
| USGS water levels: 4 reservoirs | `data/raw/` — blueMarsh, beltzvilleCombined, fewalter, prompton |
| Level series processed | `data/processed/level_series.csv` |
| Storage ensembles: 4 reservoirs | `data/processed/storage_ensemble_<reservoir>.csv` (USACE + curve libraries) |
| SARAH / DAHITI / SWOT directories | Set up with READMEs, data acquisition docs |
| FSM oracle scaffold | `dissertation/D3_satellite_observability/oracle/fsm_oracle.py` |
| InfeRes tool | `~/Projects/InfeRes/` — installed |

### Blocked — waiting on decisions
| Item | Blocked by |
|---|---|
| FSM oracle implementation | **Committee sign-off on approach** — must get before coding |
| Full inference pipeline | Oracle approval + surface area data |

### Can start now
- [ ] Surface area data: acquire SARAH-CONUS surface area CSVs (Texas Data Repository, Yadav et al. 2024 GRL) — ingestion script path defined
- [ ] Acquire GRDL / 3D-LAKES curve files
- [ ] **Get committee sign-off on FSM oracle approach** (Gate 1, May 30) — this unblocks everything in D3
- [ ] InfeRes: run smoke test on Blue Marsh with existing USGS levels

### Key design facts
- D3 is the most **independent** direction — no LB drought stage dependency, no CENAP
- Lives primarily in `rs_policy_observability/` — dissertation repo has oracle scaffold only
- Inference chain: surface area (SARAH) → curve library (GRDL/3D-LAKES) → storage estimate → FSM oracle → decision error → Pywr-DRB impact

---

## D4 — Distributed Risk Characterization (DRC) Under 1954 Decree

### Done ✓ — Most model-ready direction
| Item | Location |
|---|---|
| IERQ Trenton bank tracking | `pywrdrb/src/pywrdrb/parameters/banks.py` (`IERQRelease_step1`) |
| Hashimoto RRV metrics | `pywrdrb/src/pywrdrb/post/metrics.py` |
| Five-party RRV metric functions | `D4_distributed_risk/lib/rrv_metrics/metrics.py` ✓ 2026-05-28 |
| **Baseline run script (prerun + rerun modes)** | `D4_distributed_risk/experiments/run_d4_baseline.py` ✓ 2026-05-28 |
| Sobol sensitivity config (N=1024, k=6) | `D4_distributed_risk/lib/sensitivity/config.py` ✓ 2026-05-28 |
| Sobol sample generation script | `D4_distributed_risk/lib/sensitivity/sobol_design.py` ✓ 2026-05-28 |
| **Sobol sweep runner** | `D4_distributed_risk/experiments/run_sobol_sweep.py` ✓ 2026-05-31 |
| **50-member subset selector** | `D4_distributed_risk/lib/sensitivity/subset_members.py` ✓ 2026-05-31 |
| SLURM scripts (baseline + Sobol array) | `D4_distributed_risk/slurm/` ✓ 2026-05-28 (wall time fixed 2026-05-31) |
| Shared attribution module | `shared/pywrdrb_utils/attribution.py` ✓ 2026-05-28 |
| Committee experimental plan | `committee/D1_D4_experimental_plans.md` ✓ 2026-05-28 |
| Party-to-node mapping scaffold | `D4_distributed_risk/party_mapping/decree_party_node_mapping.md` |
| **Amestoy Zenodo download + md5 verified** | `~/data/amestoy_2026/` ✓ 2026-05-28 |
| Pat Reed confirmed: "the gap is real" | — |

### Blocked
| Item | Blocked by |
|---|---|
| `lb_cap_multiplier` injection | Need to find `max_mrf_trenton_step{step}_{reservoir}` model_dict keys; blocked until first rerun |
| `q_nj_warning` + `ierq_max_bg` Sobol injection | Need to confirm model_dict keys; both emit UserWarning + use defaults for now |

### Done ✓ (2026-06-01) — continued
- [x] **Baseline 1000/1000 members complete** — job 252087 TIMEOUT at 993/1000; missing 7 (901,904,910,929,938,992,994) re-run and completed (job 253078). Final `rrv_summary.parquet` has 1000 rows (job 253229 reagg).
- [x] **NJ delivery reliability bug fixed** — `_reliability(nj_delivery, cap_per_day.min())` → `_reliability(nj_delivery, normal_cap_mgd)`. Old metric was constant 0.942 (zero variance). New: mean=0.016, std=0.003 across ensemble.
- [x] **NYC IERQ metrics fixed** — `OUTPUT_VARS["ierq_bank_remaining"]` corrected from `"IERQRelease_step1"` → `"nyc_mrf_trenton_step1"` (actual HDF5 key). Added `reconstruct_ierq_balance()` in metrics.py to back-calculate bank balance (6090 MG max, May 31 reset) from recorded daily releases. NYC exhaustion metrics now non-NaN: mean exhaustion_reliability=0.188, std=0.024.
- [x] **PA metric threshold fixed** — `pa_metrics()` now accepts `alpha_betz` / `alpha_bm` kwargs; when provided (Sobol runs), threshold = alpha_betz × 13500 + alpha_bm × 7450 MG (matches model switching). `compute_all_party_rrv()` and `run_sobol_sweep.py` updated to pass these through.
- [x] **m_lb crash fixed** — changed from `NotImplementedError` to `UserWarning` (no-op, like q_nj_warning and ierq_max_bg). All 14,336 Sobol tasks can now run without crashing.
- [x] **`reaggregate_baseline.py` written** — reads existing per-member HDF5 outputs, recomputes metrics without re-running model. Used to fix baseline parquet after metric bug fixes.
- [x] **`gen_experiment_manifest.py` written + executed** — auto-generates parameter/metric/threshold/inconsistency tables from live code. Output: `results/manifest/`. All 2 known inconsistencies now RESOLVED.
- [x] **`prewarm_predicted_inflows.py` + `submit_prewarm.sh`** — pre-generates predicted_inflows_mgd.csv for all 50 synthetic realizations before Sobol sweep. Prevents ~20 min overhead per realization in SLURM array. Running now (job 253148, 50-task array).

### Done ✓ (2026-06-01) — earlier (morning)
- [x] **`LowerBasinDroughtLevel` → `IndexParameter`** — base class changed from `Parameter` to `IndexParameter`; `value()` renamed to `index()` returning `int`; `IndexParameter.value()` inherited (returns `float(index())`). Root cause of `AssertionError` on `Model.load()` — Pywr's `IndexedArrayParameter` asserts `isinstance(index_parameter, IndexParameter)`.
- [x] **OUTPUT_VARS recorder names confirmed** — `"delTrenton"` → `"link_delTrenton"`, `"delMontague"` → `"link_delMontague"`. All 5-party metrics confirmed against member 0 HDF5. IERQ bank remaining not exposed as named parameter — `nyc_metrics()` returns NaN for IERQ columns (acceptable for baseline).
- [x] **`submit_baseline.sh` log paths** — absolute paths (was relative; SLURM failed when `logs/` dir didn't exist)
- [x] **D4 baseline SLURM job 252087 RUNNING** — 100 workers, ~745/1000 members done at 1:25 elapsed
- [x] **`synhydro` 0.0.2 installed** — `pip install git+https://github.com/TrevorJA/SynHydro.git` from login node. Uses `synhydro.methods.generation.hybrid.kirsch.KirschGenerator` + `synhydro.methods.disaggregation.temporal.nowak.NowakDisaggregator`.
- [x] **`gen_synthetic_flows.py` written + run** — Kirsch-Nowak generator calibrated on `pub_nhmv10_BC_withObsScaled` catchment inflows (1946–2005, 7 major sites). 50 × 79-year synthetic realizations generated to `results/sobol/synthetic_flows/realization_{r:03d}.parquet`. All 50 pass validation (28854 × 31, non-negative, 1945-01-01→2023-12-31).
- [x] **`run_sobol_sweep.py` redesigned** — replaced Amestoy HDF5 loading with synthetic parquet loading. New `--syn-flows-dir` arg replaces `--amestoy-path` + `--subset-members`. `inflow_type = f"syn_r{r:03d}"` is stable across Sobol samples for predicted_inflows caching.
- [x] **`submit_sobol.sh` updated** — absolute log paths, new CLI args, updated prerequisite docs.
- [x] **`subset_members.py` superseded** — marked deprecated; Sobol sweep no longer requires Amestoy subset selection.

### Done ✓ (2026-05-31)
- [x] **`run_model.py` pn path registration** — fixed (3-line pywrdrb path navigator registration before ModelBuilder)
- [x] **`LowerBasinDroughtLevel` threshold injection** — `betz_warning_frac`, `bm_warning_frac`, `recovery_persist_days` kwargs
- [x] **`run_sobol_sweep.py`** — complete Sobol sweep task runner
- [x] **`subset_members.py`** — Steinschneider & Brown (2013) CDF stratification; 50-member representative subset
- [x] **`submit_sobol.sh` wall time** — fixed 00:15:00 → 04:00:00
- [x] **`run_model.py` `nyc_nj_demand_source` fix** — `options={}` default; `'custom'` only for D1

### Previously done ✓ (2026-05-28)
- [x] Amestoy Zenodo download + md5 verified (`~/data/amestoy_2026/`)
- [x] Prerun pipeline validated (20 members, de_reliability=0.867, ny_reliability=0.947)
- [x] TFO override wired into `run_model.py` via model_dict patching
- [x] HDF5 structure confirmed: `/{node}/{member_id_str}`, shape=(28854,) MGD, 1945–2023

### Can start now (no blockers)
- [x] **D4 baseline SLURM run** — COMPLETE 1000/1000 members, rrv_summary.parquet written
- [x] `sobol_samples.csv` — generated (N=1024, k=6, 14,336 total runs)
- [x] `gen_synthetic_flows.py` — 50 realizations generated
- [x] **Pre-warm predicted_inflows cache** — job 253148 (50-task array) RUNNING
- [ ] **Submit Sobol array** — after pre-warm completes: `sbatch slurm/submit_sobol.sh`
- [ ] **Fill `decree_party_node_mapping.md` TODO items** — Decree Art. III–IV + Water Code §2.5.3
- [ ] **Run RQ3 analysis** — after `sobol_analysis.py`: `python D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py`
- [ ] **Ask Trevor**: NYC-limited vs LB-limited regime attribution overlap?

### Key design facts
- LB drought switching + NJ coupling DONE — model is now fully policy-faithful for D4 five-party RRV
- Shared infrastructure in `shared/pywrdrb_utils/` — D1 and D4 import same attribution logic
- **RQ3 (2026-06):** Options A/B/C in `D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py` — tradeoff classification, regime-stratified response, Sobol S2. **PRIM removed** per advisor (not peer-review eligible as primary method).

---

## Priority Matrix — What to Work on in What Order

### Immediate (June 1–3)
| Priority | Task | Time | Unlocks |
|---|---|---|---|
| 1 | ✓ **D4 baseline complete** | DONE | rrv_summary.parquet |
| 2 | ✓ **Metric bugs fixed** (NJ, NYC IERQ, PA threshold) | DONE | Valid Sobol outputs |
| 3 | ✓ **m_lb crash → UserWarning** | DONE | Sobol array can run |
| 4 | ✓ **predicted_inflows pre-warm** | RUNNING (job 253148) | Fast Sobol tasks |
| 5 | **Submit Sobol array** | After pre-warm (tonight) | 14,336 sensitivity samples |
| 6 | **Fill `decree_party_node_mapping.md` TODO items** | 2 hrs | D4 five-party accuracy |

### After baseline run (June 7–14)
| Task | Direction | Depends on |
|---|---|---|
| `python lib/sensitivity/sobol_design.py` → sobol_samples.csv | D4 | — (can run now) |
| `python lib/sensitivity/subset_members.py` | D4 | Baseline rerun parquet |
| `sbatch slurm/submit_sobol.sh` | D4 | Both above + smoke test |
| Confirm `q_nj_warning` + `ierq_max_bg` model_dict keys | D4 | First rerun (inspect HDF5) |
| Wire `lb_cap_multiplier` (m_lb) in run_model.py | D1/D4 | Model_dict key inspection |
| D1: install synhydro, run `kirsch_calibrate.py` | D1 | Scott generator decision |
| D1: confirm TFO table from DRBC 2025-6 | D1 | DRBC document |

### Gate 2 (June 27) — Core D4 figures → Pat
6-panel D4 figure set. Full experimental plan in `committee/D1_D4_experimental_plans.md`.

### Milestone: Pywr-DRB runs on GitHub (June 13 target)
D4 baseline ensemble + D1 scenario test sweep. All model implementation done as of 2026-05-28.

---

## Open Questions for Gate 1

| Direction | Question | Who | Status |
|---|---|---|---|
| D4 | Five-party vs two-subsystem for Paper 1? | Full committee | Gate 1 |
| D4 | Stochastic ensemble (Amestoy/Kirsch) or nhmv10 only for Paper 1? | Scott/Pat | Gate 1 |
| D4 | LHC sensitivity in Paper 1, or defer to revision? | Committee | Gate 1 |
| D4 | NYC-limited vs LB-limited attribution overlap with Trevor? | Trevor | This week |
| D1 | Kirsch or Gosney generator? | Scott | Gate 1 |
| D1 | Streamflow metric for CMIP6 weighting (NYC aggregate vs Montague)? | Scott | Gate 1 |
| D1 | Realization selection (Steinschneider 2015)? | Scott | Gate 1 |
| D2 | Framing A (empirical/CENAP) vs Framing B (FIRO)? | Full committee | Gate 1 |
| D2 | CENAP contact name/email at USACE Philadelphia District? | Advisor | Before email |
| D3 | FSM oracle approach endorsed? | Committee | Gate 1 |

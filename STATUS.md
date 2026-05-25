# Dissertation Status — What Is Done / What Needs To Be Done
**Updated:** 2026-05-25  
**Hard deadline:** Extension petition — August 1, 2026  
**Gate 1:** Committee direction sign-off — May 30, 2026

---

## Shared Critical Path Blocker — RESOLVED ✓ (2026-05-25)

**`lower_basin_ffmp.py` — LB drought stage switching**

**DONE.** All three changes implemented and syntax-verified.

1. ✓ `LowerBasinDroughtLevel` Parameter in `ffmp.py` — checks Blue Marsh + Beltzville fractions
   against Water Code §2.5.6 thresholds; 3-day persistence counter for full LB Drought
2. ✓ `drought_level_agg_lb` registered in `model_builder.py` → `add_parameter_nyc_reservoirs_operational_regimes`
3. ✓ `LowerBasinMaxMRFContribution` in `lower_basin_ffmp.py`:
   - Loads `drought_level_agg_lb` (graceful KeyError fallback if absent)
   - `get_current_usable_reservoirs()` checks NYC AND LB drought
   - `value()` computes R_min dynamically from normal vs drought conservation releases

**Next step:** Run July–Dec 2004 validation — expect non-zero LB Trenton contributions Oct–Dec 2004.

---

## D1 — Decision Scaling: Trenton Flow Objectives Under SLR

### Done ✓
| Item | Location |
|---|---|
| CMIP6 data: all 72 folders, all files | `cmip6/pywrdrb/inputs/` (symlink) |
| Diversions generated (all 72) | SLURM job 245198 ✓ |
| Predicted inflows in progress | SLURM job 245199 running |
| Experiment design + RQs | `D1_decision_scaling/README.md` |
| Performance criteria (Step 2 skeleton) | `D1_decision_scaling/performance/criteria.py` |
| CMIP6 cell weight extraction script (Step 3) | `D1_decision_scaling/scenario_extraction/extract_cmip6_cell_weights.py` |
| SEE reference code (read-only) | `D1_decision_scaling/stochastic_experiment/` |

### Blocked — waiting on decisions
| Item | Blocked by | Who decides |
|---|---|---|
| Generator choice: Kirsch vs Gosney | Pending | Scott |
| Streamflow metric for Step 3 mapping (NYC aggregate vs Montague) | Pending | Scott |
| Realization selection (Steinschneider 2015, ~10× compute reduction) | Pending | Scott |
| Failure surface sweep script | Generator choice + LB drought stage | Scott + implementation |
| D1 model runs | All above | — |

### Can start now (no blockers)
- [ ] Run `extract_cmip6_cell_weights.py` once job 245199 completes — produces Step 3 probability weights
- [ ] Committee sign-off on scenario space (streamflow space Path B confirmed; ask Scott: Kirsch or Gosney)
- [ ] Gate 1 meeting: confirm D1 direction by May 30

### Key design facts (locked)
- **Path B (streamflow space)** — Kirsch or Gosney generator → synthetic DRB flows. No weather generator, no hydrologic model.
- **CMIP6 enters Step 3 only** — probability weighting of failure surface cells, not generator input
- **Three axes:** streamflow (generator) × SLR → TFO (DRBC 2025-6) × LB contribution cap
- **Attribution:** NYC IERQ exhaustion vs LB storage depletion — per-cell decomposition
- **NOT overlap with SEE** — SEE maps drought event frequency across ensembles; D1 maps failure surface boundary with attribution

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

### Critical external dependency — take action immediately
| Item | Action | Timeline risk |
|---|---|---|
| **CENAP data request** | **Send the drafted email NOW** — HEC-ResSim PR-73 model files from USACE CENAP. This is the highest-risk dependency: government response time is unpredictable. | HIGH |

### Blocked
| Item | Blocked by |
|---|---|
| July–Dec 2004 Pywr-DRB validation run | LB drought stage switching — model currently shows **zero** LB Trenton contributions Oct–Dec 2004 (see `lower_basin_mrf_contributions.csv`). The mechanism exists physically but Pywr-DRB cannot reproduce it. |
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

## D4 — Cooperative Risk Attribution Under 1954 Decree

### Done ✓ — Most model-ready direction
| Item | Location |
|---|---|
| IERQ Trenton bank tracking | `pywrdrb/src/pywrdrb/parameters/banks.py` (`IERQRelease_step1`) |
| Hashimoto RRV metrics | `pywrdrb/src/pywrdrb/post/metrics.py` |
| D4 baseline run scaffold (full per-party metrics) | `D4_cooperative_risk/rrv_metrics/run_d4_baseline.py` |
| Party-to-node mapping scaffold | `D4_cooperative_risk/party_mapping/decree_party_node_mapping.md` |
| Pat Reed confirmed: "the gap is real" | — |

### Blocked
| Item | Blocked by |
|---|---|
| RQ1 baseline simulations | **LB drought stage switching** — IERQ exhaustion vs LB depletion attribution requires LB staging |
| Ensemble runs | LB drought stage + Amestoy 1000-member ensemble download |

### Can start now (no blockers)
- [ ] **Write party-to-subsystem mapping** — read 1954 Decree Articles III–IV + Water Code §2.5.3 together, fill exact flow targets per party. Pure document work, no model.
- [ ] **Download Amestoy 1000-member reconstruction** from Zenodo (no model dependency)
- [ ] **baseline_metrics.py**: add PA storage depletion rate + NJ diversion restriction days — ~50 lines each, independent of LB drought stage
- [ ] **Ask Trevor**: does NYC-limited vs LB-limited regime attribution overlap with any planned dissertation papers?
- [ ] **Gate 1**: committee endorsement — five-party vs two-subsystem framing? Is this Paper 1 standalone?

### Key design facts
- **Immediate executable** once LB drought stage is done — no external data dependencies
- **Two-subsystem framing first** — run NYC vs LB attribution, then extend to five-party if committee confirms
- Concern from committee: asymmetric NYC/LB model development. Response: that asymmetry IS the finding — we're measuring how institutional rules distribute risk given current model fidelity.

---

## Priority Matrix — What to Work on in What Order

### This week (before May 30 Gate 1)
| Priority | Task | Time | Unlocks |
|---|---|---|---|
| 1 | **Send CENAP email** | 30 min | D2 external dependency starts its clock |
| 2 | **LB drought stage switching** | 1–2 days | D1 + D2 + D4 model runs |
| 3 | **Party-to-node mapping (D4)** | 2–3 hrs | D4 committee discussion |
| 4 | **Ask Scott: Kirsch vs Gosney, streamflow metric** | Meeting | D1 generator setup |
| 5 | **Get D3 oracle sign-off (Gate 1)** | Meeting | D3 implementation |
| 6 | **Run extract_cmip6_cell_weights.py** | 30 min | D1 Step 3 |

### After Gate 1 (May 30 – June 13)
| Task | Direction | Depends on |
|---|---|---|
| Set up generator + failure surface sweep | D1 | Generator choice + LB drought stage |
| July–Dec 2004 Pywr-DRB validation run | D2 | LB drought stage |
| D4 baseline ensemble run | D4 | LB drought stage + Amestoy download |
| Surface area data acquisition (SARAH) | D3 | Nothing |
| baseline_metrics.py PA + NJ extensions | D4 | Nothing |

### Milestone: Pywr-DRB runs on GitHub (June 13 target)
D1 failure surface sweep + D4 baseline runs. Requires LB drought stage done by June 6.

---

## Open Questions for Each Direction

| Direction | Question | Who | Urgency |
|---|---|---|---|
| D1 | Kirsch or Gosney? | Scott | This week |
| D1 | Streamflow metric for Step 3 (NYC aggregate vs Montague)? | Scott | This week |
| D1 | Realization selection (Steinschneider 2015)? | Scott | Before sweep |
| D2 | CENAP contact at USACE CENAP? (name, email) | Advisor | Send email today |
| D3 | FSM oracle approach endorsed? | Committee | Gate 1 |
| D4 | Five-party vs two-subsystem framing for Paper 1? | Committee | Gate 1 |
| D4 | Parameter ranges reasonable (±10–20% thresholds, ±15–30% MRF cap)? | Committee | Gate 1 |
| D4 | NYC-limited vs LB-limited attribution overlap with Trevor? | Trevor | This week |
| All | D4 as Paper 1 (most model-ready), D1+D2 as Papers 2+3? | Committee | Gate 1 |

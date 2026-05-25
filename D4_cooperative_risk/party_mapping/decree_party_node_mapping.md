# 1954 Decree Party-to-Subsystem Mapping
**Direction 4 — Cooperative Risk Attribution**  
Status: DRAFT — fill in from Decree Articles III–IV + Water Code §2.5.3

---

## Purpose
Map each party to the Supreme Court Decree (NJ v. NY, 1954) to specific Pywr-DRB nodes, storage accounts, and flow targets. This document defines the measurable "risk" each party bears under current DRBC rules — the foundation for per-party RRV metric calculation.

---

## Party Mapping

### Delaware (DE)
**Primary interest:** Trenton flow reliability (downstream salinity / water quality)
- **Pywr-DRB node:** `delTrenton` recorder
- **Metric:** Trenton flow reliability = fraction of days flow ≥ TFO target
- **Decree reference:** Article III, §[X] — Trenton Flow Objective
- **Failure definition:** daily flow at Trenton < TFO target (currently [X] MGD baseline; elevated by DRBC 2025-6 under SLR)
- **Notes:** DE is the downstream party most directly affected by TFO shortfalls. Salinity at Camden intakes (RM 98) is the physical mechanism behind TFO requirements.

### New York City (NYC)
**Primary interest:** Diversion availability and IERQ bank access
- **Pywr-DRB node:** `banks.py` → `IERQRelease_step1` (tracks 6.09 BG/yr Trenton bank); `drought_level_agg_nyc`
- **Metric 1:** IERQ exhaustion days = days IERQ bank reaches zero before year reset
- **Metric 2:** Diversion reliability = fraction of days NYC diversions not curtailed by Decree restrictions
- **Decree reference:** Article VII — NYC diversion rights (up to 800 MGD / 1.1 BG/day combined)
- **Failure definition:** IERQ bank exhausted (all 6.09 BG consumed) before June 1 reset
- **Notes:** NYC operations are the primary driver of basin dynamics per Pat Reed. IERQ exhaustion is the hard upper bound on NYC's downstream contribution — after this, LB bears full responsibility.

### Pennsylvania (PA)
**Primary interest:** Lower basin reservoir storage availability
- **Pywr-DRB nodes:** `reservoir_beltzvilleCombined`, `reservoir_blueMarsh` (USACE LB reservoirs)
- **Metric:** LB conservation pool depletion rate = fraction of days combined LB storage (blueMarsh + beltzville) falls below conservation pool threshold (~69% of usable pool for blueMarsh, ~73.7% for beltzville)
- **Decree reference:** Article IV — Delaware Basin tributaries; Water Code §2.5.3 — LB reservoir contributions
- **Failure definition:** combined LB storage < conservation pool in drought period
- **Notes:** PA hosts Beltzville and Blue Marsh (LB USACE reservoirs) which carry dual mandates (flood control + DRBC drought augmentation). F.E. Walter is in PA but not fully implemented in model yet.

### New Jersey (NJ)
**Primary interest:** NYC diversion restriction (protects NJ stream flows and NJ's share of basin yield)
- **Pywr-DRB node:** NYC diversion parameter (extrapolated NJ diversions); FFMP restriction triggers
- **Metric:** NJ diversion restriction days = days NYC diversions fall below FFMP-specified limit due to Decree restrictions
- **Decree reference:** Article IV §[X]; FFMP restriction tables
- **Failure definition:** days where NYC diversion restriction curtails NJ's allocation
- **Notes:** NJ's risk is expressed through restriction of NYC diversions that would otherwise reduce NJ's own stream flows. The FFMP diversion limits protect NJ's interests operationally.

### New York State (NY)
**Primary interest:** Montague flow target (Delaware tributary flows)
- **Pywr-DRB node:** `delMontague` recorder (Montague, NJ gage — USGS 01438500)
- **Metric:** Montague flow reliability = fraction of days flow ≥ Montague TFO target
- **Decree reference:** Article III — Montague flow requirement
- **Failure definition:** daily flow at Montague < Montague target
- **Notes:** Montague sits upstream of Trenton. NY State's Decree interest relates to ensuring Delaware tributaries in NY contribute adequate flows. Montague target is often met during non-drought periods; drought shortfalls are correlated with Trenton shortfalls.

---

## Regime Attribution Logic

### NYC-Limited Regime
- Condition: IERQ bank exhausted **before** LB storage falls below conservation pool
- Interpretation: NYC is the binding constraint — all remaining Trenton support must come from LB
- Pywr-DRB diagnostic: `banks.py.bank_remaining == 0` on timestep T1; `(blueMarsh.volume + beltzville.volume) > conservation_pool_threshold` on same T1

### LB-Limited Regime
- Condition: LB storage falls below conservation pool **before** or **without** IERQ exhaustion
- Interpretation: LB is the binding constraint — even if NYC could release more, LB cannot support Trenton
- Pywr-DRB diagnostic: `(blueMarsh.volume + beltzville.volume) < conservation_pool_threshold` on timestep T2; `banks.py.bank_remaining > 0` on same T2

### Co-Limited Regime
- Both constraints bind simultaneously (within lag window)
- Rarest but most severe failure mode

---

## TODO: Fill from Primary Sources
- [ ] Read Decree Articles III–IV for exact flow targets and party obligations
- [ ] Read Water Code §2.5.3 for LB MRF annual cap and activation sequencing
- [ ] Confirm Pywr-DRB node names against `pywr_drb_node_data.py`
- [ ] Verify FFMP §2.c.i: IERQ 6.09 BG/yr — confirm is the Trenton bank specifically (not total IERQ)
- [ ] Add exact MGD values for each flow target to the table above

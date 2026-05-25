# September 2004 Storm Validation Notes

## Objective
Reproduce the post-storm storage deficit mechanism in Pywr-DRB for July–December 2004.
Model should show zero Trenton contributions from LB reservoirs Oct–Dec 2004 
(already observed in `lower_basin_mrf_contributions.csv` — model needs to reproduce this).

## Observed Data Summary (from committee document)
| Reservoir | Aug Baseline | Storm-Window Peak | Post-Storm Storage |
|-----------|-------------|------------------|-------------------|
| F.E. Walter | 478 MGD | 1,540 MGD (3.2×) | — |
| Beltzville | 116 MGD | 402 MGD (3.5×) | — |
| Prompton | 53 MGD | 297 MGD (5.6×) | ~0 MG ⚠ |
| Blue Marsh | 455 MGD | 368 MGD | 5,138 MG (12% cap, Dec 6) |

**Blue Marsh key finding:** Post-storm storage (5,138 MG, Dec 6) sits just above DRBC 
drought-support staging line (~5,133 MG = 69% usable pool). At 12% total capacity, 
effectively no drought headroom.

## Validation Run Setup
```python
# Run Pywr-DRB with observed inflows for July 1 – December 31, 2004
# Use nwmv21_withObsScaled or observed streamflow as input
# Check:
#   1. Blue Marsh storage trajectory July–December 2004
#   2. Trenton MRF contributions from LB reservoirs Oct–Dec 2004 (should be ~0)
#   3. IERQ bank status during this period

import pywrdrb
model = pywrdrb.Model()
model.set_inflow("nwmv21_withObsScaled")  # or observed
model.set_timerange("2004-07-01", "2004-12-31")
# ... run and extract blue_marsh_volume, beltzville_volume, trenton_lb_contributions
```

## Gap to close
Current Pywr-DRB does NOT reproduce zero LB contributions post-storm.
Suspected cause: LB drought-stage switching not yet implemented.
Fix: implement `drought_level_agg_lb` parameter (see shared/lower_basin_ffmp_dev/).

## External Dependency (CRITICAL — CONTACT NOW)
HEC-ResSim PR-73 operational model files from USACE CENAP.
- IEPR confirmed by WEST Consultants (2012)
- Needed for: actual vs counterfactual release sequence comparison
- Contact: USACE CENAP (Philadelphia District)
- Frame as: academic collaboration supporting 2026 F.E. Walter Reevaluation Study
- Draft email in: dissertation/D2_flood_drought/validation_2004/cenap_data_request_draft.md

## Physical Defensibility Question
Committee must decide whether the mechanism is defensible before committing:
> "If the basin is wet enough to flood, it is by definition not in drought."

Counter-argument:
- The mechanism is a 90-DAY LAG effect, not a simultaneous wet/dry condition
- Late-season tropical storm (September) arrives after dry summer → LB storage already depleted
- Storm forces large flood releases → storage does not recover → drought deficit materializes by December
- Blue Marsh Dec 6 data point is the evidence: 12% capacity, sitting at the staging threshold

If committee says mechanism holds → Framing A (empirical falsification test)
If committee says "wet = not drought" critique holds → Framing B (FIRO reframe)

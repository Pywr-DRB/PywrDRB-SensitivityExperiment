# CMIP6 Dataset Reference
**Source:** Kao et al., Oak Ridge / SECURE Water Act Section 9505 Assessment v3  
**Local path:** `~/Research/CMIP6_multimodel_streamflow/`  
**Cloned:** 2026-05-25 (shallow, main branch)

---

## Naming Convention
```
<hydro_model>_RAPID_<GCM>_<SSP>_<run_id>_DBCCA_Daymet_<start>_<end>
```

| Field | Values |
|-------|--------|
| hydro_model | PRMS, VIC5 |
| GCM | ACCESS-CM2, BCC-CSM2-MR, CNRM-ESM2-1, EC-Earth3, MPI-ESM1-2-HR, MRI-ESM2-0, NorESM2-MM |
| SSP | ssp126 (historical 1980-2019), ssp245 (future), ssp370 (future) |
| date range | 1980_2019 (historical), 2020_2059 (near-future), 2060_2099 (far-future) |
| Baselines | PRMS_RAPID_Daymet2019_1980_2019, VIC5_RAPID_Daymet2019_..., PRMS_RAPID_Livneh2018_1950_2013 |

**Total folders:** 72

---

## File Status Per Folder
| File | Status |
|------|--------|
| `gage_flow_mgd.csv` | ✓ Done — all 72 folders |
| `catchment_inflow_mgd.csv` | ✓ Done — all 72 folders |
| `predicted_inflows_mgd.csv` | ✗ Missing — needs `01_prep_pywrdrb_inputs.py` |
| diversions CSVs | ✗ Missing — needs `01_prep_pywrdrb_inputs.py` |

---

## How to Generate Missing Files (cluster job)
```bash
cd ~/Research/CMIP6_multimodel_streamflow
# Activate pywrdrb env from dissertation branch
source ~/Research/Release_Policy_DRB/Pywr-DRB/venv/bin/activate  # or whatever env

# MPI run (adjust -np to available cores; 72 datasets)
mpirun -np 8 python 01_prep_pywrdrb_inputs.py
```
Requires `pywrdrb >= 2.1.0`. Dissertation branch satisfies this.

---

## D1 Scenario Selection
For Decision Scaling GCM probability weighting, use:
- **Near-future (2020-2059):** `*_ssp245_*_2020_2059` — 14 projections (7 GCMs × 2 hydro models)
- **Far-future (2060-2099):** `*_ssp245_*_2060_2099` — 14 projections (matches "by 2075" framing)
- **Historical skill weighting:** `*_ssp126_*_1980_2019` vs observed gage_flow (Daymet2019 baseline)

Note: The committee memo said "7 GCMs under SSP2-4.5" — the dataset delivers 7 GCMs × 2 hydro models = **14 projections**. Clarify with Scott whether to pool PRMS+VIC5 or treat as separate ensemble members.

---

## Trevor's Scenario Filtering Scripts
`S1_compare_historic_data.py` through `S5_plot_annual_flows.py` — Trevor's work-in-progress for scenario selection. Check with Trevor before using these; they may define the subset he intends to use in his dissertation Paper 3.

# Dissertation Repository — Marilyn Smith (ms3654)
**Cornell EWRS PhD | Reed Research Group | Delaware River Basin**  
**Created:** 2026-05-25

---

## Overview

This repository consolidates all code, analysis, and documentation for Marilyn Smith's dissertation. It is the single source of truth for dissertation-specific changes and experiment tracking.

---

## Repository Structure

```
dissertation/
├── README.md                      # This file — provenance and organization
├── IMPLEMENTATION_PLAN.md         # Week-by-week plan for all four directions
├── .gitignore
│
├── pywrdrb/                       # Dissertation-specific Pywr-DRB (tracked here)
│   ├── src/pywrdrb/               # Model source code
│   ├── pyproject.toml             # Package definition (version: 2.1.0-beta)
│   ├── experiments/               # Experiment scripts
│   ├── scripts/                   # Utility scripts
│   └── tests/                     # Test suite
│
├── cmip6/                         # CMIP6 multimodel streamflow workflow
│   ├── 01_prep_pywrdrb_inputs.py  # MPI: generate predicted inflows + diversions
│   ├── 02_run_pywrdrb_simulations.py  # MPI: run Pywr-DRB for all 72 datasets
│   ├── config.py                  # Dataset names (auto-discovers from inputs/)
│   ├── run_workflow.sh            # SLURM job script
│   ├── S1–S5 scripts              # Trevor's scenario selection (under development)
│   └── pywrdrb/
│       ├── inputs/  -> symlink    # → ~/Research/CMIP6_multimodel_streamflow/pywrdrb/inputs/
│       ├── json/                  # Generated model JSON files (gitignored)
│       └── outputs/               # Model run HDF5 outputs (gitignored)
│
├── shared/
│   ├── data/
│   │   └── cmip6_dataset_reference.md   # Dataset inventory and D1 usage guide
│   └── lower_basin_ffmp_dev/
│       └── lb_drought_stage_notes.md    # Implementation notes for LB drought stage
│
├── D1_decision_scaling/           # Decision Scaling + GCM probability weighting
├── D2_flood_drought/              # FIRO / flood-drought compound risk
├── D3_satellite_observability/    # Satellite-informed reservoir inference
└── D4_cooperative_risk/           # Cooperative risk metrics (5-party DRB)
```

---

## Provenance — What Came From Where

### `pywrdrb/` — Dissertation Pywr-DRB
Assembled from three sources on **2026-05-25**:

| Component | Source | What it adds |
|---|---|---|
| Core model | `Pywr-DRB/feature/release-policy-refactor` branch | Parametric release policies (PWL, RBF, STARFIT), perfect foresight mode, observations through April 2026 |
| NYC optimization data | `Pywr-DRB/nyc_opt` branch (Trevor Amestoy) | NYC optimization experiments, data files |
| Bug fixes | ms/dissertation | `lower_basin_ffmp.py` numpy scalar fix; `path_manager.py` PathNavigator API compatibility |

**Branch lineage:**  
`feature/release-policy-refactor` → `ms/dissertation` (cherry-picked nyc_opt files + bug fixes)

**Key dissertation additions over upstream:**
- `src/pywrdrb/release_policies/` — abstract_policy, config, PWL, RBF, STARFIT parametric
- `src/pywrdrb/parameters/parametric_release.py` — parametric release parameter class
- `src/pywrdrb/pre/generate_presimulated_releases.py` — STARFIT offline simulator
- Bug fix: `lower_basin_ffmp.py` — added `import numpy as np`; changed `float(max_allowable)` → `x = np.asarray(max_allowable).ravel(); return float(x[0])` (fixes ensemble scenario runs)
- Bug fix: `path_manager.py` — try/except for PathNavigator API version compatibility

### `cmip6/` — CMIP6 Multimodel Streamflow Scripts
Source: `https://github.com/Pywr-DRB/CMIP6_multimodel_streamflow` (Trevor Amestoy, 2026-05-25)  
Data source: Kao et al., Oak Ridge / SECURE Water Act Section 9505 Assessment v3

**Dataset:** 72 scenario folders — 7 GCMs × 2 hydro models (PRMS, VIC5) × SSPs (126/245/370) × periods (1980-2019, 2020-2059, 2060-2099)  
**Data location:** `cmip6/pywrdrb/inputs/` → symlink to `~/Research/CMIP6_multimodel_streamflow/pywrdrb/inputs/`

**Changes from source:**
- `run_workflow.sh` updated: correct SLURM resource request, full module chain (`gnu9 openmpi4 py3-mpi4py/3.0.3`), venv path → `~/dissertation/venv/`, per-job log filenames

**Input file status:**
| File | Status |
|---|---|
| `gage_flow_mgd.csv` | ✓ All 72 folders |
| `catchment_inflow_mgd.csv` | ✓ All 72 folders |
| `predicted_inflows_mgd.csv` | ✗ Generate via `01_prep_pywrdrb_inputs.py` |
| Diversion CSVs | ✗ Generate via `01_prep_pywrdrb_inputs.py` |

---

## Environment Setup

```bash
# From project root — run once
module load python/3.11.5 gnu9 openmpi4 py3-mpi4py/3.0.3
python3 -m venv --system-site-packages ~/dissertation/venv
source ~/dissertation/venv/bin/activate
pip install -e ~/dissertation/pywrdrb/
```

> `--system-site-packages` is required so the venv can see `mpi4py` from the cluster module.

---

## CMIP6 Preprocessing (generate missing input files)

```bash
# From cmip6/
cd ~/dissertation/cmip6
sbatch run_workflow.sh
```

Or interactively (8 processes):
```bash
cd ~/dissertation/cmip6
source ~/dissertation/venv/bin/activate
mpirun -n 8 python3 01_prep_pywrdrb_inputs.py
```

---

## Research Directions

| Dir | Topic | Key model dependency |
|---|---|---|
| D1 | Decision Scaling — GCM probability weighting | CMIP6 SSP245 runs, synthetic generator |
| D2 | FIRO flood-drought compound risk | Pywr-DRB + HEC-ResSim |
| D3 | Satellite-informed reservoir inference | FSM oracle, InfeRes |
| D4 | Cooperative risk metrics (5-party DRB) | Pywr-DRB RRV, LB drought stage |

**Shared blocker:** LB drought stage switching (`lower_basin_ffmp.py`) — required by D1, D4, and D2. See `shared/lower_basin_ffmp_dev/lb_drought_stage_notes.md`.

---

## Change Log

| Date | Change | Source |
|---|---|---|
| 2026-05-25 | Repository initialized | — |
| 2026-05-25 | `pywrdrb/` added from `ms/dissertation` branch | feature/release-policy-refactor + nyc_opt |
| 2026-05-25 | `cmip6/` scripts added | CMIP6_multimodel_streamflow (Trevor Amestoy) |
| 2026-05-25 | `run_workflow.sh` updated for cluster module chain | dissertation |

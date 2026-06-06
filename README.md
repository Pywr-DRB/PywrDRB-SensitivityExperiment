# Dissertation Repository — Marilyn Smith (ms3654)
**Cornell EWRS PhD | Reed Research Group | Delaware River Basin**  
**Created:** 2026-05-25

---

## Overview

This repository consolidates all code, analysis, and documentation for Marilyn Smith's dissertation. It is the single source of truth for dissertation-specific changes and experiment tracking.

---

## Repository Structure

See **[REPO_LAYOUT.md](REPO_LAYOUT.md)** for the full convention. Each research direction uses the same layout:

```
dissertation/
├── README.md, STATUS.md, IMPLEMENTATION_PLAN.md, REPO_LAYOUT.md
├── notes/                         # Cross-cutting markdown (committee, shared model notes)
├── pywrdrb/                       # Dissertation-specific Pywr-DRB package
├── cmip6/                         # CMIP6 multimodel streamflow workflow
├── shared/pywrdrb_utils/          # Cross-direction model runners + attribution
│
├── D1_decision_scaling/
│   ├── experiments/               # Runners (failure surface sweep, prewarm, …)
│   ├── lib/                       # Supporting code (performance, generator, TFO, CMIP6 weights)
│   ├── scripts/figures|analysis/  # Figure + post-hoc analysis scripts
│   ├── figures/                   # Figure outputs
│   ├── notes/                     # Workflow, briefing, traceability
│   ├── slurm/                     # SLURM submission scripts
│   └── results/                   # Experiment outputs
│
├── D2_flood_drought/              # notes/ + figures/ (growing)
├── D3_satellite_observability/
└── D4_distributed_risk/           # Same layout — Paper 1 (DRC)
    ├── experiments/               # baseline, Sobol sweep, synthetic flows, prewarm
    ├── lib/rrv_metrics/           # Five-party RRV metric functions
    ├── lib/sensitivity/           # Sobol design, config, analysis
    ├── scripts/figures/publication/  # fig_E … fig_M + run_all_figures.py
    ├── figures/publication/       # Generated PNGs
    └── notes/                     # D4_workflow.md, briefing, party mapping
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
pip install SALib pyarrow h5py   # D4 Sobol analysis + parquet I/O
```

> `--system-site-packages` is required so the venv can see `mpi4py` from the cluster module.

**Every session on the cluster** (required before `source venv/bin/activate`):

```bash
module load python/3.11.5
cd ~/dissertation && source venv/bin/activate
export PYTHONPATH=~/dissertation/shared:$PYTHONPATH
```

---

## D4 — Running the Full Experiment (End-to-End)

Paper 1 (Distributed Risk Characterization). Detailed file tree and data-flow diagram: [`D4_distributed_risk/notes/D4_workflow.md`](D4_distributed_risk/notes/D4_workflow.md).

All commands assume you are in `~/dissertation` with the session setup above. SLURM logs go to `D4_distributed_risk/logs/`.

### 0. One-time setup (fresh machine)

```bash
module load python/3.11.5 gnu9 openmpi4 py3-mpi4py/3.0.3
python3 -m venv --system-site-packages ~/dissertation/venv
source ~/dissertation/venv/bin/activate
pip install -e ~/dissertation/pywrdrb/
pip install SALib pyarrow h5py

# Amestoy 1000-member ensemble (if not present)
bash D4_distributed_risk/slurm/download_amestoy.sh
# → ~/data/amestoy_2026/
mkdir -p D4_distributed_risk/logs
```

### 1. Stage 0 — Sobol design + synthetic flows (once per sweep)

Shared synthetic flows (same for all sweeps):

```bash
python D4_distributed_risk/experiments/gen_synthetic_flows.py \
    --outdir D4_distributed_risk/results/sobol/synthetic_flows
```

Generate Saltelli sample tables (run once per sweep directory):

```bash
# Sweep 1 — k=6, 14,336 samples (early RQ2; 3 params were placeholders)
python D4_distributed_risk/lib/sensitivity/sobol_design.py \
    --outdir D4_distributed_risk/results/sobol

# Sweep 2 — k=7 (+ erq_cap_mg), 16,384 samples
python D4_distributed_risk/lib/sensitivity/sobol_design.py \
    --outdir D4_distributed_risk/results/sobol_sweep2

# Sweep 3 — k=6 all active (publication target for RQ3)
python D4_distributed_risk/lib/sensitivity/sobol_design.py \
    --outdir D4_distributed_risk/results/sobol_sweep3
```

### 2. Stage 1 — Baseline (1,000 Amestoy members → RQ1/RQ2)

```bash
sbatch D4_distributed_risk/slurm/submit_baseline.sh
# → D4_distributed_risk/results/baseline/member_*/ + rrv_summary.parquet
```

If `metrics.py` changed but HDF5 outputs already exist:

```bash
python D4_distributed_risk/experiments/reaggregate_baseline.py \
    --results-dir D4_distributed_risk/results/baseline \
    --n-workers 8
```

### 3. Stage 2 — Prewarm predicted-inflows cache (required before Sobol)

```bash
sbatch D4_distributed_risk/slurm/submit_prewarm.sh
# → results/sobol/synthetic_flows/predicted_inflows_cache/syn_r000/ … syn_r049/

# Optional gate before a large sweep:
sbatch D4_distributed_risk/slurm/submit_sobol_smoke.sh
```

Monitor: `squeue -u $USER` · `ls D4_distributed_risk/results/sobol/synthetic_flows/predicted_inflows_cache/ | wc -l` (target: 50)

### 4. Stage 3 — Sobol sweep (pick one)

| Sweep | Dir | Samples | Status (2026-06) | Use |
|-------|-----|---------|-------------------|-----|
| 1 | `results/sobol/` | 14,336 | **Complete** | Early figures; 3 params placeholders |
| 2 | `results/sobol_sweep2/` | 16,384 | **~49%** | Adds `erq_cap_mg` |
| 3 | `results/sobol_sweep3/` | 14,336 | **Not started** | All 6 params active — **publication RQ3** |

**Sweep 1** (rerun):

```bash
bash D4_distributed_risk/slurm/batch_submit_sobol.sh
```

**Sweep 2** (finish remainder):

```bash
# Resubmit failed offset 8000, then 9000–16000
sbatch --array=0-999%10 --export=ALL,BATCH_OFFSET=8000 \
  D4_distributed_risk/slurm/submit_sobol_sweep2.sh
bash D4_distributed_risk/slurm/submit_sweep2_remaining.sh

# Or submit all remaining batches:
bash D4_distributed_risk/slurm/batch_submit_sobol_sweep2.sh
```

**Sweep 3** (recommended from here):

```bash
# Preflight + optimized launch (16 concurrent tasks/array, all 15 batches)
bash D4_distributed_risk/slurm/launch_sweep3.sh --smoke-only   # optional ~10 min gate
sbatch D4_distributed_risk/slurm/submit_launch_sweep3.sh       # recommended — detach-safe
# bash D4_distributed_risk/slurm/launch_sweep3.sh              # interactive alternative

# Manual equivalent:
SOBOL_CONCURRENT=16 \
SOBOL_SCRIPT=~/dissertation/D4_distributed_risk/slurm/submit_sobol_sweep3.sh \
SOBOL_TOTAL=14336 \
bash D4_distributed_risk/slurm/batch_submit_sobol.sh
```

> **Speed notes:** Sweep 3 reuses `results/sobol/synthetic_flows/` (50 parquets + 50 prewarm caches — already complete). Each SLURM task uses 50 workers for 50 realizations (~1.5 min/task median). Hopper nodes have 80 CPUs → `SOBOL_CONCURRENT=16` uses ~16 nodes in parallel; all 15 batch jobs are submitted at once and the scheduler queues excess.

Monitor progress:

```bash
squeue -u $USER
ls D4_distributed_risk/results/sobol_sweep3/task_outputs/task_*.csv | wc -l   # target: 14336
```

### 5. Stage 4 — Post-processing

Point `--task-dir` / `--outdir` at the sweep you finished (`sobol`, `sobol_sweep2`, or `sobol_sweep3`).

**Sobol indices** (RQ2; figures K–M):

```bash
python D4_distributed_risk/lib/sensitivity/sobol_analysis.py \
    --task-dir D4_distributed_risk/results/sobol_sweep3/task_outputs \
    --design   D4_distributed_risk/results/sobol_sweep3/sobol_design.json \
    --outdir   D4_distributed_risk/results/sobol_sweep3
```

**RQ3 tradeoff analysis:**

```bash
python D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py \
    --task-dir  D4_distributed_risk/results/sobol_sweep3/task_outputs \
    --sobol-dir D4_distributed_risk/results/sobol_sweep3 \
    --baseline  D4_distributed_risk/results/baseline/rrv_summary.csv \
    --outdir    D4_distributed_risk/results/rq3
```

**Optional experiment manifest:**

```bash
python D4_distributed_risk/experiments/gen_experiment_manifest.py
```

### 6. Stage 5 — Publication figures

```bash
python D4_distributed_risk/scripts/figures/publication/run_opening_figures.py   # A–D
python D4_distributed_risk/scripts/figures/publication/run_all_figures.py       # E–M
```

Outputs: `D4_distributed_risk/figures/publication/`

### Minimal path from current state to done

Baseline, synthetic flows, prewarm, and sweep 1 are already complete. To run the **full publication pipeline**:

```bash
module load python/3.11.5 && cd ~/dissertation && source venv/bin/activate
export PYTHONPATH=~/dissertation/shared:$PYTHONPATH

# 1. Sweep 3 design
python D4_distributed_risk/lib/sensitivity/sobol_design.py \
    --outdir D4_distributed_risk/results/sobol_sweep3

# 2. Submit sweep 3 (~1–2 days on cluster)
SOBOL_SCRIPT=~/dissertation/D4_distributed_risk/slurm/submit_sobol_sweep3.sh \
SOBOL_TOTAL=14336 \
bash D4_distributed_risk/slurm/batch_submit_sobol.sh

# 3. After all 14,336 task CSVs exist
python D4_distributed_risk/lib/sensitivity/sobol_analysis.py \
    --task-dir D4_distributed_risk/results/sobol_sweep3/task_outputs \
    --design   D4_distributed_risk/results/sobol_sweep3/sobol_design.json \
    --outdir   D4_distributed_risk/results/sobol_sweep3

python D4_distributed_risk/scripts/analysis/rq3_institutional_tradeoff.py \
    --task-dir  D4_distributed_risk/results/sobol_sweep3/task_outputs \
    --sobol-dir D4_distributed_risk/results/sobol_sweep3 \
    --baseline  D4_distributed_risk/results/baseline/rrv_summary.csv \
    --outdir    D4_distributed_risk/results/rq3

python D4_distributed_risk/scripts/figures/publication/run_all_figures.py
python D4_distributed_risk/scripts/figures/publication/run_opening_figures.py
```

To finish **sweep 2** instead, use the sweep 2 submit commands in Stage 4 and point analysis at `results/sobol_sweep2/`.

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
| D1 | Decision Scaling — GCM probability weighting | CMIP6 SSP245 runs, Kirsch-Nowak generator |
| D2 | FIRO flood-drought compound risk | Pywr-DRB + HEC-ResSim |
| D3 | Satellite-informed reservoir inference | FSM oracle, InfeRes |
| D4 | Distributed risk characterization (DRC) — 5-party DRB | Pywr-DRB RRV, LB drought stage — see **[D4 end-to-end walkthrough](#d4--running-the-full-experiment-end-to-end)** |

**Shared blocker:** LB drought stage switching (`lower_basin_ffmp.py`) — required by D1, D4, and D2. See `shared/lower_basin_ffmp_dev/lb_drought_stage_notes.md`.

---

## PywrDRB Organization — CMIP6 Integration Map

Surveyed 2026-05-25 across all 16 Pywr-DRB GitHub repos:

| Repo | CMIP6 dataset | How it's used |
|---|---|---|
| `CMIP6_multimodel_streamflow` | Kao et al. 10.13139/OLCF/2318650 | Bias-corrected streamflow at DRB nodes (PRMS + VIC5) — **D1/D4 source** |
| `CMIP6_multimodel_hydroclimate` | Kao et al. 10.13139/OLCF/2311812 | Raw gridded climate (precip/temp) aggregated to 33 watershed nodes — upstream of streamflow repo |
| `StochasticExploratoryExperiment` | CMIP6 PRMS 2020-2059 monthly shifts | 3 discrete climate scenarios fed into Kirsch-Nowak generator — **D1 infrastructure template** |
| All others | None | Use historical NHMv10 / WRF flows only |

### D1 CMIP6 role — Step 3 only (probability weighting, not generator input)

```
Step 1+2: Build failure surface
    Streamflow generator (Kirsch or Gosney — pending Scott)
        → synthetic DRB daily flows at prescribed percentile
    + SLR level → DRBC 2025-6 TFO → Pywr-DRB parameter
    + LB contribution volume → institutional cap → Pywr-DRB parameter
    → Pywr-DRB v2 run (daily, FFMP drought stages, IERQ banking)
    → pass/fail per cell (Trenton reliability × shortfall severity × LB depletion)

Step 3: GCM probability weighting (CMIP6 enters here)
    CMIP6 gage_flow_mgd.csv (SSP245, 2020-2059) × 14 projections
        → extract streamflow statistic per projection
        → map to cell on failure surface streamflow axis
        → count projections per cell → probability weight
    → "X% of CMIP6 projections place DRB in failure region by 2075"
```

**SEE (`stochastic_experiment/`) is reference-only** — Trevor Amestoy's separate paper. D1's experiment design is distinct: 3-axis failure surface (streamflow × SLR × LB volume), daily Pywr-DRB with FFMP drought stage switching, and NYC IERQ vs LB storage attribution. See `D1_decision_scaling/README.md`.

---

## Change Log

| Date | Change | Source |
|---|---|---|
| 2026-05-25 | Repository initialized | — |
| 2026-05-25 | `pywrdrb/` added from `ms/dissertation` branch | feature/release-policy-refactor + nyc_opt |
| 2026-05-25 | `cmip6/` scripts added | CMIP6_multimodel_streamflow (Trevor Amestoy) |
| 2026-05-25 | `run_workflow.sh` updated: full module chain, dissertation venv path | dissertation |
| 2026-05-25 | Bug fix: `pywrdrb/pre/extrapolate_nyc_nj_diversions.py:659` — `df_long_m["nn"] = pd.NaT` (was `-1`); newer pandas rejects Timestamp assignment into int64 column | dissertation |
| 2026-05-25 | Bug fix: venv mpi4py — pip-installed against system OpenMPI (py3-mpi4py module is Python 3.6 only) | dissertation |
| 2026-05-25 | `D1_decision_scaling/stochastic_experiment/` added from StochasticExploratoryExperiment | Trevor Amestoy |
| 2026-05-25 | CMIP6 preprocessing complete: diversions + predicted inflows generated for all 72 datasets (SLURM jobs 245198, 245199) | dissertation |
| 2026-06-05 | D4 end-to-end experiment walkthrough added to README; repo reorganized under `experiments/`, `lib/`, `scripts/` | dissertation |

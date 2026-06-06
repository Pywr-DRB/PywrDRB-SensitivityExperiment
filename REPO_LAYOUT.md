# Dissertation Repository Layout

Every research direction (`D1`–`D4`) follows the same folder convention so scripts are easy to find.

```
{Dx}/
├── experiments/          # Entry points that launch runs (SLURM-facing)
├── lib/                  # Supporting Python modules imported by experiments
├── scripts/
│   ├── figures/          # Figure-generation scripts
│   └── analysis/         # Post-hoc analysis scripts
├── figures/              # Figure outputs only (PNG, HTML, validation JSON)
├── notes/                # Markdown docs, briefings, workflow guides
├── slurm/                # SLURM submission scripts
└── results/              # Experiment outputs (parquet, HDF5, CSV)
```

Repo-wide shared code stays in `shared/` (`pywrdrb_utils/`, model validation).  
Cross-cutting markdown lives in `notes/` at the repo root (`committee/`, `shared/`).

---

## D4 — Distributed Risk Characterization

| What | Where |
|------|-------|
| Run baseline ensemble | `experiments/run_d4_baseline.py` |
| Sobol sweep (one Saltelli sample) | `experiments/run_sobol_sweep.py` |
| Generate synthetic flows | `experiments/gen_synthetic_flows.py` |
| Prewarm predicted inflows | `experiments/prewarm_predicted_inflows.py` |
| RRV metric functions | `lib/rrv_metrics/metrics.py` |
| Sobol design + analysis | `lib/sensitivity/` |
| Publication figures | `scripts/figures/publication/` |
| Opening figures A–D | `fig_A_*` … `fig_D_*` · `run_opening_figures.py` |
| DRB spatial assets | `scripts/figures/DRB_spatial/` |
| Figure PNGs | `figures/publication/` |
| RQ3 analysis | `scripts/analysis/` |
| Workflow + briefing | `notes/` |

**Common commands**

```bash
cd ~/dissertation
source venv/bin/activate

# Regenerate all publication figures
python D4_distributed_risk/scripts/figures/publication/run_all_figures.py

# Submit Sobol array (after prerequisites in slurm script header)
sbatch D4_distributed_risk/slurm/submit_sobol.sh
```

---

## D1 — Decision Scaling

| What | Where |
|------|-------|
| Failure surface sweep | `experiments/run_failure_surface_sweep.py` |
| Performance criteria | `lib/performance/criteria.py` |
| Kirsch flow generator | `lib/generator/kirsch_generate.py` |
| TFO / SLR lookup | `lib/tfo_schedule/` |
| CMIP6 cell weights | `lib/scenario_extraction/` |
| Synthetic flow data | `generator/synthetic_flows/` *(data, not code)* |
| RQ analysis | `scripts/analysis/` |
| Workflow + briefing | `notes/` |

---

## D2 / D3

Smaller footprints — `notes/` for markdown; code will follow the same `experiments/`, `lib/`, `scripts/` pattern as it grows.

---

## Unchanged top-level

| Path | Purpose |
|------|---------|
| `pywrdrb/` | Pywr-DRB model package |
| `cmip6/` | CMIP6 multimodel workflow (legacy flat layout) |
| `shared/pywrdrb_utils/` | Cross-direction model runners, attribution, Kirsch flows |
| `notes/committee/` | Committee experimental plans |
| `notes/shared/` | Model implementation notes (LB drought, ERQ, CMIP6 reference) |

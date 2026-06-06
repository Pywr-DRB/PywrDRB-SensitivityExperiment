# D1 — Decision Scaling Under SLR

## Research Questions

**Core:** Across a joint space of streamflow variability and externally driven flow target increases, where is the boundary of acceptable system performance — and within the failure region, which institutional subsystem binds first?

**RQ1:** Across the joint space of streamflow variability and flow target level, where is the boundary of acceptable performance — and how does that boundary shift as the target level increases?

**RQ2:** Within the failure region, what fraction of failures are attributable to upstream diversion-side exhaustion versus downstream storage-side depletion — and does attribution shift across the scenario space?

**RQ3:** How does the probability mass of the GCM-plausible ensemble falling within the failure region change as the flow target level increases — and at what target level does a majority of plausible futures fall inside the failure boundary?

---

## Documentation

| Document | Purpose |
|----------|---------|
| [`notes/briefing/D1_stage1_implementation_briefing.md`](notes/briefing/D1_stage1_implementation_briefing.md) | Committee walkthrough |
| [`notes/D1_workflow.md`](notes/D1_workflow.md) | End-to-end commands |
| [`notes/briefing/traceability_matrix.csv`](notes/briefing/traceability_matrix.csv) | Threshold / parameter audit |

---

## Three-step experiment

1. **Failure surface** — Pywr-DRB across 126 cells (7 streamflow × 6 SLR/TFO × 3 LB cap)
2. **Performance criteria** — Trenton reliability, severity, LB storage, salinity Mode A (`lib/performance/criteria.py`)
3. **CMIP6 overlay** — Probability weight per streamflow bin (`lib/scenario_extraction/`)

---

## Implementation status

| Component | Status |
|-----------|--------|
| CMIP6 data + cell weights | ✓ |
| FFMP LB drought + NJ coupling | ✓ (2026-05-28) |
| ERQ banking | ✓ |
| TFO schedule (DRBC Dec 2025) | ✓ provisional (`lib/tfo_schedule/tfo_slr_table.csv`) |
| Kirsch-Nowak generator | ✓ (`shared/pywrdrb_utils/kirsch_flows.py`) |
| Failure surface sweep | ✓ scaffold + SLURM |
| `lb_cap_multiplier` injection | ✓ |
| CMIP6 dual metric (NYC + Montague) | ✓ |
| Salinity Mode A (SalinityLSTM + SLR bias) | ✓ requires `PYWRDRB_ML_PLUGIN_PATH` |

**Salinity (PywrDRB-ML):** Clone once (HTTPS if SSH keys unavailable):

```bash
git clone https://github.com/Pywr-DRB/PywrDRB-ML.git \
  D1_decision_scaling/stochastic_experiment/PywrDRB-ML
```

SLURM scripts default `PYWRDRB_ML_PLUGIN_PATH` to that path. Use `--no-salinity` to skip.

**Open (Scott):** Generator formal choice (Kirsch working default), performance thresholds, 30 vs 10 realizations/cell.

---

## Folder structure

```
D1_decision_scaling/
├── notes/                       # Workflow, briefing, traceability
├── experiments/                 # Runners (sweep, prewarm, aggregate, smoke)
│   └── config.py                # 3-axis grid (single source of truth)
├── lib/
│   ├── performance/criteria.py
│   ├── generator/               # kirsch_generate.py, validate_generator.py
│   ├── tfo_schedule/            # tfo_slr_table.csv, lookup helpers
│   └── scenario_extraction/     # CMIP6 cell weights
├── generator/synthetic_flows/     # Generated flow data (not code)
├── scripts/analysis/            # RQ1–RQ3 post-processing
├── slurm/
└── stochastic_experiment/       # Reference only — SEE
```

---

## Separation from SEE

SEE (`stochastic_experiment/`) maps drought event frequency. D1 maps a structured failure surface with IERQ vs LB attribution. Read-only reference — do not base D1 on SEE code.

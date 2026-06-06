#!/bin/bash
# Launch Sobol sweep 3 with preflight checks and tuned cluster settings.
#
# Usage (from login node):
#   cd ~/dissertation
#   sbatch D4_distributed_risk/slurm/submit_launch_sweep3.sh     # recommended — detach-safe
#   bash D4_distributed_risk/slurm/launch_sweep3.sh              # interactive (keep terminal open)
#   bash D4_distributed_risk/slurm/launch_sweep3.sh --smoke-only # SLURM smoke test only
#   bash D4_distributed_risk/slurm/launch_sweep3.sh --dry-run
#
# Resume missing batches only (if a prior launch was interrupted):
#   BATCH_START=9 BATCH_END=14 sbatch D4_distributed_risk/slurm/submit_launch_sweep3.sh
#
# Tunables (env vars):
#   SOBOL_CONCURRENT=16   tasks running at once per batch job (%N throttle)
#                         Hopper nodes: 80 CPUs, 191 GB. Each task uses 50 CPUs / 64 GB
#                         → ~1 task/node; 15 idle nodes ≈ 15–20 effective concurrent tasks
#   SOBOL_TOTAL=14336     total Saltelli samples (default for sweep 3)

set -euo pipefail

DISSERTATION_ROOT="${DISSERTATION_ROOT:-$HOME/dissertation}"
cd "$DISSERTATION_ROOT"

SOBOL_CONCURRENT="${SOBOL_CONCURRENT:-16}"
SOBOL_TOTAL="${SOBOL_TOTAL:-14336}"
SYN_FLOWS="D4_distributed_risk/results/sobol/synthetic_flows"
SWEEP3="D4_distributed_risk/results/sobol_sweep3"
TASK_DIR="$SWEEP3/task_outputs"
SMOKE_ONLY=0
DRY_RUN=0

for arg in "$@"; do
    case "$arg" in
        --smoke-only) SMOKE_ONLY=1 ;;
        --dry-run)    DRY_RUN=1 ;;
        *) echo "Unknown arg: $arg"; exit 1 ;;
    esac
done

echo "═══════════════════════════════════════════════════════════════"
echo "  D4 Sweep 3 launch — preflight"
echo "═══════════════════════════════════════════════════════════════"

# ── 1. Design files ──
for f in "$SWEEP3/sobol_samples.csv" "$SWEEP3/sobol_design.json"; do
    if [[ ! -f "$f" ]]; then
        echo "MISSING: $f"
        echo "Run: python D4_distributed_risk/lib/sensitivity/sobol_design.py --outdir $SWEEP3"
        exit 1
    fi
    echo "  OK  $f"
done

# ── 2. Synthetic flows + prewarm cache (shared with sweep 1 — do NOT use sweep3/synthetic_flows) ──
N_PARQUETS=$(ls "$SYN_FLOWS"/realization_*.parquet 2>/dev/null | wc -l)
N_CACHE=$(find "$SYN_FLOWS/predicted_inflows_cache" -mindepth 1 -maxdepth 1 -type d -name 'syn_r*' 2>/dev/null | wc -l)
echo "  OK  $N_PARQUETS synthetic flow parquets in $SYN_FLOWS"
echo "  OK  $N_CACHE/50 predicted_inflows caches"

if (( N_PARQUETS < 50 )); then
    echo "FAIL: need 50 parquets — run gen_synthetic_flows.py"
    exit 1
fi
if (( N_CACHE < 50 )); then
    echo "FAIL: prewarm incomplete — run: sbatch D4_distributed_risk/slurm/submit_prewarm.sh"
    exit 1
fi

# ── 3. Worker script path ──
WORKER="D4_distributed_risk/slurm/submit_sobol_sweep3.sh"
if ! grep -q "experiments/run_sobol_sweep.py" "$WORKER"; then
    echo "FAIL: $WORKER must call experiments/run_sobol_sweep.py"
    exit 1
fi
echo "  OK  $WORKER → experiments/run_sobol_sweep.py"

# ── 4. Incomplete task CSVs (partial runs are redone automatically) ──
module load python/3.11.5 2>/dev/null || true
source ~/dissertation/venv/bin/activate 2>/dev/null || true
INCOMPLETE=$(python3 << 'PY'
import pandas as pd
from pathlib import Path
task_dir = Path("D4_distributed_risk/results/sobol_sweep3/task_outputs")
bad = []
for p in sorted(task_dir.glob("task_*.csv")):
    try:
        df = pd.read_csv(p)
        n_ok = (df["status"] == "ok").sum() if "status" in df.columns else 0
        if n_ok < 50:
            bad.append(p.name)
    except Exception:
        bad.append(p.name)
print("\n".join(bad))
PY
)
if [[ -n "$INCOMPLETE" ]]; then
    echo "  WARN incomplete task CSVs (will be re-run automatically):"
    echo "$INCOMPLETE" | sed 's/^/       /'
fi

# ── 5. Progress + ETA ──
N_DONE=$(ls "$TASK_DIR"/task_*.csv 2>/dev/null | wc -l)
N_REMAIN=$(( SOBOL_TOTAL - N_DONE ))
# Empirical from sweep 2: median ~1.4 min/task, mean ~3.2 min at CONCURRENT=10
MED_MIN=1.4
HOURS_LO=$(python3 -c "print(f'{$N_REMAIN / $SOBOL_CONCURRENT * $MED_MIN / 60:.1f}')")
HOURS_HI=$(python3 -c "print(f'{$N_REMAIN / $SOBOL_CONCURRENT * 3.2 / 60:.1f}')")

echo ""
echo "  Completed:   $N_DONE / $SOBOL_TOTAL"
echo "  Remaining:   $N_REMAIN"
echo "  Concurrent:  $SOBOL_CONCURRENT tasks/array (%N per batch job)"
echo "  ETA (rough): ${HOURS_LO}–${HOURS_HI} h wall time (15 batches submitted in parallel)"
echo ""

if (( SMOKE_ONLY )); then
    echo "Submitting SLURM smoke test (sample 1, 50 realizations) ..."
    if (( DRY_RUN )); then
        echo "[DRY] sbatch D4_distributed_risk/slurm/submit_sobol_sweep3_smoke.sh"
    else
        sbatch D4_distributed_risk/slurm/submit_sobol_sweep3_smoke.sh
        echo "Monitor:  tail -f D4_distributed_risk/logs/d4_sobol3_test_*.out"
        echo "Then run: bash D4_distributed_risk/slurm/launch_sweep3.sh"
    fi
    exit 0
fi

echo "═══════════════════════════════════════════════════════════════"
echo "  Submitting $SOBOL_TOTAL tasks in 15 batches"
echo "═══════════════════════════════════════════════════════════════"

export SOBOL_SCRIPT="$DISSERTATION_ROOT/D4_distributed_risk/slurm/submit_sobol_sweep3.sh"
export SOBOL_TOTAL
export SOBOL_CONCURRENT
export BATCH_START="${BATCH_START:-0}"
export BATCH_END="${BATCH_END:-14}"

if (( DRY_RUN )); then
    bash D4_distributed_risk/slurm/batch_submit_sobol.sh --dry-run
else
    bash D4_distributed_risk/slurm/batch_submit_sobol.sh
fi

echo ""
echo "Monitor:"
echo "  squeue -u \$USER | grep d4_sobol"
echo "  watch -n 120 'ls $TASK_DIR/task_*.csv | wc -l'"
echo ""
echo "When complete (target: $SOBOL_TOTAL):"
echo "  python D4_distributed_risk/lib/sensitivity/sobol_analysis.py \\"
echo "    --task-dir $TASK_DIR \\"
echo "    --design   $SWEEP3/sobol_design.json \\"
echo "    --outdir   $SWEEP3"

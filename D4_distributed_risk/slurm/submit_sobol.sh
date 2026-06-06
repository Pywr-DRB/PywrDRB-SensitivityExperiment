#!/bin/bash
#SBATCH --job-name=d4_sobol
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol_%A_%a.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol_%A_%a.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --partition=normal
#
# D4 Sobol sensitivity sweep — one SLURM task per Saltelli sample.
# Total: 14,336 tasks × SOBOL_ENSEMBLE_SUBSET=50 Kirsch-Nowak realizations,
# run in parallel (50 workers per task).
#
# IMPORTANT: MaxArraySize=1001 on this cluster. Do NOT submit --array=0-14335 directly.
# Use batch_submit_sobol.sh to split into 15 batches of ≤1000 tasks:
#
#   bash D4_distributed_risk/slurm/batch_submit_sobol.sh
#
# Each task:
#   - Reads row BATCH_OFFSET+SLURM_ARRAY_TASK_ID from sobol_samples.csv
#   - Runs Pywr-DRB for all 50 synthetic realizations in parallel (50 processes)
#   - predicted_inflows_mgd.csv must be pre-cached (run submit_prewarm.sh first)
#   - Writes per-party RRV metrics to results/sobol/task_outputs/task_{SAMPLE_ID:05d}.csv
#
# Prerequisites:
#   1. python sensitivity/sobol_design.py          (sobol_samples.csv)
#   2. python sensitivity/gen_synthetic_flows.py   (50 × 79-year parquets)
#   3. sbatch slurm/submit_prewarm.sh              (predicted_inflows cache)
#   4. Baseline run complete (submit_baseline.sh finished)

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"

export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

# BATCH_OFFSET is set by the calling script (batch_submit_sobol.sh) via --export.
# Default 0 allows direct invocation for testing (covers samples 0-999).
BATCH_OFFSET=${BATCH_OFFSET:-0}
TASK_ID=${SLURM_ARRAY_TASK_ID}
SAMPLE_ID=$(( BATCH_OFFSET + TASK_ID ))

echo "Array task $TASK_ID | Batch offset $BATCH_OFFSET | Sample ID $SAMPLE_ID"

python D4_distributed_risk/experiments/run_sobol_sweep.py \
    --sample-id     "$SAMPLE_ID" \
    --samples-csv   D4_distributed_risk/results/sobol/sobol_samples.csv \
    --syn-flows-dir D4_distributed_risk/results/sobol/synthetic_flows \
    --outdir        D4_distributed_risk/results/sobol/task_outputs \
    --n-workers     "$SLURM_CPUS_PER_TASK" \
    --log-level     INFO

echo "Sample $SAMPLE_ID complete"

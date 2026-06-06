#!/bin/bash
#SBATCH --job-name=d1_fs_lb1
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_fs_lb1_%A_%a.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_fs_lb1_%A_%a.err
#SBATCH --array=0-41
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --partition=normal

# 42-cell LB1 pilot: 7 flow bins × 6 SLR levels × LB1 only
# Requires prewarm — fails fast if cache incomplete (see submit_d1_fast_pipeline.sh)

set -euo pipefail
module load python/3.11.5
source ~/dissertation/venv/bin/activate
PYTHON="${PYTHON:-$HOME/dissertation/venv/bin/python}"

DISSERTATION_ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

export PYWRDRB_ML_PLUGIN_PATH="${PYWRDRB_ML_PLUGIN_PATH:-$DISSERTATION_ROOT/D1_decision_scaling/stochastic_experiment/PywrDRB-ML}"

REALIZATIONS_CHECK="${D1_REALIZATIONS:-30}"
"$PYTHON" D1_decision_scaling/experiments/check_d1_ready.py --realizations "$REALIZATIONS_CHECK" \
  || { echo "Aborting: run prewarm first (sbatch slurm/submit_prewarm_d1.sh)" >&2; exit 1; }

# Speed (sbatch --export=ALL,D1_REALIZATIONS=10):
#   D1_REALIZATIONS=10     fewer samples per cell
#   D1_POSTHOC=0           inline SalinityLSTM in Pywr-DRB (slower)
SWEEP_CMD=(
  "$PYTHON" D1_decision_scaling/experiments/run_failure_surface_sweep.py
  --cell-index "$SLURM_ARRAY_TASK_ID"
  --lb-level LB1
)
if [ "${D1_POSTHOC:-1}" != "0" ]; then
  SWEEP_CMD+=(--posthoc-salinity --flow-prediction-mode regression_disagg)
fi
if [ -n "${D1_REALIZATIONS:-}" ]; then
  SWEEP_CMD+=(--realizations "$D1_REALIZATIONS")
fi
"${SWEEP_CMD[@]}"

echo "LB1 pilot cell $SLURM_ARRAY_TASK_ID complete"

#!/bin/bash
#SBATCH --job-name=d1_failure_surface
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_fs_%A_%a.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_fs_%A_%a.err
#SBATCH --array=0-125
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --partition=normal

set -euo pipefail
module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

export PYWRDRB_ML_PLUGIN_PATH="${PYWRDRB_ML_PLUGIN_PATH:-$DISSERTATION_ROOT/D1_decision_scaling/stochastic_experiment/PywrDRB-ML}"

REALIZATIONS_CHECK="${D1_REALIZATIONS:-30}"
python D1_decision_scaling/experiments/check_d1_ready.py --realizations "$REALIZATIONS_CHECK" \
  || { echo "Aborting: run prewarm first" >&2; exit 1; }

SWEEP_CMD=(
  python D1_decision_scaling/experiments/run_failure_surface_sweep.py
  --cell-index "$SLURM_ARRAY_TASK_ID"
  --posthoc-salinity
  --flow-prediction-mode gage_flow
)
if [ -n "${D1_REALIZATIONS:-}" ]; then
  SWEEP_CMD+=(--realizations "$D1_REALIZATIONS")
fi
"${SWEEP_CMD[@]}"

echo "Cell $SLURM_ARRAY_TASK_ID complete"
# After array completes: python D1_decision_scaling/experiments/aggregate_results.py

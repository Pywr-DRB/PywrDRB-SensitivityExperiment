#!/bin/bash
#SBATCH --job-name=d4_prewarm
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_prewarm_%A_%a.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_prewarm_%A_%a.err
#SBATCH --array=0-49                    # one task per synthetic realization
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=01:00:00                 # PredictedInflowPreprocessor takes ~20 min/realization
#SBATCH --partition=normal

# D4 pre-warm: generate predicted_inflows_mgd.csv for each Kirsch-Nowak realization.
# Run ONCE before submitting submit_sobol.sh to avoid ~20 min overhead per realization
# in the Sobol SLURM array (14,336 tasks, one per Saltelli sample).
#
# After this completes:
#   results/sobol_sweep3/synthetic_flows/predicted_inflows_cache/
#     syn_r000/predicted_inflows_mgd.csv  ... syn_r049/predicted_inflows_mgd.csv

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"

export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

python D4_distributed_risk/experiments/prewarm_predicted_inflows.py \
    --syn-flows-dir D4_distributed_risk/results/sobol_sweep3/synthetic_flows \
    --realization-id "$SLURM_ARRAY_TASK_ID" \
    --log-level INFO

echo "Realization $SLURM_ARRAY_TASK_ID pre-warm complete"

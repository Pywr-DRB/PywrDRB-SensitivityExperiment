#!/bin/bash
#SBATCH --job-name=d1_prewarm
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_prewarm_%j.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_prewarm_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=24:00:00
#SBATCH --partition=normal

# One-time: cache predicted_inflows for 7 bins × 30 realizations (210 files).
# Run before failure-surface sweep for ~10–20× faster first Pywr-DRB pass per run.

set -euo pipefail
module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"
mkdir -p D1_decision_scaling/slurm/logs

python D1_decision_scaling/experiments/prewarm_predicted_inflows.py --workers 8

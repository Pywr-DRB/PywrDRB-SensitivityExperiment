#!/bin/bash
#SBATCH --job-name=d4_sweep3_launch
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sweep3_launch_%j.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sweep3_launch_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:30:00
#SBATCH --partition=normal
#
# Coordinator: runs preflight + submits all 15 sweep-3 array batches via sbatch.
# Detach-safe — you can close the terminal after submitting THIS job.
#
# Usage:
#   cd ~/dissertation
#   sbatch D4_distributed_risk/slurm/submit_launch_sweep3.sh
#
# Resume only missing batches (e.g. interactive launch stopped at batch 9):
#   BATCH_START=9 sbatch D4_distributed_risk/slurm/submit_launch_sweep3.sh
#
# Tunables (pass via --export):
#   sbatch --export=ALL,SOBOL_CONCURRENT=16,BATCH_START=0 \
#     D4_distributed_risk/slurm/submit_launch_sweep3.sh

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"

export SOBOL_CONCURRENT="${SOBOL_CONCURRENT:-16}"
export SOBOL_TOTAL="${SOBOL_TOTAL:-14336}"
export BATCH_START="${BATCH_START:-0}"
export BATCH_END="${BATCH_END:-14}"

echo "Sweep 3 launch coordinator started at $(date)"
echo "  SOBOL_CONCURRENT=$SOBOL_CONCURRENT"
echo "  BATCH_START=$BATCH_START  BATCH_END=$BATCH_END"

bash D4_distributed_risk/slurm/launch_sweep3.sh

echo "Coordinator finished at $(date)"

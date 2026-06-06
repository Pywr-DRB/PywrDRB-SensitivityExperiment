#!/bin/bash
#SBATCH --job-name=d4_baseline
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_baseline_%j.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_baseline_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=100
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --partition=normal

# D4 baseline ensemble run — 1000 Amestoy members, 100 parallel cores.
# Estimated wall time: ~40 min (1000 runs × 4 min / 100 cores).
#
# Prerequisites:
#   1. Amestoy 1000-member ensemble downloaded to $AMESTOY_PATH
#   2. pywrdrb installed in dissertation venv
#   3. LB drought stage switching implemented (done 2026-05-28)
#   4. NJ diversion coupling implemented (done 2026-05-28)
#
# Output: D4_distributed_risk/results/baseline/  — one CSV per member + summary DataFrame

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"

# TODO: set Amestoy ensemble path after Zenodo download
AMESTOY_PATH="${AMESTOY_PATH:-$HOME/data/amestoy_2026}"

if [[ ! -d "$AMESTOY_PATH" ]]; then
    echo "ERROR: Amestoy ensemble not found at $AMESTOY_PATH"
    echo "Download from Zenodo first: see D4_distributed_risk/README.md"
    exit 1
fi

export AMESTOY_PATH
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

python D4_distributed_risk/experiments/run_d4_baseline.py \
    --mode rerun \
    --ensemble-path "$AMESTOY_PATH" \
    --outdir D4_distributed_risk/results/baseline \
    --n-workers "$SLURM_CPUS_PER_TASK"

echo "D4 baseline complete — results in D4_distributed_risk/results/baseline/"

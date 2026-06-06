#!/bin/bash
#SBATCH --job-name=d4_sobol_test
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol_test_%j.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol_test_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH --partition=normal
#
# Gate before batch_submit_sobol.sh: sample 0, 2 realizations, 2 workers.
# Expect task_00000.csv with 2 ok rows in ~25–40 min (pre-warmed caches).

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

rm -f D4_distributed_risk/results/sobol/task_outputs/task_00000.csv

python D4_distributed_risk/experiments/run_sobol_sweep.py \
    --sample-id       0 \
    --n-realizations  2 \
    --n-workers       2 \
    --samples-csv     D4_distributed_risk/results/sobol/sobol_samples.csv \
    --syn-flows-dir   D4_distributed_risk/results/sobol/synthetic_flows \
    --outdir          D4_distributed_risk/results/sobol/task_outputs \
    --log-level       INFO

echo "Smoke OK: $(wc -l < D4_distributed_risk/results/sobol/task_outputs/task_00000.csv) lines in task_00000.csv"

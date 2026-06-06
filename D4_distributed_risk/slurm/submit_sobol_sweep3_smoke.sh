#!/bin/bash
#SBATCH --job-name=d4_sobol3_test
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol3_test_%j.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D4_distributed_risk/logs/d4_sobol3_test_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=50
#SBATCH --mem=64G
#SBATCH --time=02:00:00
#SBATCH --partition=normal
#
# Gate before launch_sweep3.sh: sample 1, all 50 realizations, sweep 3 params.
# Expect ~1–3 min wall time with pre-warmed predicted_inflows cache.

set -euo pipefail

module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=~/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

rm -f D4_distributed_risk/results/sobol_sweep3/task_outputs/task_00001.csv

python D4_distributed_risk/experiments/run_sobol_sweep.py \
    --sample-id       1 \
    --samples-csv     D4_distributed_risk/results/sobol_sweep3/sobol_samples.csv \
    --syn-flows-dir   D4_distributed_risk/results/sobol/synthetic_flows \
    --outdir          D4_distributed_risk/results/sobol_sweep3/task_outputs \
    --n-workers       "$SLURM_CPUS_PER_TASK" \
    --log-level       INFO

N=$(($(wc -l < D4_distributed_risk/results/sobol_sweep3/task_outputs/task_00001.csv) - 1))
echo "Sweep 3 smoke OK: ${N}/50 realization rows in task_00001.csv"
test "$N" -ge 50

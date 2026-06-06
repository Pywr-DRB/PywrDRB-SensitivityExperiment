#!/bin/bash
#SBATCH --job-name=d1_gen_bins
#SBATCH --output=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_gen_%A_%a.out
#SBATCH --error=/home/fs02/pmr82_0001/ms3654/dissertation/D1_decision_scaling/slurm/logs/d1_gen_%A_%a.err
#SBATCH --array=0-6
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --partition=normal

set -euo pipefail
module load python/3.11.5
source ~/dissertation/venv/bin/activate

DISSERTATION_ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
cd "$DISSERTATION_ROOT"
export PYTHONPATH="$DISSERTATION_ROOT/shared:$PYTHONPATH"

BINS=(Q01 Q02 Q03 Q04 Q05 Q06 Q07)
BIN_ID="${BINS[$SLURM_ARRAY_TASK_ID]}"

python D1_decision_scaling/lib/generator/kirsch_generate.py --bin-id "$BIN_ID"
echo "Bin $BIN_ID complete"

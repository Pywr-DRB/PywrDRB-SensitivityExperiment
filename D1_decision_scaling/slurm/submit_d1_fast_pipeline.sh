#!/bin/bash
# Submit prewarm only. Pilot waits until cache is verified.
#
#   bash D1_decision_scaling/slurm/submit_d1_fast_pipeline.sh
#   bash D1_decision_scaling/slurm/submit_d1_fast_pipeline.sh 10   # 10 realizations

set -euo pipefail
REALIZATIONS="${1:-30}"

DISSERTATION_ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
cd "$DISSERTATION_ROOT"
mkdir -p D1_decision_scaling/slurm/logs

echo "=== Prewarm only (failure-surface NOT submitted) ==="
PREWARM_JOB=$(sbatch --parsable D1_decision_scaling/slurm/submit_prewarm_d1.sh)
echo "Prewarm job: $PREWARM_JOB"
echo ""
echo "When prewarm completes, verify then submit pilot:"
echo "  python D1_decision_scaling/experiments/check_d1_ready.py --realizations ${REALIZATIONS}"
echo "  sbatch --export=ALL,D1_REALIZATIONS=${REALIZATIONS} \\"
echo "    D1_decision_scaling/slurm/submit_failure_surface_lb1_pilot.sh"
echo ""
echo "Or chain pilot after prewarm:"
echo "  sbatch --dependency=afterok:${PREWARM_JOB} --export=ALL,D1_REALIZATIONS=${REALIZATIONS} \\"
echo "    D1_decision_scaling/slurm/submit_failure_surface_lb1_pilot.sh"

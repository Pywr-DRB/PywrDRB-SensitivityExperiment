#!/bin/bash
# Submit the full 16,384-task Sobol sweep 2 array in batches of 1000,
# working around the cluster's MaxArraySize=1001 limit.
#
# Sweep 2 changes vs sweep 1:
#   k=7 (adds erq_cap_mg: 1954 Decree Art. III-B-1(d) seasonal cap)
#   N=1024 → TOTAL_RUNS = 1024 × (2×7+2) = 16,384
#   pywrdrb includes ERQRelease (implemented 2026-06-02)
#
# Usage:
#   bash D4_distributed_risk/slurm/batch_submit_sobol_sweep2.sh [--dry-run]

set -euo pipefail

DISSERTATION_ROOT=~/dissertation
SLURM_SCRIPT="$DISSERTATION_ROOT/D4_distributed_risk/slurm/submit_sobol_sweep2.sh"
TOTAL_SAMPLES=16384
BATCH_SIZE=1000
CONCURRENT=10   # max simultaneous tasks per array (%N throttle — cluster etiquette)
DRY_RUN=0

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    echo "DRY RUN — will print sbatch commands but not submit"
fi

# Create task output directory
mkdir -p "$DISSERTATION_ROOT/D4_distributed_risk/results/sobol_sweep2/task_outputs"

N_BATCHES=$(( (TOTAL_SAMPLES + BATCH_SIZE - 1) / BATCH_SIZE ))
echo "Sweep 2: submitting $TOTAL_SAMPLES samples in $N_BATCHES batches of up to $BATCH_SIZE"
echo "  Samples CSV:  results/sobol_sweep2/sobol_samples.csv  (k=7, erq_cap_mg added)"
echo "  Task outputs: results/sobol_sweep2/task_outputs/"
echo ""

for batch in $(seq 0 $(( N_BATCHES - 1 ))); do
    OFFSET=$(( batch * BATCH_SIZE ))
    LAST=$(( OFFSET + BATCH_SIZE - 1 ))
    if (( LAST >= TOTAL_SAMPLES )); then
        LAST=$(( TOTAL_SAMPLES - 1 ))
    fi
    ARRAY_END=$(( LAST - OFFSET ))

    CMD=(sbatch
        --array="0-${ARRAY_END}%${CONCURRENT}"
        --export="ALL,BATCH_OFFSET=${OFFSET}"
        "$SLURM_SCRIPT"
    )

    printf "Batch %2d/%d  samples %5d–%5d  (array 0-%d)  " \
        "$batch" "$(( N_BATCHES - 1 ))" "$OFFSET" "$LAST" "$ARRAY_END"

    if (( DRY_RUN )); then
        echo "[DRY] ${CMD[*]}"
    else
        JOB_OUTPUT=$("${CMD[@]}" 2>&1)
        JOB_ID=$(echo "$JOB_OUTPUT" | grep -oP '(?<=Submitted batch job )\d+')
        echo "→ job $JOB_ID"
    fi
done

echo ""
echo "Done. Monitor with: squeue -u $USER | grep d4_sobol2"
echo "Check progress:     python D4_distributed_risk/lib/sensitivity/sobol_analysis.py --task-dir D4_distributed_risk/results/sobol_sweep2/task_outputs --design D4_distributed_risk/results/sobol_sweep2/sobol_design.json --outdir D4_distributed_risk/results/sobol_sweep2"

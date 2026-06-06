#!/bin/bash
# Submit Sobol batches 9–14 (samples 9000–14335) with sbatch retry.
# Use when batch_submit_sobol.sh stopped early due to Slurm submission limits.
#
#   bash D4_distributed_risk/slurm/submit_sobol_batches_remaining.sh

set -euo pipefail

DISSERTATION_ROOT=~/dissertation
SLURM_SCRIPT="$DISSERTATION_ROOT/D4_distributed_risk/slurm/submit_sobol.sh"
MAX_TRIES=30
SLEEP_SEC=60

submit_with_retry() {
    local -a cmd=("$@")
    local try
    for (( try = 1; try <= MAX_TRIES; try++ )); do
        if out=$("${cmd[@]}" 2>&1); then
            echo "$out"
            return 0
        fi
        echo "sbatch failed (try $try/$MAX_TRIES): $out"
        sleep "$SLEEP_SEC"
    done
    return 1
}

for batch in 9 10 11 12 13 14; do
    OFFSET=$(( batch * 1000 ))
    if (( batch == 14 )); then
        ARRAY_END=335
        LAST=14335
    else
        ARRAY_END=999
        LAST=$(( OFFSET + 999 ))
    fi
    printf "Batch %2d  samples %5d–%5d  " "$batch" "$OFFSET" "$LAST"
    submit_with_retry sbatch \
        --array="0-${ARRAY_END}" \
        --export="ALL,BATCH_OFFSET=${OFFSET}" \
        "$SLURM_SCRIPT"
done

echo "All remaining batches submitted."

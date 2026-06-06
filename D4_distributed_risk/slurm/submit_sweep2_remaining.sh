#!/bin/bash
# Submits the remaining sweep 2 batches (offsets 9000-16000) with retry on scheduler overload.
cd ~/dissertation
SLURM_SCRIPT="D4_distributed_risk/slurm/submit_sobol_sweep2.sh"

CONCURRENT=10  # %10 throttle — max 10 tasks running simultaneously per array

for OFFSET in 9000 10000 11000 12000 13000 14000 15000 16000; do
    if [ "$OFFSET" -eq 16000 ]; then ARRAY="0-383%${CONCURRENT}"; else ARRAY="0-999%${CONCURRENT}"; fi

    for attempt in 1 2 3 4 5; do
        OUT=$(sbatch --array="$ARRAY" --export="ALL,BATCH_OFFSET=${OFFSET}" "$SLURM_SCRIPT" 2>&1)
        if echo "$OUT" | grep -q "Submitted batch job"; then
            JOB_ID=$(echo "$OUT" | grep -oP '(?<=Submitted batch job )\d+')
            echo "Offset $OFFSET → job $JOB_ID (attempt $attempt)"
            break
        else
            echo "Offset $OFFSET attempt $attempt failed — sleeping 30s: $OUT"
            sleep 30
        fi
    done
done
echo "All remaining batches submitted."

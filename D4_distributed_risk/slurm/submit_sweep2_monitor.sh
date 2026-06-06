#!/bin/bash
# Submits sweep 2 remaining batches (offsets 9000-16000) one at a time,
# waiting for queue depth to drop below 6000 expanded tasks before each submission.
# Designed to run as a SLURM job so it can sleep and poll without a login session.

SLURM_SCRIPT="$HOME/dissertation/D4_distributed_risk/slurm/submit_sobol_sweep2.sh"
MAX_QUEUE=6000   # submit next batch only when expanded user queue drops below this

echo "Sweep 2 monitor started at $(date)"
echo "Remaining offsets: 9000 10000 11000 12000 13000 14000 15000 16000"

for OFFSET in 9000 10000 11000 12000 13000 14000 15000 16000; do
    if [ "$OFFSET" -eq 16000 ]; then ARRAY="0-383"; else ARRAY="0-999"; fi

    # Wait until queue is below threshold
    while true; do
        NQUEUE=$(squeue -u "$USER" --array --noheader 2>/dev/null | wc -l)
        echo "$(date +%H:%M:%S) Queue depth: $NQUEUE | Waiting to submit offset $OFFSET (threshold $MAX_QUEUE)"
        if [ "$NQUEUE" -lt "$MAX_QUEUE" ]; then
            break
        fi
        sleep 120   # check every 2 minutes
    done

    # Submit with retries
    for attempt in 1 2 3 4 5; do
        OUT=$(sbatch --array="$ARRAY" --export="ALL,BATCH_OFFSET=${OFFSET}" "$SLURM_SCRIPT" 2>&1)
        if echo "$OUT" | grep -q "Submitted batch job"; then
            JOB_ID=$(echo "$OUT" | grep -oP '(?<=Submitted batch job )\d+')
            echo "$(date +%H:%M:%S) Offset $OFFSET → job $JOB_ID"
            break
        else
            echo "$(date +%H:%M:%S) Offset $OFFSET attempt $attempt failed — sleeping 60s: $OUT"
            sleep 60
        fi
        if [ "$attempt" -eq 5 ]; then
            echo "ERROR: failed to submit offset $OFFSET after 5 attempts"
        fi
    done
done

echo "All remaining sweep 2 batches submitted at $(date)"

#!/bin/bash
# Submit the full 14,336-task Sobol array in batches of 1000,
# working around the cluster's MaxArraySize=1001 limit.
#
# Usage:
#   bash D4_distributed_risk/slurm/batch_submit_sobol.sh [--dry-run]
#
# Each batch submits --array=0-999 (or 0-N for the final partial batch)
# with BATCH_OFFSET exported so the worker script computes the real sample_id:
#   sample_id = BATCH_OFFSET + SLURM_ARRAY_TASK_ID
#
# Batches:
#   0:  samples    0 –  999  (1000 tasks)
#   1:  samples 1000 – 1999  (1000 tasks)
#   ...
#  13:  samples 13000 – 13999 (1000 tasks)
#  14:  samples 14000 – 14335 ( 336 tasks)

set -euo pipefail

DISSERTATION_ROOT=~/dissertation
SLURM_SCRIPT="$DISSERTATION_ROOT/D4_distributed_risk/slurm/submit_sobol.sh"
TOTAL_SAMPLES=14336
BATCH_SIZE=1000
CONCURRENT=${SOBOL_CONCURRENT:-10}   # override: SOBOL_CONCURRENT=16 bash batch_submit_sobol.sh
DRY_RUN=0

# Allow overriding the SLURM script and sample count via env vars or flags:
#   SOBOL_SCRIPT=.../submit_sobol_sweep3.sh bash batch_submit_sobol.sh
#   SOBOL_TOTAL=16384 bash batch_submit_sobol.sh   (for k=7 sweep2)
if [[ -n "${SOBOL_SCRIPT:-}" ]]; then
    SLURM_SCRIPT="$SOBOL_SCRIPT"
fi
if [[ -n "${SOBOL_TOTAL:-}" ]]; then
    TOTAL_SAMPLES="$SOBOL_TOTAL"
fi

if [[ "${1:-}" == "--dry-run" ]]; then
    DRY_RUN=1
    echo "DRY RUN — will print sbatch commands but not submit"
fi

N_BATCHES=$(( (TOTAL_SAMPLES + BATCH_SIZE - 1) / BATCH_SIZE ))
echo "Submitting $TOTAL_SAMPLES samples in $N_BATCHES batches of up to $BATCH_SIZE"
echo "  SLURM script:  $SLURM_SCRIPT"
echo "  Concurrent/array: ${CONCURRENT} (set SOBOL_CONCURRENT to override)"

BATCH_START=${BATCH_START:-0}
BATCH_END=${BATCH_END:-$(( N_BATCHES - 1 ))}
if (( BATCH_START < 0 || BATCH_END >= N_BATCHES || BATCH_START > BATCH_END )); then
    echo "Invalid batch range: BATCH_START=$BATCH_START BATCH_END=$BATCH_END (N_BATCHES=$N_BATCHES)"
    exit 1
fi
echo "  Batch range: ${BATCH_START}–${BATCH_END} (of 0–$(( N_BATCHES - 1 )))"

for batch in $(seq "$BATCH_START" "$BATCH_END"); do
    OFFSET=$(( batch * BATCH_SIZE ))
    LAST=$(( OFFSET + BATCH_SIZE - 1 ))
    if (( LAST >= TOTAL_SAMPLES )); then
        LAST=$(( TOTAL_SAMPLES - 1 ))
    fi
    ARRAY_END=$(( LAST - OFFSET ))

    # Build sbatch command
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
        for attempt in 1 2 3 4 5; do
            JOB_OUTPUT=$("${CMD[@]}" 2>&1) && break
            echo "attempt $attempt failed — sleeping 30s: $JOB_OUTPUT"
            sleep 30
        done
        JOB_ID=$(echo "$JOB_OUTPUT" | grep -oP '(?<=Submitted batch job )\d+' || true)
        if [[ -z "$JOB_ID" ]]; then
            echo "FAILED after 5 attempts: $JOB_OUTPUT"
            exit 1
        fi
        echo "→ job $JOB_ID"
    fi
done

echo "Done."

#!/bin/bash
# Re-run LB1 pilot cells with SalinityLSTM after PywrDRB-ML is available.
#
#   export PYWRDRB_ML_PLUGIN_PATH=/path/to/PywrDRB-ML
#   bash D1_decision_scaling/experiments/rerun_salinity_lb1.sh
#
# Removes metrics JSON without salinity.enabled, then resubmits 42-cell array.

set -euo pipefail
ROOT=/home/fs02/pmr82_0001/ms3654/dissertation
export PYWRDRB_ML_PLUGIN_PATH="${PYWRDRB_ML_PLUGIN_PATH:-$ROOT/D1_decision_scaling/stochastic_experiment/PywrDRB-ML}"
if [ ! -d "$PYWRDRB_ML_PLUGIN_PATH/models/SalinityLSTM" ]; then
  echo "PywrDRB-ML not found at $PYWRDRB_ML_PLUGIN_PATH" >&2
  exit 1
fi
RESULTS="$ROOT/D1_decision_scaling/results/failure_surface/d1_v1_7x6x3_r30"

find "$RESULTS" -name 'realization_*_metrics.json' | while read -r f; do
  if ! python3 -c "import json; d=json.load(open('$f')); exit(0 if d.get('salinity',{}).get('enabled') else 1)"; then
    rm -f "$f"
  fi
done

cd "$ROOT"
echo "Use fast pipeline after prewarm:"
echo "  python D1_decision_scaling/experiments/check_d1_ready.py"
echo "  sbatch D1_decision_scaling/slurm/submit_failure_surface_lb1_pilot.sh"

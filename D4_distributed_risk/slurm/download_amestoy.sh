#!/bin/bash
#SBATCH --job-name=download_amestoy
#SBATCH --output=slurm/logs/download_amestoy_%j.out
#SBATCH --error=slurm/logs/download_amestoy_%j.err
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=08:00:00          # 32.8 GB — generous buffer for slow network
#SBATCH --partition=normal

# Download Amestoy et al. (2025) DRB ensemble from Zenodo.
# DOI: 10.5281/zenodo.15101164
#
# Files downloaded:
#   pywrdrb_data.zip       (32.8 GB)  — PRIORITY: contains pre-run outputs + model inputs
#   prediction_locations.csv (1 kB)   — node location metadata
#
# NOT downloaded here (can add later if needed for raw streamflow):
#   drb_historic_streamflow_ensemble_data.zip  (11.5 GB)  — raw gage flow ensemble
#
# Output directory: ~/data/amestoy_2026/
#
# After completion, run:
#   cd ~/data/amestoy_2026 && unzip pywrdrb_data.zip
#   Then set AMESTOY_PATH in D4 run scripts.
#
# md5 verification (from Zenodo):
#   pywrdrb_data.zip: 2cd0d16301961268a895ad6f7a6229d3

set -euo pipefail

OUTDIR="$HOME/data/amestoy_2026"
mkdir -p "$OUTDIR"
cd "$OUTDIR"

ZENODO_RECORD="15101164"
BASE_URL="https://zenodo.org/records/${ZENODO_RECORD}/files"

echo "============================================================"
echo "Amestoy et al. (2025) Zenodo download"
echo "DOI: 10.5281/zenodo.${ZENODO_RECORD}"
echo "Target: $OUTDIR"
echo "Start: $(date)"
echo "============================================================"

# --- prediction_locations.csv (small, download first as connectivity check) ---
echo ""
echo "[1/2] Downloading prediction_locations.csv..."
wget -c --progress=dot:giga \
     -O prediction_locations.csv \
     "${BASE_URL}/prediction_locations.csv?download=1"
echo "  Done: $(ls -lh prediction_locations.csv | awk '{print $5}')"

# --- pywrdrb_data.zip (32.8 GB — primary data) ---
echo ""
echo "[2/2] Downloading pywrdrb_data.zip (32.8 GB)..."
echo "  Expected md5: 2cd0d16301961268a895ad6f7a6229d3"
wget -c --progress=dot:giga \
     -O pywrdrb_data.zip \
     "${BASE_URL}/pywrdrb_data.zip?download=1"
echo "  Done: $(ls -lh pywrdrb_data.zip | awk '{print $5}')"

# --- md5 verification ---
echo ""
echo "Verifying md5..."
EXPECTED_MD5="2cd0d16301961268a895ad6f7a6229d3"
ACTUAL_MD5=$(md5sum pywrdrb_data.zip | awk '{print $1}')
if [[ "$ACTUAL_MD5" == "$EXPECTED_MD5" ]]; then
    echo "  md5 OK: $ACTUAL_MD5"
else
    echo "  WARNING: md5 mismatch!"
    echo "    Expected: $EXPECTED_MD5"
    echo "    Got:      $ACTUAL_MD5"
    echo "  File may be corrupt. Re-run with: wget -c ..."
fi

echo ""
echo "Download complete: $(date)"
echo ""
echo "Next step: extract the zip"
echo "  cd $OUTDIR && unzip pywrdrb_data.zip"
echo ""
echo "Key files after extraction:"
echo "  pywrdrb_inputs/historic_ensembles/"
echo "    catchment_inflow_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5  <- re-run inputs"
echo "    predicted_inflows_diversions_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5"
echo "  pywrdrb_outputs/"
echo "    pywrdrb_results_export_obs_pub_nhmv10_BC_ObsScaled_ensemble.hdf5  <- pre-run results"
echo ""
echo "Then run D4 baseline pipeline validation (fast, pre-run data):"
echo "  python ~/dissertation/D4_distributed_risk/experiments/run_d4_baseline.py \\"
echo "      --mode prerun \\"
echo "      --ensemble-path ~/data/amestoy_2026 \\"
echo "      --outdir ~/dissertation/D4_distributed_risk/results/baseline_prerun"
echo ""
echo "For publication-quality results (after Gate 1 endorsement), submit:"
echo "  cd ~/dissertation && sbatch D4_distributed_risk/slurm/submit_baseline.sh"

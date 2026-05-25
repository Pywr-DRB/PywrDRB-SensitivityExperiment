#!/bin/bash
# =============================================================================
# CMIP6 Multimodel Streamflow Workflow
# Dissertation branch: ms3654 (Marilyn Smith)
#
# Provenance: scripts from Pywr-DRB/CMIP6_multimodel_streamflow (Trevor Amestoy)
# pywrdrb: dissertation branch (~/dissertation/pywrdrb), installed as editable
#          into ~/dissertation/venv — must include mpi4py via system site packages
#
# Venv setup (run once before submitting):
#   module load python/3.11.5 gnu9 openmpi4 py3-mpi4py/3.0.3
#   python3 -m venv --system-site-packages ~/dissertation/venv
#   source ~/dissertation/venv/bin/activate
#   pip install -e ~/dissertation/pywrdrb/
#
# Submit: sbatch run_workflow.sh
# =============================================================================
#SBATCH --job-name=cmip6_prep
#SBATCH --output=./logs/%j_prep.out
#SBATCH --error=./logs/%j_prep.err
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --time=04:00:00

# Load modules (must match venv creation environment)
module load python/3.11.5 gnu9 openmpi4 py3-mpi4py/3.0.3

# Activate dissertation venv (installed from ~/dissertation/pywrdrb/)
source ~/dissertation/venv/bin/activate

# Number of MPI tasks
np=$(($SLURM_NTASKS_PER_NODE * $SLURM_NNODES))

# Change to cmip6 script directory (config.py resolves DATA_DIR relative to __file__)
cd ~/dissertation/cmip6

# --- Step 1: Generate predicted inflows + diversions for all 72 CMIP6 datasets ---
mpirun -n $np python3 01_prep_pywrdrb_inputs.py

# --- Step 2: Run Pywr-DRB simulations for all 72 datasets ---
# mpirun -n $np python3 02_run_pywrdrb_simulations.py

# --- Plotting (single process) ---
# python3 plot_model_results.py
# python3 plot_dataset_pval_tests.py

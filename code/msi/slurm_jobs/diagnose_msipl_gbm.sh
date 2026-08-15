#!/bin/bash
#SBATCH --job-name=msipl-diag
#SBATCH --partition=bigbatch
#SBATCH --output=logs/msipl-diag-%j.out
#SBATCH --error=logs/msipl-diag-%j.err
#SBATCH --time=00:10:00
#SBATCH --cpus-per-task=1

set -e

echo "=========================================="
echo "        msiPL GBM DATA DIAGNOSTIC"
echo "=========================================="

echo "Date: $(date)"
echo "User: $USER"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Working directory: $(pwd)"
echo

# --------------------------------------------------
# Environment
# --------------------------------------------------

source ~/miniconda3/etc/profile.d/conda.sh
conda activate msipl_env

echo "--- Python ---"
which python
python --version
echo

# --------------------------------------------------
# Project directory
# --------------------------------------------------

cd ~/msi

# --------------------------------------------------
# Run diagnostic
# --------------------------------------------------

python scripts/diagnose_msipl_gbm.py \
    --input /datasets/zsuliman/msi_data/gbm/Dataset_S1.h5 \
    --output results/baselines/msipl/diagnostics/Dataset_S1_stats.json

echo
echo "=========================================="
echo "      msiPL DIAGNOSTIC COMPLETE"
echo "=========================================="
echo "Output:"
echo "results/baselines/msipl/diagnostics/Dataset_S1_stats.json"
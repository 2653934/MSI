#!/bin/bash
#SBATCH --job-name=msipl-gbm
#SBATCH --output=logs/msipl-gbm-%j.out
#SBATCH --error=logs/msipl-gbm-%j.err
#SBATCH --time=12:00:00
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch

set -e

echo "=========================================="
echo "        msiPL GBM BASELINE"
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
# Move to project
# --------------------------------------------------

cd ~/msi

# --------------------------------------------------
# Run msiPL smoke test
# --------------------------------------------------

python scripts/run_msipl_gbm.py \
    --input /datasets/zsuliman/msi_data/gbm/Dataset_S1.h5 \
    --output-dir results/baselines/msipl/test_S1 \
    --epochs 2 \
    --batch-size 128 \
    --latent-dim 5 \
    --intermediate-dim 512 \
    --beta 2.5 \
    --seed 0

echo
echo "=========================================="
echo "        msiPL JOB COMPLETE"
echo "=========================================="
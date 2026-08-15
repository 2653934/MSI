#!/bin/bash
#SBATCH --job-name=msipl-legacy
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/msipl-legacy-%j.out
#SBATCH --error=logs/msipl-legacy-%j.err

set -e

DATASET="${1:?Usage: sbatch slurm_jobs/run_msipl_legacy_s1.sh Dataset_S2}"

echo "=========================================="
echo "        LEGACY msiPL GBM"
echo "=========================================="

echo "Dataset: $DATASET"
echo "Date: $(date)"
echo "User: $USER"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo

source ~/miniconda3/etc/profile.d/conda.sh
conda activate msipl_legacy

echo "--- Environment ---"
which python
python --version
python -c "import tensorflow; print('TensorFlow:', tensorflow.__version__)"
python -c "import keras; print('Keras:', keras.__version__)"
echo

cd ~/msi

python scripts/run_msipl_legacy_gbm.py \
    --input "/datasets/zsuliman/msi_data/gbm/${DATASET}.h5" \
    --output-dir "results/baselines/msipl/legacy/${DATASET}" \
    --epochs 100 \
    --batch-size 128 \
    --latent-dim 5 \
    --intermediate-dim 512 \
    --beta 2.5 \
    --seed 1337

echo
echo "=========================================="
echo "        LEGACY msiPL JOB COMPLETE"
echo "=========================================="
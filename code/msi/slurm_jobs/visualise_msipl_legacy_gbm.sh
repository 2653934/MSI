#!/bin/bash
#SBATCH --job-name=msipl-legacy-vis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --output=logs/msipl-legacy-vis-%j.out
#SBATCH --error=logs/msipl-legacy-vis-%j.err

set -e

echo "=========================================="
echo "      LEGACY msiPL VISUALISATION"
echo "=========================================="

echo "Date: $(date)"
echo "User: $USER"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Working directory: $(pwd)"
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

python scripts/visualise_msipl_legacy_gbm.py \
    --input /datasets/zsuliman/msi_data/gbm/Dataset_S1.h5 \
    --checkpoint checkpoints/baselines/msipl/legacy/Dataset_S1/msipl_weights.h5 \
    --output-dir results/baselines/msipl/legacy/Dataset_S1 \
    --latent-dim 5 \
    --intermediate-dim 512 \
    --batch-size 128 \
    --seed 1337

echo
echo "=========================================="
echo "     VISUALISATION JOB COMPLETE"
echo "=========================================="
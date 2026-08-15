#!/bin/bash
#SBATCH --job-name=msipl-vis
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --output=logs/msipl-vis-%j.out
#SBATCH --error=logs/msipl-vis-%j.err

set -e

DATASET="${1:?Usage: sbatch slurm_jobs/visualise_msipl_legacy.sh Dataset_S2}"

echo "=========================================="
echo "      LEGACY msiPL VISUALISATION"
echo "=========================================="

echo "Dataset: $DATASET"
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo

source ~/miniconda3/etc/profile.d/conda.sh
conda activate msipl_legacy

cd ~/msi

python scripts/visualise_msipl_legacy_gbm.py \
    --input "/datasets/zsuliman/msi_data/gbm/${DATASET}.h5" \
    --checkpoint "checkpoints/baselines/msipl/legacy/${DATASET}/msipl_weights.h5" \
    --output-dir "results/baselines/msipl/legacy/${DATASET}" \
    --latent-dim 5 \
    --intermediate-dim 512 \
    --batch-size 128 \
    --seed 1337

echo
echo "=========================================="
echo "     VISUALISATION JOB COMPLETE"
echo "=========================================="
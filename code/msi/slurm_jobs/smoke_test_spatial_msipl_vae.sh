#!/bin/bash
#SBATCH --job-name=spatial-vae
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=8G
#SBATCH --output=logs/spatial-vae-%j.out
#SBATCH --error=logs/spatial-vae-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_vae/GBM108_positive_smoke"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/smoke_test_spatial_msipl_vae.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --epochs 1 \
    --batch-size 4 \
    --hidden-dim 32 \
    --latent-dim 5 \
    --maximum-samples 32 \
    --device cpu


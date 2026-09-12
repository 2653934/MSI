#!/bin/bash
#SBATCH --job-name=spatial-pilot
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=12G
#SBATCH --output=logs/spatial-pilot-%j.out
#SBATCH --error=logs/spatial-pilot-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_neighbourhood_training/GBM108_positive_pilot"
CHECKPOINT_OUTPUT="$PROJECT_ROOT/checkpoints/spatial_msipl/validation/GBM108_positive_pilot"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/pilot_spatial_msipl_neighbourhood_training.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --epochs 1 \
    --batch-size 4 \
    --hidden-dim 32 \
    --latent-dim 5 \
    --attention-dim 8 \
    --maximum-samples 32 \
    --learning-rate 0.001 \
    --seed 1 \
    --device cpu


#!/bin/bash
#SBATCH --job-name=spatial-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster45,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/spatial-eval-%j.out
#SBATCH --error=logs/spatial-eval-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/GBM108_positive_seed1"
TRAINING_RESULTS="$PROJECT_ROOT/results/experiments/spatial_msipl_neighbourhood/GBM108_positive_seed1"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_neighbourhood_evaluation/GBM108_positive_seed1"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable on this node; evaluation stopped before loading a model.")'

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_spatial_msipl_neighbourhoods.py \
    --input "$INPUT" \
    --checkpoint-root "$CHECKPOINT_ROOT" \
    --training-results "$TRAINING_RESULTS" \
    --output "$OUTPUT" \
    --batch-size 64 \
    --tile-rows 4 \
    --tile-columns 4 \
    --halo 1 \
    --seed 1

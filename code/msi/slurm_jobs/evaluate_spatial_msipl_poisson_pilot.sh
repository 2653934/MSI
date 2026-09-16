#!/bin/bash
#SBATCH --job-name=poisson-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster74,mscluster83
#SBATCH --output=logs/poisson-eval-%j.out
#SBATCH --error=logs/poisson-eval-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
BASELINE_NAME="uniform_mean_lambda_0p0_spectral_scaled_pilot"
POISSON_NAME="uniform_mean_count_100000_pilot"
BASELINE_CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/spatial_loss/GBM108_positive_seed1/$BASELINE_NAME/checkpoint.pt"
POISSON_CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/poisson/GBM108_positive_seed1/$POISSON_NAME/checkpoint.pt"
BASELINE_SUMMARY="$PROJECT_ROOT/results/experiments/spatial_msipl_spatial_loss/GBM108_positive_seed1/$BASELINE_NAME/summary.json"
POISSON_SUMMARY="$PROJECT_ROOT/results/experiments/spatial_msipl_poisson/GBM108_positive_seed1/$POISSON_NAME/summary.json"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_poisson_evaluation/GBM108_positive_seed1"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; Poisson evaluation stopped.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_poisson_augmentation_pilot.py \
    --input "$INPUT" \
    --baseline-checkpoint "$BASELINE_CHECKPOINT" \
    --poisson-checkpoint "$POISSON_CHECKPOINT" \
    --baseline-summary "$BASELINE_SUMMARY" \
    --poisson-summary "$POISSON_SUMMARY" \
    --output "$OUTPUT" \
    --effective-count 100000 \
    --batch-size 64 \
    --seed 1 \
    --noise-seed 20260916

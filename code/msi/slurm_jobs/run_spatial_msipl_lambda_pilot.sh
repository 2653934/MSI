#!/bin/bash
#SBATCH --job-name=spatial-lambda
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster74,mscluster83
#SBATCH --output=logs/spatial-lambda-%j.out
#SBATCH --error=logs/spatial-lambda-%j.err

set -eo pipefail

if [[ $# -ne 1 ]] || ! [[ "$1" =~ ^(0\.0|0\.01|0\.1|1\.0)$ ]]; then
    echo "Usage: sbatch $0 {0.0|0.01|0.1|1.0}" >&2
    exit 2
fi

SPATIAL_LAMBDA="$1"
LAMBDA_LABEL="${SPATIAL_LAMBDA//./p}"
PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_spatial_loss/GBM108_positive_seed1/uniform_mean_lambda_${LAMBDA_LABEL}_spectral_scaled_pilot"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/spatial_loss/GBM108_positive_seed1/uniform_mean_lambda_${LAMBDA_LABEL}_spectral_scaled_pilot"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; spatial-loss pilot stopped before training.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant uniform_mean \
    --epochs 5 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda "$SPATIAL_LAMBDA" \
    --spatial-loss-scale spectral_bins \
    --seed 1

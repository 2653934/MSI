#!/bin/bash
#SBATCH --job-name=spatial-cached-full
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/spatial-cached-full-%j.out
#SBATCH --error=logs/spatial-cached-full-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {central_only|uniform_mean}" >&2
    exit 2
fi
VARIANT="$1"
case "$VARIANT" in
    central_only|uniform_mean) ;;
    *) echo "Unknown variant: $VARIANT" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_cached_full/GBM108_positive_seed1/$VARIANT"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cache_validation/GBM108_positive_seed1/$VARIANT"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [ ! -f "$INPUT" ]; then
    echo "Input does not exist: $INPUT" >&2
    exit 1
fi
if [ -f "$FINAL_CHECKPOINT" ] && [ -f "$OUTPUT/summary.json" ]; then
    echo "Cached validation already complete: $OUTPUT"
    exit 0
fi
if [ -f "$FINAL_CHECKPOINT" ] || [ -f "$OUTPUT/summary.json" ]; then
    echo "Partial final artifacts require inspection before resubmission: $OUTPUT" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA unavailable; cached validation stopped before loading the model")'
python -m unittest spatial_msipl.tests.test_preprocessing spatial_msipl.tests.test_model

RESUME_ARGUMENTS=()
if [ -f "$LATEST_CHECKPOINT" ]; then
    echo "Resuming cached $VARIANT from $LATEST_CHECKPOINT"
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
else
    echo "Starting separate cached 100-epoch validation: $VARIANT"
fi

python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --cache-spectra \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda 0 \
    --seed 1 \
    --checkpoint-interval 5 \
    "${RESUME_ARGUMENTS[@]}"

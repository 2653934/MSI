#!/bin/bash
#SBATCH --job-name=spatial-production
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster45,mscluster65,mscluster83
#SBATCH --output=logs/spatial-production-%j.out
#SBATCH --error=logs/spatial-production-%j.err

set -eo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: sbatch $0 {uniform_mean|depthwise|attention}" >&2
    exit 2
fi

VARIANT="$1"
case "$VARIANT" in
    uniform_mean|depthwise|attention) ;;
    *)
        echo "Unknown neighbourhood variant: $VARIANT" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_neighbourhood/GBM108_positive_seed1/$VARIANT"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/GBM108_positive_seed1/$VARIANT"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [[ -f "$FINAL_CHECKPOINT" ]]; then
    echo "Completed checkpoint already exists; refusing to overwrite: $FINAL_CHECKPOINT"
    exit 0
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable on this node; training stopped before allocating the model.")'

RESUME_ARGUMENTS=()
if [[ -f "$LATEST_CHECKPOINT" ]]; then
    echo "Resuming from: $LATEST_CHECKPOINT"
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
else
    echo "Starting a new matched run for: $VARIANT"
fi

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --attention-dim 8 \
    --learning-rate 0.001 \
    --seed 1 \
    --checkpoint-interval 5 \
    "${RESUME_ARGUMENTS[@]}"

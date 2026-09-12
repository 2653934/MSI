#!/bin/bash
#SBATCH --job-name=spatial-stability
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/spatial-stability-%j.out
#SBATCH --error=logs/spatial-stability-%j.err

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
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_stability/GBM108_positive_seed1/$VARIANT"
CHECKPOINT_OUTPUT="$PROJECT_ROOT/checkpoints/spatial_msipl/stability/GBM108_positive_seed1/$VARIANT"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable on this node; training stopped before allocating the model.")'

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_stability.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --epochs 5 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --attention-dim 8 \
    --learning-rate 0.001 \
    --seed 1

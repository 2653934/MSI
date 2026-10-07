#!/bin/bash
#SBATCH --job-name=s3pl-gbm
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=12:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-gbm-%j.out
#SBATCH --error=logs/s3pl-gbm-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATASET="${1:-GBM108_positive}"
EPOCHS="${2:-10}"
EVALUATE="${3:-true}"
PATCH_SIZE="${4:-3}"
ARTIFACT_ROOT="${5:-$PROJECT_ROOT}"
NORMALIZATION="${6:-reference_spatial_max}"
RANDOM_SEED="${7:-1}"

case "$DATASET" in
    GBM108_negative|GBM108_positive|GBM12_1|GBM12_2|GBM22_1|GBM22_2|GBM39_1|GBM39_2)
        ;;
    *)
        echo "Unknown MassNet GBM section: $DATASET" >&2
        exit 2
        ;;
esac

if ! [[ "$EPOCHS" =~ ^[1-9][0-9]*$ ]]; then
    echo "Epochs must be a positive integer: $EPOCHS" >&2
    exit 2
fi

if ! [[ "$PATCH_SIZE" =~ ^[1-9][0-9]*$ ]] || (( PATCH_SIZE % 2 == 0 )); then
    echo "Patch size must be a positive odd integer: $PATCH_SIZE" >&2
    exit 2
fi

case "$ARTIFACT_ROOT" in
    "$PROJECT_ROOT"|"$PROJECT_ROOT"/*)
        ;;
    *)
        echo "Artifact root must stay inside $PROJECT_ROOT: $ARTIFACT_ROOT" >&2
        exit 2
        ;;
esac

case "$EVALUATE" in
    true)
        EVAL_FLAG="--eval_picking"
        ;;
    false)
        EVAL_FLAG="--no-eval_picking"
        ;;
    *)
        echo "Evaluation must be true or false: $EVALUATE" >&2
        exit 2
        ;;
esac

case "$NORMALIZATION" in
    reference_spatial_max|paper_tic)
        ;;
    *)
        echo "Normalization must be reference_spatial_max or paper_tic: $NORMALIZATION" >&2
        exit 2
        ;;
esac

if ! [[ "$RANDOM_SEED" =~ ^[0-9]+$ ]]; then
    echo "Random seed must be a nonnegative integer: $RANDOM_SEED" >&2
    exit 2
fi

S3PL_ROOT="$PROJECT_ROOT/baselines/s3pl"
DATA_PATH="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() and torch.ones(1, device="cuda").item() == 1.0 else "CUDA is unavailable on this node; refusing to run S3PL on CPU.")'

cd "$S3PL_ROOT"
python main.py \
    --data_dir "$DATA_PATH" \
    --artifact_root "$ARTIFACT_ROOT" \
    --number_classes 2 \
    --n_epochs "$EPOCHS" \
    --spectral_patch_size "$PATCH_SIZE" \
    --peaks_per_spectral_patch 256 \
    --batch_size 16 \
    --learning_rate 0.01 \
    --kernel_depth_d1 51 \
    --kernel_depth_d2 1 \
    --dropout 0 \
    --normalization "$NORMALIZATION" \
    --input-context-mode none \
    --random_seed "$RANDOM_SEED" \
    "$EVAL_FLAG"

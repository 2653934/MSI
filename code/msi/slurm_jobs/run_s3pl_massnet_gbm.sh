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

S3PL_ROOT="$PROJECT_ROOT/baselines/s3pl"
DATA_PATH="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable on this node; refusing to run S3PL on CPU.")'

cd "$S3PL_ROOT"
python main.py \
    --data_dir "$DATA_PATH" \
    --artifact_root "$ARTIFACT_ROOT" \
    --number_classes 2 \
    --n_epochs "$EPOCHS" \
    --spectral_patch_size "$PATCH_SIZE" \
    "$EVAL_FLAG"

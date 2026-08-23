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

DATASET="${1:-GBM108_positive}"
EPOCHS="${2:-10}"
EVALUATE="${3:-true}"

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

PROJECT_ROOT="$HOME/msi"
S3PL_ROOT="$PROJECT_ROOT/baselines/s3pl"
DATA_PATH="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

cd "$S3PL_ROOT"
python main.py \
    --data_dir "$DATA_PATH" \
    --artifact_root "$PROJECT_ROOT" \
    --number_classes 2 \
    --n_epochs "$EPOCHS" \
    "$EVAL_FLAG"

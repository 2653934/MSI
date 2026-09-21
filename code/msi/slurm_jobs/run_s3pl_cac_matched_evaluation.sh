#!/bin/bash
#SBATCH --job-name=s3pl-match
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-match-%j.out
#SBATCH --error=logs/s3pl-match-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL}" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    40TopL)  MATCHED_PEAKS=315 ;;
    160TopL) MATCHED_PEAKS=210 ;;
    200TopL) MATCHED_PEAKS=221 ;;
    240TopL) MATCHED_PEAKS=255 ;;
    280TopL) MATCHED_PEAKS=245 ;;
    360TopL) MATCHED_PEAKS=247 ;;
    400TopL) MATCHED_PEAKS=133 ;;
    520TopL) MATCHED_PEAKS=232 ;;
    *)
        echo "Unknown CAC section: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
TRAINING_NAME="${DATASET}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
CONFIG="$PROJECT_ROOT/logs/s3pl/${TRAINING_NAME}.json"
CHECKPOINT="$PROJECT_ROOT/checkpoints/baselines/s3pl/${TRAINING_NAME}.pt"

if [ ! -f "$CONFIG" ]; then
    echo "Missing S3PL configuration: $CONFIG" >&2
    exit 1
fi
if [ ! -f "$CHECKPOINT" ]; then
    echo "Missing S3PL checkpoint: $CHECKPOINT" >&2
    exit 1
fi

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export OMP_NUM_THREADS=4

python -u scripts/evaluate_s3pl_matched_peak_count.py \
    --config "$CONFIG" \
    --number-peaks "$MATCHED_PEAKS"

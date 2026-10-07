#!/bin/bash
#SBATCH --job-name=s3pl-context
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-context-%j.out
#SBATCH --error=logs/s3pl-context-%j.err

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL}" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    40TopL) MATCHED_PEAKS=315 ;;
    160TopL) MATCHED_PEAKS=210 ;;
    200TopL) MATCHED_PEAKS=221 ;;
    240TopL) MATCHED_PEAKS=255 ;;
    280TopL) MATCHED_PEAKS=245 ;;
    360TopL) MATCHED_PEAKS=247 ;;
    400TopL) MATCHED_PEAKS=133 ;;
    520TopL) MATCHED_PEAKS=232 ;;
    *) echo "Unknown CAC section: $DATASET" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
TRAINING_NAME="${DATASET}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
CONFIG="$PROJECT_ROOT/logs/s3pl/${TRAINING_NAME}.json"
OUTPUT="$PROJECT_ROOT/results/diagnostics/s3pl_cac_frozen_context/${DATASET}.json"

cd "$PROJECT_ROOT"
set +u  # Conda's MKL activation hook reads optional unset variables.
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
set -u
export OMP_NUM_THREADS=4

python -m py_compile baselines/s3pl/test.py scripts/evaluate_s3pl_cac_frozen_context.py
python -m unittest discover -s baselines/s3pl/tests -p 'test_frozen_patch_context.py' -v
python -u scripts/evaluate_s3pl_cac_frozen_context.py \
    --config "$CONFIG" \
    --number-peaks "$MATCHED_PEAKS" \
    --output "$OUTPUT"

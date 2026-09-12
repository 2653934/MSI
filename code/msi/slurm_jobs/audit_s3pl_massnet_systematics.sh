#!/bin/bash
#SBATCH --job-name=s3pl-h5-audit
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:45:00
#SBATCH --mem=16G
#SBATCH --output=logs/s3pl-h5-audit-%j.out
#SBATCH --error=logs/s3pl-h5-audit-%j.err

set -eo pipefail

DATASET="${1:-GBM108_positive}"

case "$DATASET" in
    GBM108_negative|GBM108_positive|GBM12_1|GBM12_2|GBM22_1|GBM22_2|GBM39_1|GBM39_2)
        ;;
    *)
        echo "Unknown MassNet GBM section: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
DATA_PATH="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
OUTPUT_PATH="$PROJECT_ROOT/results/validation/s3pl_massnet_systematics/${DATASET}_p3.json"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

cd "$PROJECT_ROOT"
python scripts/audit_s3pl_massnet_systematics.py \
    --input "$DATA_PATH" \
    --patch-size 3 \
    --output "$OUTPUT_PATH"

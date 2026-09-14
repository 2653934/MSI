#!/bin/bash
#SBATCH --job-name=msipl-beta
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=64G
#SBATCH --exclusive
#SBATCH --output=logs/msipl-beta-%j.out
#SBATCH --error=logs/msipl-beta-%j.err

set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: sbatch $0 DATASET" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    GBM12_1)         TARGET_PEAKS=691 ;;
    GBM12_2)         TARGET_PEAKS=981 ;;
    GBM22_1)         TARGET_PEAKS=845 ;;
    GBM22_2)         TARGET_PEAKS=1014 ;;
    GBM39_1)         TARGET_PEAKS=696 ;;
    GBM39_2)         TARGET_PEAKS=917 ;;
    GBM108_positive) TARGET_PEAKS=581 ;;
    GBM108_negative) TARGET_PEAKS=937 ;;
    *)
        echo "Unknown MassNet dataset: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5"
WEIGHTS="/datasets/zsuliman/msi_checkpoints/baselines/msipl/massnet/$DATASET/msipl_weights.h5"
OUTPUT="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned/$DATASET"

if [[ ! -f "$INPUT" ]]; then
    echo "Input dataset not found: $INPUT" >&2
    exit 1
fi
if [[ ! -f "$WEIGHTS" ]]; then
    echo "Trained checkpoint not found: $WEIGHTS" >&2
    exit 1
fi
if [[ -f "$OUTPUT/peak_metrics.json" ]]; then
    echo "Completed tuned metrics already exist; refusing to overwrite: $OUTPUT/peak_metrics.json"
    exit 0
fi

mkdir -p "$PROJECT_ROOT/logs" "$OUTPUT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate msipl_legacy
export OMP_NUM_THREADS=8

python -m py_compile \
    scripts/tune_msipl_massnet_beta.py \
    scripts/evaluate_msipl_massnet_peaks.py

python scripts/tune_msipl_massnet_beta.py \
    --input "$INPUT" \
    --weights "$WEIGHTS" \
    --output "$OUTPUT" \
    --target-peaks "$TARGET_PEAKS" \
    --tolerance 50 \
    --beta-min 1.0 \
    --beta-max 2.5 \
    --beta-step 0.05

python scripts/evaluate_msipl_massnet_peaks.py \
    --input "$INPUT" \
    --peaks "$OUTPUT/learned_peaks.csv" \
    --output "$OUTPUT"

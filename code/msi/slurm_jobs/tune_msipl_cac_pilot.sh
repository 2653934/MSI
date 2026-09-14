#!/bin/bash
#SBATCH --job-name=msipl-cac-beta
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --exclusive
#SBATCH --output=logs/msipl-cac-beta-%j.out
#SBATCH --error=logs/msipl-cac-beta-%j.err

set -euo pipefail

DATASET="${1:-40TopL}"
if [[ "$DATASET" != "40TopL" ]]; then
    echo "This tuning pilot is intentionally restricted to 40TopL." >&2
    exit 2
fi

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5"
WEIGHTS="/datasets/zsuliman/msi_checkpoints/baselines/msipl/cac/$DATASET/msipl_weights.h5"
OUTPUT="$PROJECT_ROOT/results/baselines/msipl/cac/$DATASET"
TARGET_PEAKS=342

if [[ ! -f "$INPUT" ]]; then
    echo "CAC adapter not found: $INPUT" >&2
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
    --beta-min 0.0 \
    --beta-max 2.5 \
    --beta-step 0.05

python scripts/evaluate_msipl_massnet_peaks.py \
    --input "$INPUT" \
    --peaks "$OUTPUT/learned_peaks.csv" \
    --output "$OUTPUT"

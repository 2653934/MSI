#!/bin/bash
#SBATCH --job-name=msipl-cac
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/msipl-cac-%j.out
#SBATCH --error=logs/msipl-cac-%j.err

set -euo pipefail

DATASET="${1:-40TopL}"
if [[ "$DATASET" != "40TopL" ]]; then
    echo "This validation pilot is intentionally restricted to 40TopL." >&2
    exit 2
fi

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5"
OUTPUT="$PROJECT_ROOT/results/baselines/msipl/cac_fixed_beta/$DATASET"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/baselines/msipl/cac"

if [[ ! -f "$INPUT" ]]; then
    echo "CAC adapter not found: $INPUT" >&2
    echo "Run prepare_msipl_cac_pilot.sh first." >&2
    exit 1
fi
if [[ -f "$OUTPUT/peak_metrics.json" ]]; then
    echo "Completed pilot already exists; refusing to overwrite: $OUTPUT/peak_metrics.json"
    exit 0
fi

mkdir -p "$PROJECT_ROOT/logs" "$OUTPUT" "$CHECKPOINT_ROOT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate msipl_legacy
export OMP_NUM_THREADS=8

python -m py_compile \
    scripts/run_msipl_legacy_gbm.py \
    scripts/evaluate_msipl_massnet_peaks.py

python scripts/run_msipl_legacy_gbm.py \
    --input "$INPUT" \
    --output-dir "$OUTPUT" \
    --checkpoint-root "$CHECKPOINT_ROOT" \
    --epochs 100 \
    --batch-size 128 \
    --latent-dim 5 \
    --intermediate-dim 512 \
    --beta 2.5 \
    --seed 1337

python scripts/evaluate_msipl_massnet_peaks.py \
    --input "$INPUT" \
    --peaks "$OUTPUT/learned_peaks.csv" \
    --output "$OUTPUT"

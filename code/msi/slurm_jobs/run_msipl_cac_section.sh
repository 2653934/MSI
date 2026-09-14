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

set -eo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: sbatch $0 DATASET" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    40TopL)  TARGET_PEAKS=342 ;;
    160TopL) TARGET_PEAKS=199 ;;
    200TopL) TARGET_PEAKS=214 ;;
    240TopL) TARGET_PEAKS=257 ;;
    280TopL) TARGET_PEAKS=238 ;;
    360TopL) TARGET_PEAKS=246 ;;
    400TopL) TARGET_PEAKS=137 ;;
    520TopL) TARGET_PEAKS=257 ;;
    *)
        echo "Unknown CAC dataset: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
SOURCE_ROOT="/datasets/zsuliman/msi_data/cac"
ADAPTER_ROOT="/datasets/zsuliman/msi_data/cac_msipl"
INPUT="$ADAPTER_ROOT/$DATASET.h5"
MASK="$SOURCE_ROOT/masks/${DATASET}_mask.npy"
AUDIT="$PROJECT_ROOT/results/validation/msipl_cac_adapter/$DATASET.json"
FIXED_OUTPUT="$PROJECT_ROOT/results/baselines/msipl/cac_fixed_beta/$DATASET"
TUNED_OUTPUT="$PROJECT_ROOT/results/baselines/msipl/cac/$DATASET"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/baselines/msipl/cac"
WEIGHTS="$CHECKPOINT_ROOT/$DATASET/msipl_weights.h5"

mkdir -p \
    "$PROJECT_ROOT/logs" \
    "$ADAPTER_ROOT" \
    "$(dirname "$AUDIT")" \
    "$FIXED_OUTPUT" \
    "$TUNED_OUTPUT" \
    "$CHECKPOINT_ROOT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"

echo "=== $DATASET: 1/3 PREPARE CAC ADAPTER ==="
if [[ -f "$INPUT" && -f "$AUDIT" ]]; then
    echo "Validated adapter artifacts already exist; reusing them."
else
    conda activate s3pl_env
    python scripts/prepare_msipl_cac_h5.py \
        --input "$SOURCE_ROOT/$DATASET.imzML" \
        --mask "$MASK" \
        --output "$INPUT" \
        --audit "$AUDIT"
fi

echo "=== $DATASET: 2/3 TRAIN FIXED-BETA LEGACY msiPL ==="
conda activate msipl_legacy
export OMP_NUM_THREADS=8

python -m py_compile \
    scripts/run_msipl_legacy_gbm.py \
    scripts/tune_msipl_massnet_beta.py \
    scripts/evaluate_msipl_massnet_peaks.py

if [[ -f "$FIXED_OUTPUT/peak_metrics.json" && -f "$WEIGHTS" ]]; then
    echo "Fixed-Beta training and evaluation already exist; reusing the checkpoint."
else
    python scripts/run_msipl_legacy_gbm.py \
        --input "$INPUT" \
        --output-dir "$FIXED_OUTPUT" \
        --checkpoint-root "$CHECKPOINT_ROOT" \
        --epochs 100 \
        --batch-size 128 \
        --latent-dim 5 \
        --intermediate-dim 512 \
        --beta 2.5 \
        --seed 1337

    python scripts/evaluate_msipl_massnet_peaks.py \
        --input "$INPUT" \
        --peaks "$FIXED_OUTPUT/learned_peaks.csv" \
        --output "$FIXED_OUTPUT"
fi

if [[ ! -f "$WEIGHTS" ]]; then
    echo "Expected trained checkpoint not found: $WEIGHTS" >&2
    exit 1
fi

echo "=== $DATASET: 3/3 PAPER-ALIGNED BETA AND EVALUATION ==="
if [[ -f "$TUNED_OUTPUT/peak_metrics.json" ]]; then
    echo "Paper-aligned metrics already exist; refusing to overwrite them."
else
    python scripts/tune_msipl_massnet_beta.py \
        --input "$INPUT" \
        --weights "$WEIGHTS" \
        --output "$TUNED_OUTPUT" \
        --target-peaks "$TARGET_PEAKS" \
        --tolerance 50 \
        --beta-min 0.0 \
        --beta-max 2.5 \
        --beta-step 0.05

    python scripts/evaluate_msipl_massnet_peaks.py \
        --input "$INPUT" \
        --peaks "$TUNED_OUTPUT/learned_peaks.csv" \
        --output "$TUNED_OUTPUT"
fi

echo "=== $DATASET COMPLETE ==="
echo "Target peaks: $TARGET_PEAKS"
echo "Fixed-Beta results: $FIXED_OUTPUT"
echo "Paper-aligned results: $TUNED_OUTPUT"

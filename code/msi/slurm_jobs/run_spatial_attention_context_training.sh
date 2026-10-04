#!/bin/bash
#SBATCH --job-name=attention-context
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/attention-context-%j.out
#SBATCH --error=logs/attention-context-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 SECTION {real_attention|shuffled_attention}" >&2
    exit 2
fi

DATASET="$1"
ARM="$2"
case "$DATASET" in
    40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5" ;;
    GBM108_positive|GBM108_negative|GBM12_1|GBM12_2|GBM22_1|GBM22_2|GBM39_1|GBM39_2)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5" ;;
    *) echo "Unsupported attention-context dataset: $DATASET" >&2; exit 2 ;;
esac
case "$ARM" in
    real_attention) VARIANT=attention ;;
    shuffled_attention) VARIANT=attention_shuffled ;;
    *) echo "Unsupported attention-context arm: $ARM" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_attention_context/${DATASET}_seed1/$ARM"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${DATASET}_seed1/$ARM"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [ ! -f "$INPUT" ]; then
    echo "Input does not exist: $INPUT" >&2
    exit 1
fi
if [ -f "$FINAL_CHECKPOINT" ]; then
    if grep -q '"status": "complete"' "$OUTPUT/summary.json" 2>/dev/null; then
        echo "Training is already complete: $DATASET $ARM"
        exit 0
    fi
    echo "Final checkpoint exists but complete summary is missing: $FINAL_CHECKPOINT" >&2
    exit 1
fi

if ! mkdir -p "$OUTPUT" "$CHECKPOINT_OUTPUT"; then
    # On the shared filesystem, simultaneous sibling directory creation can
    # return EEXIST even when both requested directories now exist.
    if [ ! -d "$OUTPUT" ] || [ ! -d "$CHECKPOINT_OUTPUT" ]; then
        echo "Could not prepare both output directories for $DATASET $ARM" >&2
        exit 1
    fi
fi
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; training stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

# This is a cheap synthetic check of the model/control wiring. It does not
# constitute a result on either tissue section.
python -m unittest discover -s src/spatial_msipl/tests -p test_attention_context_control.py
python -u scripts/validate_spatial_window_cache.py \
    --input "$INPUT" --window-size 3 --variant "$ARM"

RESUME_ARGUMENTS=()
if [ -f "$LATEST_CHECKPOINT" ]; then
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
    echo "Resuming $DATASET $ARM from epoch checkpoint"
fi

python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --window-size 3 \
    --attention-dim 8 \
    --attention-input-scale sqrt_bins \
    --context-seed 1701 \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda 0 \
    --seed 1 \
    --checkpoint-interval 5 \
    --cache-spectra \
    "${RESUME_ARGUMENTS[@]}"

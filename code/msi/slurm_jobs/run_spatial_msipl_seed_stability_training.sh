#!/bin/bash
#SBATCH --job-name=spatial-seed
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/spatial-seed-%j.out
#SBATCH --error=logs/spatial-seed-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 {central_only|uniform_mean|attention_sqrt_bins} {2|3}" >&2
    exit 2
fi

LABEL="$1"
SEED="$2"
case "$LABEL" in
    central_only|uniform_mean|attention_sqrt_bins) ;;
    *)
        echo "Unknown stability variant: $LABEL" >&2
        exit 2
        ;;
esac
case "$SEED" in
    2|3) ;;
    *)
        echo "Training-seed stability is predeclared for seeds 2 and 3." >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_training_seed_stability/GBM108_positive_seed${SEED}/${LABEL}"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/seed_stability/GBM108_positive_seed${SEED}/${LABEL}"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [ ! -f "$INPUT" ]; then
    echo "Input does not exist: $INPUT" >&2
    exit 1
fi
if [ -f "$FINAL_CHECKPOINT" ]; then
    echo "Completed checkpoint already exists; nothing to do: $FINAL_CHECKPOINT"
    exit 0
fi

mkdir -p "$PROJECT_ROOT/logs" "$CHECKPOINT_OUTPUT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python - <<'PY'
import json
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable; seed-stability training stopped before loading the model.")
device = torch.device("cuda:0")
left = torch.randn((1024, 1024), device=device)
right = left @ left.T
torch.cuda.synchronize()
print(json.dumps({"cuda_warmup": "passed", "checksum": float(right[0, 0])}), flush=True)
PY

RESUME_ARGUMENTS=()
if [ -f "$LATEST_CHECKPOINT" ]; then
    echo "Resuming $LABEL seed $SEED from: $LATEST_CHECKPOINT"
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
else
    echo "Starting $LABEL with training seed $SEED"
fi

MODEL_VARIANT="$LABEL"
ATTENTION_ARGUMENTS=()
if [ "$LABEL" = "attention_sqrt_bins" ]; then
    MODEL_VARIANT="attention"
    ATTENTION_ARGUMENTS=(--attention-input-scale sqrt_bins)
fi

python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$MODEL_VARIANT" \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --attention-dim 8 \
    --learning-rate 0.001 \
    --spatial-lambda 0 \
    --seed "$SEED" \
    --checkpoint-interval 5 \
    "${ATTENTION_ARGUMENTS[@]}" \
    "${RESUME_ARGUMENTS[@]}"


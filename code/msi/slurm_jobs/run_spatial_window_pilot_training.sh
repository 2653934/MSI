#!/bin/bash
#SBATCH --job-name=spatial-window
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/spatial-window-%j.out
#SBATCH --error=logs/spatial-window-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 {GBM108_positive|40TopL} {uniform_p5|zero_p3|shuffled_p3}" >&2
    exit 2
fi

DATASET="$1"
ARM="$2"
case "$DATASET" in
    GBM108_positive) INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5" ;;
    40TopL) INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5" ;;
    *) echo "Unknown pilot dataset: $DATASET" >&2; exit 2 ;;
esac
case "$ARM" in
    uniform_p5) VARIANT=uniform_mean; WINDOW_SIZE=5 ;;
    zero_p3) VARIANT=zero_context; WINDOW_SIZE=3 ;;
    shuffled_p3) VARIANT=shuffled_uniform; WINDOW_SIZE=3 ;;
    *) echo "Unknown pilot arm: $ARM" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_window_pilot/${DATASET}_seed1/$ARM"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${DATASET}_seed1/$ARM"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [ ! -f "$INPUT" ]; then
    echo "Input does not exist: $INPUT" >&2
    exit 1
fi
if [ -f "$FINAL_CHECKPOINT" ]; then
    echo "Final checkpoint exists; refusing to overwrite: $FINAL_CHECKPOINT"
    exit 0
fi

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; no pilot model was loaded or trained")
device = torch.device("cuda:0")
probe = torch.ones((32, 32), device=device)
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(device)}: {float(probe.sum())}", flush=True)
PY

RESUME_ARGUMENTS=()
if [ -f "$LATEST_CHECKPOINT" ]; then
    echo "Resuming $DATASET $ARM from $LATEST_CHECKPOINT"
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
else
    echo "Starting $DATASET $ARM"
fi

python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --window-size "$WINDOW_SIZE" \
    --context-seed 1701 \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda 0 \
    --seed 1 \
    --checkpoint-interval 5 \
    "${RESUME_ARGUMENTS[@]}"

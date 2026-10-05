#!/bin/bash
#SBATCH --job-name=attention-rank-all
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --exclusive
#SBATCH --output=logs/attention-rank-all-%A_%a.out
#SBATCH --error=logs/attention-rank-all-%A_%a.err

set -eo pipefail

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
MATCHED_COUNTS=(315 210 221 255 245 247 133 232 530 458 453 478 589 464 686 523)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_spatial_attention_frozen_ranking_campaign.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#DATASETS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2
    exit 2
fi
DATASET="${DATASETS[TASK_ID]}"
MATCHED_COUNT="${MATCHED_COUNTS[TASK_ID]}"
PROJECT_ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${DATASET}_seed1/real_attention/checkpoint.pt"
REAL_ROOT="$PROJECT_ROOT/results/experiments/spatial_attention_context/${DATASET}_seed1/real_attention"
SWAP_SUMMARY="$PROJECT_ROOT/results/diagnostics/spatial_attention_input_swap/$DATASET/summary.json"
OUTPUT="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$DATASET"

case "$DATASET" in
    *TopL) INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5" ;;
    GBM*) INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5" ;;
esac

echo "=== $DATASET: frozen attention ranking swap on ${SLURMD_NODENAME:-unknown} ==="
if grep -q '"status": "valid"' "$OUTPUT/summary.json" 2>/dev/null &&
   [ -f "$OUTPUT/rankings.npz" ]; then
    echo "Already valid: $OUTPUT/summary.json"
    exit 0
fi
for required in "$INPUT" "$CHECKPOINT" "$SWAP_SUMMARY" "$REAL_ROOT/summary.json"; do
    if [ ! -f "$required" ]; then
        echo "Missing frozen input: $required" >&2
        exit 1
    fi
done
if ! grep -q '"status": "valid"' "$SWAP_SUMMARY"; then
    echo "Original input-swap audit is not valid: $SWAP_SUMMARY" >&2
    exit 1
fi
if ! grep -q '"status": "complete"' "$REAL_ROOT/summary.json"; then
    echo "Training is incomplete: $REAL_ROOT/summary.json" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
# Only the two pilots already have real-input attribution and peak evaluation.
# For the other sections this reuses the frozen 100-epoch checkpoint but runs
# the same original real-input GMM/IG/peak evaluator before the intervention.
if ! grep -q '"status": "valid"' "$REAL_ROOT/attribution/summary.json" 2>/dev/null ||
   ! grep -q '"status": "complete"' "$REAL_ROOT/peak_evaluation/summary.json" 2>/dev/null; then
    echo "Preparing missing real-input attribution and matched peak evaluation"
    bash slurm_jobs/run_spatial_attention_context_evaluation.sh "$DATASET" real_attention
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4

python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; frozen ranking swap stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

python -m unittest discover -s src/spatial_msipl/tests -p test_attention_frozen_ranking_swap.py
python -u scripts/evaluate_spatial_attention_frozen_ranking_swap.py \
    --input "$INPUT" --checkpoint "$CHECKPOINT" \
    --attribution-dir "$REAL_ROOT/attribution" \
    --peak-evaluation-summary "$REAL_ROOT/peak_evaluation/summary.json" \
    --input-swap-summary "$SWAP_SUMMARY" \
    --output "$OUTPUT" --matched-count "$MATCHED_COUNT"

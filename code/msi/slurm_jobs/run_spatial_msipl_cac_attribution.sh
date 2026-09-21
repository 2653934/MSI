#!/bin/bash
#SBATCH --job-name=cac-ig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=16G
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/cac-ig-%j.out
#SBATCH --error=logs/cac-ig-%j.err

set -eo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: sbatch $0 DATASET MATCHED_PEAK_COUNT [uniform_mean|central_only]" >&2
    exit 2
fi

DATASET="$1"
MATCHED_COUNT="$2"
VARIANT="${3:-uniform_mean}"
case "$DATASET:$MATCHED_COUNT" in
    40TopL:315|160TopL:210|200TopL:221|240TopL:255|280TopL:245|360TopL:247|400TopL:133|520TopL:232) ;;
    *)
        echo "Unknown CAC dataset/count pair: $DATASET:$MATCHED_COUNT" >&2
        exit 2
        ;;
esac
case "$VARIANT" in
    uniform_mean|central_only) ;;
    *)
        echo "Unknown attribution variant: $VARIANT" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5"
if [ "$VARIANT" = "central_only" ]; then
    CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac/reconstruction/${DATASET}_seed1/central_only/checkpoint.pt"
else
    CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac/production/${DATASET}_seed1/uniform_mean/checkpoint.pt"
fi
ATTRIBUTION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_cac_gmm_integrated_gradients/${DATASET}_seed1/${VARIANT}"
LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/cac/$DATASET"
EVALUATION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_cac_attributed_peak_evaluation/${DATASET}_seed1/${VARIANT}"
MAX_CUDA_RETRIES=4
CUDA_RETRY_COUNT="${CUDA_RETRY_COUNT:-0}"
CUDA_RETRY_ROOT="${CUDA_RETRY_ROOT:-$SLURM_JOB_ID}"
FAILED_NODES_FILE="$PROJECT_ROOT/logs/cac-ig-${VARIANT}-${CUDA_RETRY_ROOT}.failed_nodes"
CUDA_QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"

mkdir -p \
    "$PROJECT_ROOT/logs" \
    "$ATTRIBUTION_OUTPUT" \
    "$EVALUATION_OUTPUT"
if grep -q '"status": "complete"' "$EVALUATION_OUTPUT/summary.json" 2>/dev/null; then
    echo "$DATASET $VARIANT already has a complete attribution evaluation; nothing to do."
    exit 0
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

if ! python - <<'PY'
import json
import torch

if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable")
device = torch.device("cuda:0")
left = torch.randn((1024, 1024), device=device)
right = left @ left.T
checksum = float(right[0, 0].item())
torch.cuda.synchronize()
print(json.dumps({
    "cuda_warmup": "passed",
    "device": torch.cuda.get_device_name(device),
    "checksum": checksum,
}), flush=True)
PY
then
    failed_node="${SLURMD_NODENAME:-$(hostname -s)}"
    echo "$failed_node" >> "$FAILED_NODES_FILE"
    echo "CUDA warm-up failed on $failed_node (attempt $((CUDA_RETRY_COUNT + 1)))." >&2
    if (( CUDA_RETRY_COUNT >= MAX_CUDA_RETRIES )); then
        echo "CUDA retry limit reached; inspect manually." >&2
        exit 1
    fi

    combined_excludes=$( \
        { \
            if [ -f "$CUDA_QUARANTINE_FILE" ]; then
                sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
                    "$CUDA_QUARANTINE_FILE"
            fi
            cat "$FAILED_NODES_FILE"
        } | sort -u | paste -sd, - \
    )
    next_retry=$((CUDA_RETRY_COUNT + 1))
    replacement_submission=$(sbatch \
        --exclude="$combined_excludes" \
        --export="ALL,CUDA_RETRY_COUNT=$next_retry,CUDA_RETRY_ROOT=$CUDA_RETRY_ROOT" \
        --job-name="${SLURM_JOB_NAME:-cac-ig}" \
        --output="logs/cac-ig-${VARIANT}-%j.out" \
        --error="logs/cac-ig-${VARIANT}-%j.err" \
        "$PROJECT_ROOT/slurm_jobs/run_spatial_msipl_cac_attribution.sh" \
        "$DATASET" "$MATCHED_COUNT" "$VARIANT")
    echo "Submitted replacement ${replacement_submission##* } excluding $combined_excludes." >&2
    exit 0
fi

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
if grep -q '"status": "valid"' "$ATTRIBUTION_OUTPUT/summary.json" 2>/dev/null; then
    echo "Reusing complete attribution artifacts: $ATTRIBUTION_OUTPUT"
else
    python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" \
        --checkpoint "$CHECKPOINT" \
        --output "$ATTRIBUTION_OUTPUT" \
        --variant "$VARIANT" \
        --batch-size 64 \
        --gmm-components 3 \
        --gmm-n-init 20 \
        --attribution-per-cluster 12 \
        --faithfulness-per-cluster 32 \
        --ig-steps 64 \
        --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 \
        --random-repeats 10 \
        --top-candidates 50 \
        --seed 1 \
        --sampling-seed 1
fi

python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$INPUT" \
    --attribution-dir "$ATTRIBUTION_OUTPUT" \
    --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
    --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
    --output "$EVALUATION_OUTPUT" \
    --matched-count "$MATCHED_COUNT" \
    --peak-tolerance-ppm 10 \
    --consolidated-candidates 50 \
    --ion-images 12 \
    --chunk-size 1024

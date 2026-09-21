#!/bin/bash
#SBATCH --job-name=gbm-ig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/gbm-ig-%j.out
#SBATCH --error=logs/gbm-ig-%j.err

set -eo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: sbatch $0 DATASET MATCHED_PEAK_COUNT [uniform_mean|central_only|depthwise|attention|attention_sqrt_bins]" >&2
    exit 2
fi

DATASET="$1"
MATCHED_COUNT="$2"
VARIANT="${3:-uniform_mean}"
case "$DATASET:$MATCHED_COUNT" in
    GBM108_positive:530|GBM108_negative:458|GBM12_1:453|GBM12_2:478|GBM22_1:589|GBM22_2:464|GBM39_1:686|GBM39_2:523) ;;
    *)
        echo "Unknown dataset/count pair: $DATASET:$MATCHED_COUNT" >&2
        exit 2
        ;;
esac
case "$VARIANT" in
    uniform_mean|central_only|depthwise|attention|attention_sqrt_bins) ;;
    *)
        echo "Unknown attribution variant: $VARIANT" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
if [ "$VARIANT" = "central_only" ]; then
    CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/reconstruction/${DATASET}_seed1/central_only/checkpoint.pt"
else
    CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/${DATASET}_seed1/${VARIANT}/checkpoint.pt"
fi
ATTRIBUTION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/${VARIANT}"
LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet/$DATASET"
EVALUATION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed1/${VARIANT}"
MAX_CUDA_RETRIES=4
CUDA_RETRY_COUNT="${CUDA_RETRY_COUNT:-0}"
CUDA_RETRY_ROOT="${CUDA_RETRY_ROOT:-$SLURM_JOB_ID}"
FAILED_NODES_FILE="$PROJECT_ROOT/logs/gbm-ig-${VARIANT}-${CUDA_RETRY_ROOT}.failed_nodes"
CUDA_QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"

mkdir -p "$PROJECT_ROOT/logs"

if grep -q '"status": "complete"' "$EVALUATION_OUTPUT/summary.json" 2>/dev/null; then
    echo "$DATASET already has a complete attribution evaluation; nothing to do."
    exit 0
fi

if [ ! -f "$CHECKPOINT" ]; then
    echo "Required 100-epoch checkpoint is missing: $CHECKPOINT" >&2
    exit 1
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
        echo "CUDA retry limit reached; job will fail for manual inspection." >&2
        exit 1
    fi

    combined_excludes=""
    while IFS= read -r node; do
        [ -n "$node" ] || continue
        case ",$combined_excludes," in
            *",$node,"*) ;;
            *)
                if [ -z "$combined_excludes" ]; then
                    combined_excludes="$node"
                else
                    combined_excludes="$combined_excludes,$node"
                fi
                ;;
        esac
    done < <(
        {
            if [ -f "$CUDA_QUARANTINE_FILE" ]; then
                sed -e 's/\r$//' \
                    -e 's/#.*$//' \
                    -e '/^[[:space:]]*$/d' \
                    "$CUDA_QUARANTINE_FILE"
            fi
            cat "$FAILED_NODES_FILE"
        } | sort -u
    )

    next_retry=$((CUDA_RETRY_COUNT + 1))
    export_spec="ALL,CUDA_RETRY_COUNT=$next_retry,CUDA_RETRY_ROOT=$CUDA_RETRY_ROOT"
    if [ -n "${GBM_GATE_JOB_ID:-}" ]; then
        export_spec+=",GBM_GATE_JOB_ID=$GBM_GATE_JOB_ID"
    fi

    echo "Submitting a replacement and excluding: $combined_excludes" >&2
    if ! replacement_submission=$(sbatch \
        --exclude="$combined_excludes" \
        --export="$export_spec" \
        --job-name="${SLURM_JOB_NAME:-gbm-ig}" \
        --output="logs/gbm-ig-${VARIANT}-%j.out" \
        --error="logs/gbm-ig-${VARIANT}-%j.err" \
        "$PROJECT_ROOT/slurm_jobs/run_spatial_msipl_gbm_attribution.sh" \
        "$DATASET" "$MATCHED_COUNT" "$VARIANT"); then
        echo "Replacement submission failed; rerun manually with the recorded exclusions." >&2
        exit 1
    fi
    replacement_job=${replacement_submission##* }

    if [ -n "${GBM_GATE_JOB_ID:-}" ]; then
        if ! scontrol update \
            JobId="$GBM_GATE_JOB_ID" \
            Dependency="afterok:$replacement_job"; then
            echo "Could not repoint gate job $GBM_GATE_JOB_ID to replacement $replacement_job." >&2
            scancel "$replacement_job" || true
            exit 1
        fi
        echo "Gate job $GBM_GATE_JOB_ID now waits for replacement $replacement_job." >&2
    fi

    echo "Submitted replacement job $replacement_job (retry $next_retry/$MAX_CUDA_RETRIES)." >&2
    exit 0
fi

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" \
    --checkpoint "$CHECKPOINT" \
    --output "$ATTRIBUTION_OUTPUT" \
    --variant "$VARIANT" \
    --batch-size 64 \
    --gmm-components 2 \
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

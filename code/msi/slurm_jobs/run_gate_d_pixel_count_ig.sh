#!/bin/bash
# Gate (d) attribution-pixel-count test: one IG run for one development section,
# arm and pixel count. Protocol 18 Section 6 ("Pixel-count run specification").
# Identical to the production IG invocation except --attribution-total N, and
# written to its own output root so production artifacts are never touched.
# Real CUDA warm-up; on failure the node is excluded (together with
# slurm_jobs/gpu_cuda_quarantine.txt) and a replacement is submitted.
# Submit through slurm_jobs/submit_gate_d_pixel_counts.sh.
#SBATCH --job-name=gate-d-ig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --exclusive
#SBATCH --open-mode=append
#SBATCH --output=logs/gate-d-ig-%j.out
#SBATCH --error=logs/gate-d-ig-%j.err

set -eo pipefail

if [ "$#" -ne 3 ]; then
    echo "Usage: sbatch $0 GBM108_positive|40TopL central_only|uniform_mean 12|48|192" >&2
    exit 2
fi
DATASET="$1"
VARIANT="$2"
TOTAL="$3"
case "$DATASET" in
    GBM108_positive)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
        CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl"
        GMM_COMPONENTS=2 ;;
    40TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5"
        CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac"
        GMM_COMPONENTS=3 ;;
    *) echo "Gate (d) sections are GBM108_positive and 40TopL only: $DATASET" >&2; exit 2 ;;
esac
case "$VARIANT" in
    central_only) CHECKPOINT="$CHECKPOINT_ROOT/reconstruction/${DATASET}_seed1/central_only/checkpoint.pt" ;;
    uniform_mean) CHECKPOINT="$CHECKPOINT_ROOT/production/${DATASET}_seed1/uniform_mean/checkpoint.pt" ;;
    *) echo "Unknown arm: $VARIANT" >&2; exit 2 ;;
esac
case "$TOTAL" in
    12|48|192) ;;
    *) echo "Pixel count must be 12, 48 or 192: $TOTAL" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/diagnostics/gate_d_pixel_counts/${DATASET}_seed1/${VARIANT}/n${TOTAL}"
MAX_CUDA_RETRIES=4
CUDA_RETRY_COUNT="${CUDA_RETRY_COUNT:-0}"
CUDA_RETRY_ROOT="${CUDA_RETRY_ROOT:-$SLURM_JOB_ID}"
FAILED_NODES_FILE="$PROJECT_ROOT/logs/gate-d-ig-${DATASET}-${VARIANT}-n${TOTAL}-${CUDA_RETRY_ROOT}.failed_nodes"
CUDA_QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
cd "$PROJECT_ROOT"
mkdir -p logs

# Never overwrite or silently reuse: a finished run is left alone, and any
# other existing content must be moved aside by a person.
if [ -f "$OUTPUT/summary.json" ]; then
    echo "$OUTPUT already has a summary.json; nothing to do (move it aside to rerun)."
    exit 0
fi
if [ -d "$OUTPUT" ] && [ -n "$(ls -A "$OUTPUT")" ]; then
    echo "STALE: $OUTPUT has files but no summary.json; move it aside before rerunning." >&2
    exit 3
fi
if [ ! -f "$CHECKPOINT" ]; then
    echo "Required checkpoint is missing: $CHECKPOINT" >&2
    exit 1
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
# scripts/ is needed by the test suite (several tests import audit scripts);
# pilot jobs 66286-66291 failed at the test step without it.
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
echo "=== gate (d) IG: $DATASET $VARIANT n=$TOTAL on ${SLURMD_NODENAME:-unknown} (job $SLURM_JOB_ID, retry $CUDA_RETRY_COUNT) ==="

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
    combined_excludes=$(
        {
            if [ -f "$CUDA_QUARANTINE_FILE" ]; then
                sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' "$CUDA_QUARANTINE_FILE"
            fi
            cat "$FAILED_NODES_FILE"
        } | sort -u | paste -sd, -
    )
    next_retry=$((CUDA_RETRY_COUNT + 1))
    echo "Submitting a replacement and excluding: $combined_excludes" >&2
    # The replacement keeps this job's partition, memory and time limit.
    if ! replacement=$(sbatch --parsable \
        --partition="$SLURM_JOB_PARTITION" \
        --mem="${GATE_D_MEM:?}" \
        --time="${GATE_D_TIME:?}" \
        --exclude="$combined_excludes" \
        --export="ALL,CUDA_RETRY_COUNT=$next_retry,CUDA_RETRY_ROOT=$CUDA_RETRY_ROOT" \
        --job-name="gate-d-ig-${DATASET}-${VARIANT}-n${TOTAL}" \
        "$PROJECT_ROOT/slurm_jobs/run_gate_d_pixel_count_ig.sh" \
        "$DATASET" "$VARIANT" "$TOTAL"); then
        echo "Replacement submission failed; rerun manually with the recorded exclusions." >&2
        exit 1
    fi
    echo "Submitted replacement job ${replacement%%;*} (retry $next_retry/$MAX_CUDA_RETRIES)." >&2
    exit 0
fi

python -m unittest discover -s src/spatial_msipl/tests -v
# Record elapsed time and peak RSS of the IG process when GNU time exists.
timed() {
    local record="$1"; shift
    if [ -x /usr/bin/time ]; then
        /usr/bin/time -v -o "$record" "$@"
    else
        echo "GNU time unavailable; use sacct Elapsed/MaxRSS" > "$record"
        "$@"
    fi
}
# Everything except --attribution-total matches the production IG invocation
# (run_spatial_msipl_gbm_attribution.sh / run_spatial_msipl_cac_attribution.sh).
timed "logs/gate-d-ig-${SLURM_JOB_ID}.resources.txt" \
python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" \
    --checkpoint "$CHECKPOINT" \
    --output "$OUTPUT" \
    --variant "$VARIANT" \
    --batch-size 64 \
    --gmm-components "$GMM_COMPONENTS" \
    --gmm-n-init 20 \
    --attribution-per-cluster 12 \
    --attribution-total "$TOTAL" \
    --faithfulness-per-cluster 32 \
    --ig-steps 64 \
    --ig-internal-batch-size 8 \
    --deletion-budgets 32 128 512 \
    --random-repeats 10 \
    --top-candidates 50 \
    --seed 1 \
    --sampling-seed 1

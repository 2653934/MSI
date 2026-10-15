#!/bin/bash
# Item E (supervisor chat 2026-10-15 13:00, 15:35): uniform 7x7 and 9x9 windows,
# trained exactly like the existing uniform_p5 arm (uniform_mean, seed 1, 100
# epochs, batch 128, lr 1e-3, context seed 1701 unused for measured context;
# cached loader on GBM, streaming on CAC, as for uniform_p5), then
# reconstruction, GMM+IG and matched peak evaluation at the production K_bin.
# One array task per section-arm: 0-15 uniform_p7, 16-31 uniform_p9.
# Requires the passed 7x7/9x9 data-contract audit (68632). Status lines only.
#SBATCH --job-name=window-e79
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=16:00:00
#SBATCH --exclusive
#SBATCH --output=logs/window-e79-%A_%a.out
#SBATCH --error=logs/window-e79-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_window_e79_campaign.sh}"
if (( TASK_ID >= 0 && TASK_ID < 16 )); then
    DATASET="${FAIR_SECTIONS[TASK_ID]}"; ARM=uniform_p7; WINDOW=7
elif (( TASK_ID >= 16 && TASK_ID < 32 )); then
    DATASET="${FAIR_SECTIONS[TASK_ID - 16]}"; ARM=uniform_p9; WINDOW=9
else
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
INPUT="$(fair_input_for "$DATASET")"
case "$DATASET" in
    GBM*) LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned/$DATASET"
          GMM_COMPONENTS=2; CACHE_ARGUMENTS=(--cache-spectra) ;;
    *)    LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/cac/$DATASET"
          GMM_COMPONENTS=3; CACHE_ARGUMENTS=() ;;
esac
case "$DATASET" in
    GBM108_positive) K_BIN=584 ;; GBM108_negative) K_BIN=940 ;; GBM12_1) K_BIN=691 ;;
    GBM12_2) K_BIN=986 ;; GBM22_1) K_BIN=834 ;; GBM22_2) K_BIN=1028 ;;
    GBM39_1) K_BIN=695 ;; GBM39_2) K_BIN=911 ;;
    40TopL) K_BIN=315 ;; 160TopL) K_BIN=210 ;; 200TopL) K_BIN=221 ;; 240TopL) K_BIN=255 ;;
    280TopL) K_BIN=245 ;; 360TopL) K_BIN=247 ;; 400TopL) K_BIN=133 ;; 520TopL) K_BIN=232 ;;
esac
RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_window_e79/${DATASET}_seed1/$ARM"
CHECKPOINT_DIR="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_e79/${DATASET}_seed1/$ARM"
CHECKPOINT="$CHECKPOINT_DIR/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_DIR/checkpoint_latest.pt"
AUDIT="$PROJECT_ROOT/results/diagnostics/spatial_msipl_data_contract_windows"
for section in 40TopL 280TopL GBM108_positive GBM22_2; do
    grep -q '"status": "valid"' "$AUDIT/$section/summary.json" \
        || { echo "7x7/9x9 audit not valid for $section; E training refused" >&2; exit 1; }
done
for required in "$INPUT" "$LEGACY_DIR/peak_metrics.json" "$LEGACY_DIR/learned_peaks.csv"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
mkdir -p "$RESULT_ROOT" "$CHECKPOINT_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

"$PYTHON" - "$LEGACY_DIR/peak_metrics.json" "$K_BIN" <<'PY'
import json, sys
count = int(json.load(open(sys.argv[1]))["unique_nearest_bins"])
if count != int(sys.argv[2]):
    sys.exit(f"legacy unique_nearest_bins {count} != K_bin {sys.argv[2]}")
PY
"$PYTHON" - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

if [ -f "$CHECKPOINT" ] && grep -q '"status": "complete"' "$RESULT_ROOT/summary.json" 2>/dev/null; then
    echo "Training already complete"
elif [ -f "$CHECKPOINT" ]; then
    echo "Final checkpoint exists without a complete summary: $CHECKPOINT" >&2; exit 1
else
    if [ "${#CACHE_ARGUMENTS[@]}" -gt 0 ]; then
        "$PYTHON" -u scripts/validate_spatial_window_cache.py --input "$INPUT" \
            --window-size "$WINDOW" --variant "$ARM" > "$RESULT_ROOT/cache_validation.log"
    fi
    RESUME_ARGUMENTS=()
    [ -f "$LATEST_CHECKPOINT" ] && RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
    "$PYTHON" -u scripts/train_spatial_msipl_production.py \
        --input "$INPUT" --output "$RESULT_ROOT" --checkpoint-output "$CHECKPOINT_DIR" \
        --variant uniform_mean --window-size "$WINDOW" --context-seed 1701 \
        --epochs 100 --batch-size 128 --hidden-dim 512 --latent-dim 5 \
        --learning-rate 0.001 --spatial-lambda 0 --seed 1 --checkpoint-interval 5 \
        "${CACHE_ARGUMENTS[@]}" "${RESUME_ARGUMENTS[@]}" > "$RESULT_ROOT/training_stdout.log"
    echo "Training finished"
fi

"$PYTHON" - "$CHECKPOINT" "$WINDOW" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
checkpoint = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
spec = checkpoint_input_spec(checkpoint)
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("not a complete 100-epoch checkpoint")
if checkpoint["model_configuration"]["neighbourhood"].get("name") != "uniform_mean":
    sys.exit("checkpoint is not a uniform_mean model")
if spec["window_size"] != int(sys.argv[2]) or spec["context_mode"] != "measured":
    sys.exit("checkpoint window or context does not match the arm")
if checkpoint["resume_signature"].get("seed") != 1 or "centre_mask_probability" in checkpoint["resume_signature"]:
    sys.exit("checkpoint is not the seed-1 unmasked run")
print("Checkpoint verified", flush=True)
PY

if [ ! -f "$RESULT_ROOT/reconstruction/reconstruction.json" ]; then
    "$PYTHON" -u scripts/evaluate_spatial_window_reconstruction.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" --output "$RESULT_ROOT/reconstruction" \
        --variant uniform_mean --batch-size 64 > "$RESULT_ROOT/reconstruction_stdout.log"
fi
if ! grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RESULT_ROOT/attribution" --variant uniform_mean \
        --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
        --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
        --ig-steps 64 --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 --random-repeats 10 \
        --top-candidates 50 --seed 1 --sampling-seed 1 > "$RESULT_ROOT/attribution_stdout.log"
fi
grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" \
    || { echo "IG status is not valid; peak evaluation not run" >&2; exit 4; }
if ! grep -q '"status": "complete"' "$RESULT_ROOT/peak_evaluation/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
        --input "$INPUT" --attribution-dir "$RESULT_ROOT/attribution" \
        --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
        --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
        --output "$RESULT_ROOT/peak_evaluation" --matched-count "$K_BIN" \
        --peak-tolerance-ppm 10 --consolidated-candidates 50 \
        --ion-images 12 --chunk-size 1024 > "$RESULT_ROOT/peak_evaluation_stdout.log"
fi
echo "=== $DATASET $ARM complete ==="

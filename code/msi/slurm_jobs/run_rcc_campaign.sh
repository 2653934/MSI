#!/bin/bash
# RCC steps 2-4 (protocol 18 Section 6.1, item D step 2): train one run-arm
# exactly as the CAC production arms (3x3, 100 epochs, seed 1, streaming loader),
# then GMM K = 3 + IG with the CAC settings, then matched evaluation at
# K_bin = |R@0.4| (from run_rcc_preparation.sh) without legacy msiPL.
# Array: 0-7 central_only, 8-15 uniform_mean (rcc_sections.sh). Status lines only;
# every scientific script logs into the result folder.
# Predeclared: a GMM component below 44 pixels (12 + 32) stops IG by design; the
# run-arm is then reported "not done", and no setting is changed.
#SBATCH --job-name=rcc-campaign
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --exclusive
#SBATCH --output=logs/rcc-campaign-%A_%a.out
#SBATCH --error=logs/rcc-campaign-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_rcc.sh}"
if (( TASK_ID < 0 || TASK_ID >= 2 * ${#RCC_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${RCC_SECTIONS[TASK_ID % 8]}"
ARM="${RCC_ARMS[TASK_ID / 8]}"
INPUT="$(rcc_input_for "$DATASET")"
SECTION_ROOT="$PROJECT_ROOT/results/experiments/rcc_spatial_msipl/${DATASET}_seed1"
RESULT_ROOT="$SECTION_ROOT/$ARM"
BUDGET="$SECTION_ROOT/reference_budget.json"
CHECKPOINT_DIR="/datasets/zsuliman/msi_checkpoints/spatial_msipl/rcc/${DATASET}_seed1/$ARM"
CHECKPOINT="$CHECKPOINT_DIR/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_DIR/checkpoint_latest.pt"
[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }
grep -q '"status": "complete"' "$BUDGET" 2>/dev/null \
    || { echo "Reference budget missing or incomplete: $BUDGET (run preparation first)" >&2; exit 1; }
mkdir -p "$RESULT_ROOT" "$CHECKPOINT_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

K_BIN="$("$PYTHON" -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["K_bin"]))' "$BUDGET")"
echo "K_bin = |R@0.4| = $K_BIN"
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
    RESUME_ARGUMENTS=()
    [ -f "$LATEST_CHECKPOINT" ] && RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
    "$PYTHON" -u scripts/train_spatial_msipl_production.py \
        --input "$INPUT" --output "$RESULT_ROOT" --checkpoint-output "$CHECKPOINT_DIR" \
        --variant "$ARM" --epochs 100 --batch-size 128 --hidden-dim 512 --latent-dim 5 \
        --learning-rate 0.001 --spatial-lambda 0 --seed 1 --checkpoint-interval 5 \
        "${RESUME_ARGUMENTS[@]}" > "$RESULT_ROOT/training_stdout.log"
    echo "Training finished"
fi

"$PYTHON" - "$CHECKPOINT" "$ARM" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
checkpoint = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
spec = checkpoint_input_spec(checkpoint)
configuration = checkpoint["model_configuration"]
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("not a complete 100-epoch checkpoint")
if sys.argv[2] == "central_only":
    if configuration.get("input_mode") != "central_only" or "neighbourhood" in configuration:
        sys.exit("checkpoint is not a central_only model")
elif configuration.get("neighbourhood", {}).get("name") != "uniform_mean":
    sys.exit("checkpoint is not a uniform_mean model")
if spec["window_size"] != 3 or spec["context_mode"] != "measured":
    sys.exit("checkpoint window or context does not match the arm")
if checkpoint["resume_signature"].get("seed") != 1 or "centre_mask_probability" in checkpoint["resume_signature"]:
    sys.exit("checkpoint is not the seed-1 unmasked run")
print("Checkpoint verified", flush=True)
PY

if ! grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RESULT_ROOT/attribution" --variant "$ARM" \
        --batch-size 64 --gmm-components "$RCC_GMM_COMPONENTS" --gmm-n-init 20 \
        --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
        --ig-steps 64 --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 --random-repeats 10 \
        --top-candidates 50 --seed 1 --sampling-seed 1 > "$RESULT_ROOT/attribution_stdout.log" \
        || { echo "IG stopped (see attribution_stdout.log; a GMM component below 44 px is reported as not done)" >&2; exit 4; }
fi
grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" \
    || { echo "IG status is not valid; peak evaluation not run" >&2; exit 4; }
if ! grep -q '"status": "complete"' "$RESULT_ROOT/peak_evaluation/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
        --input "$INPUT" --attribution-dir "$RESULT_ROOT/attribution" --no-legacy \
        --output "$RESULT_ROOT/peak_evaluation" --matched-count "$K_BIN" \
        --peak-tolerance-ppm 10 --consolidated-candidates 50 \
        --ion-images 12 --chunk-size 1024 > "$RESULT_ROOT/peak_evaluation_stdout.log"
fi
echo "=== $DATASET $ARM complete ==="

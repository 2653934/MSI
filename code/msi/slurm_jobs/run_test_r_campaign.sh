#!/bin/bash
# Test R (protocol 18 Section 6.3; supervisor chat 2026-10-17 09:45): training-seed
# replication of the core arms. One array task per section-arm, for one training
# seed (2 or 3):
#   sbatch --array=0-47 slurm_jobs/run_test_r_campaign.sh SEED   (via submit_test_r.sh)
# Index i: section TEST_R_SECTIONS[i / 2] (RCC 0-15, CAC 16-31, GBM 32-47),
# arm TEST_R_ARMS[i % 2].
# Identical to the production seed-1 runs except the training seed (model
# initialisation and sample order): 3x3, 100 epochs, batch 128, hidden 512,
# latent 5, lr 1e-3, spatial_lambda 0, cached loader (--cache-spectra; validated
# equivalent to streaming, investigation 10), real CUDA warm-up, quarantine
# excluded at submit time. Then GMM (production K, n_init 20, GMM seed 1) + IG
# (sampling seed 1, 12 px/component, 64 steps), exactly the RCC campaign's IG call,
# and the matched evaluation at the production K_bin: GBM/CAC with the legacy list
# (as run_centremask_campaign.sh), RCC at the released target without legacy (as
# run_rcc_campaign.sh).
# Predeclared: a GMM component below 44 px stops IG by design, and an IG status
# other than valid makes the seed-arm "not done" (exit 4); no setting changes.
# Appends node_record.json (node, GPU model, CPU model) for the runtime table v2
# (supervisor chat 2026-10-17 09:48). Outputs never overwrite seed 1.
#SBATCH --job-name=test-r
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=06:00:00
#SBATCH --exclusive
#SBATCH --output=logs/test-r-%A_%a.out
#SBATCH --error=logs/test-r-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/test_r_sections.sh"
SEED="${1:?Usage: sbatch --array=0-47 $0 SEED}"
test_r_check_seed "$SEED"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_test_r.sh}"
if (( TASK_ID < 0 || TASK_ID >= 2 * ${#TEST_R_SECTIONS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
DATASET="${TEST_R_SECTIONS[TASK_ID / 2]}"
ARM="${TEST_R_ARMS[TASK_ID % 2]}"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
GMM_COMPONENTS="$(test_r_gmm_components "$DATASET")"
RESULT_ROOT="$(test_r_result_root "$DATASET" "$SEED" "$ARM")"
CHECKPOINT_DIR="$(test_r_checkpoint_dir "$DATASET" "$SEED" "$ARM")"
CHECKPOINT="$CHECKPOINT_DIR/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_DIR/checkpoint_latest.pt"
[ -f "$INPUT" ] || { echo "Missing input: $INPUT" >&2; exit 1; }
if [ "$COLLECTION" = RCC ]; then
    BUDGET="$(test_r_rcc_budget "$DATASET")"
    grep -q '"status": "complete"' "$BUDGET" 2>/dev/null \
        || { echo "RCC released-target budget missing: $BUDGET" >&2; exit 1; }
else
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    for required in "$LEGACY_DIR/peak_metrics.json" "$LEGACY_DIR/learned_peaks.csv"; do
        [ -f "$required" ] || { echo "Missing legacy input: $required" >&2; exit 1; }
    done
fi
mkdir -p "$RESULT_ROOT" "$CHECKPOINT_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM seed $SEED (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

if [ "$COLLECTION" = RCC ]; then
    K_BIN="$("$PYTHON" -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["K_bin"]))' "$BUDGET")"
else
    K_BIN="$(test_r_k_bin "$DATASET")"
    # K_bin must equal the legacy unique-bin count used by fair scoring.
    "$PYTHON" - "$LEGACY_DIR/peak_metrics.json" "$K_BIN" <<'PY'
import json, sys
count = int(json.load(open(sys.argv[1]))["unique_nearest_bins"])
if count != int(sys.argv[2]):
    sys.exit(f"legacy unique_nearest_bins {count} != K_bin {sys.argv[2]}")
PY
fi
echo "K_bin = $K_BIN"

# Real CUDA warm-up; also records the node and device for the runtime table.
"$PYTHON" - "$RESULT_ROOT/node_record.json" <<'PY'
import json, os, platform, socket, sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
cpu = platform.processor()
with open("/proc/cpuinfo", encoding="utf-8") as stream:
    for line in stream:
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
job = os.environ.get("SLURM_ARRAY_JOB_ID", "") + "_" + os.environ.get("SLURM_ARRAY_TASK_ID", "")
record = {"node": socket.gethostname(), "gpu_model": torch.cuda.get_device_name(0),
          "cuda_version": torch.version.cuda, "torch_version": torch.__version__,
          "cpu_model": cpu, "slurm_job": job}
with open(sys.argv[1], "a", encoding="utf-8") as stream:  # one JSON line per attempt
    stream.write(json.dumps(record) + "\n")
print(f"CUDA warm-up passed on {record['gpu_model']}: {float(probe.sum())}", flush=True)
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
        --learning-rate 0.001 --spatial-lambda 0 --seed "$SEED" --checkpoint-interval 5 \
        --cache-spectra "${RESUME_ARGUMENTS[@]}" >> "$RESULT_ROOT/training_stdout.log"
    echo "Training finished"
fi

# The checkpoint must be the complete, unmasked 3x3 run of this arm at this seed.
"$PYTHON" - "$CHECKPOINT" "$ARM" "$SEED" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
checkpoint = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
arm, seed = sys.argv[2], int(sys.argv[3])
spec = checkpoint_input_spec(checkpoint)
configuration = checkpoint["model_configuration"]
signature = checkpoint["resume_signature"]
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("not a complete 100-epoch checkpoint")
if arm == "central_only":
    if configuration.get("input_mode") != "central_only" or "neighbourhood" in configuration:
        sys.exit("checkpoint is not a central_only model")
elif configuration.get("neighbourhood", {}).get("name") != "uniform_mean":
    sys.exit("checkpoint is not a uniform_mean model")
if spec["window_size"] != 3 or spec["context_mode"] != "measured":
    sys.exit("checkpoint window or context does not match the arm")
if signature.get("seed") != seed or "centre_mask_probability" in signature:
    sys.exit(f"checkpoint is not the seed-{seed} unmasked run")
print("Checkpoint verified", flush=True)
PY

if ! grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RESULT_ROOT/attribution" --variant "$ARM" \
        --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
        --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
        --ig-steps 64 --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 --random-repeats 10 \
        --top-candidates 50 --seed 1 --sampling-seed 1 > "$RESULT_ROOT/attribution_stdout.log" \
        || { echo "IG stopped (see attribution_stdout.log; a GMM component below 44 px is reported as not done)" >&2; exit 4; }
fi
grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" \
    || { echo "IG status is not valid: seed-arm not done; peak evaluation not run" >&2; exit 4; }

if [ "$COLLECTION" = RCC ]; then
    EVALUATION="$RESULT_ROOT/peak_evaluation_released_target"
    LEGACY_ARGUMENTS=(--no-legacy)
else
    EVALUATION="$RESULT_ROOT/peak_evaluation"
    LEGACY_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
fi
if ! grep -q '"status": "complete"' "$EVALUATION/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
        --input "$INPUT" --attribution-dir "$RESULT_ROOT/attribution" "${LEGACY_ARGUMENTS[@]}" \
        --output "$EVALUATION" --matched-count "$K_BIN" \
        --peak-tolerance-ppm 10 --consolidated-candidates 50 \
        --ion-images 12 --chunk-size 1024 > "$EVALUATION.stdout.log"
fi
echo "=== $DATASET $ARM seed $SEED complete ==="

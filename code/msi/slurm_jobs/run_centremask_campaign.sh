#!/bin/bash
# Item G (supervisor chat 2026-10-15 13:30; protocol 18 Section 6): train with
# random centre masking (p = 0.5, training only), then reconstruction, GMM+IG
# and matched peak evaluation at the production K_bin, all on the unmasked
# input. One array task per section-arm:
#   0-15   G1 attention_centremask_p50          (corrected 3x3 attention, all 16 sections)
#   16-31  G2 uniform_centremask_p50            (uniform 3x3, all 16 sections)
#   32-33  G3 shuffled_attention_centremask_p50 (160TopL, GBM22_2; shuffle seed 1701)
# Attention arms on 160TopL/GBM22_2 also write the label-free mechanism check.
# Submit via slurm_jobs/submit_centremask_campaign.sh (CUDA quarantine excluded
# there). Prints status lines only; scores are read after the sync.
#SBATCH --job-name=centremask-p50
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=12:00:00
#SBATCH --exclusive
#SBATCH --output=logs/centremask-p50-%A_%a.out
#SBATCH --error=logs/centremask-p50-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_centremask_campaign.sh}"
P=0.5
if (( TASK_ID >= 0 && TASK_ID < 16 )); then
    DATASET="${FAIR_SECTIONS[TASK_ID]}"; ARM=attention_centremask_p50
    VARIANT=attention; MECHANISM_ARM=real_attention
elif (( TASK_ID >= 16 && TASK_ID < 32 )); then
    DATASET="${FAIR_SECTIONS[TASK_ID - 16]}"; ARM=uniform_centremask_p50
    VARIANT=uniform_mean; MECHANISM_ARM=""
elif (( TASK_ID == 32 || TASK_ID == 33 )); then
    if (( TASK_ID == 32 )); then DATASET=160TopL; else DATASET=GBM22_2; fi
    ARM=shuffled_attention_centremask_p50; VARIANT=attention_shuffled
    MECHANISM_ARM=shuffled_attention
else
    echo "Invalid array index: $TASK_ID" >&2; exit 2
fi
INPUT="$(fair_input_for "$DATASET")"
case "$DATASET" in
    GBM*) LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned/$DATASET"
          GMM_COMPONENTS=2 ;;
    *)    LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/cac/$DATASET"
          GMM_COMPONENTS=3 ;;
esac
# Production K_bin (protocol 18 Section 1), shared by every method and arm.
case "$DATASET" in
    GBM108_positive) K_BIN=584 ;; GBM108_negative) K_BIN=940 ;; GBM12_1) K_BIN=691 ;;
    GBM12_2) K_BIN=986 ;; GBM22_1) K_BIN=834 ;; GBM22_2) K_BIN=1028 ;;
    GBM39_1) K_BIN=695 ;; GBM39_2) K_BIN=911 ;;
    40TopL) K_BIN=315 ;; 160TopL) K_BIN=210 ;; 200TopL) K_BIN=221 ;; 240TopL) K_BIN=255 ;;
    280TopL) K_BIN=245 ;; 360TopL) K_BIN=247 ;; 400TopL) K_BIN=133 ;; 520TopL) K_BIN=232 ;;
esac

RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_centremask_p50/${DATASET}_seed1/$ARM"
CHECKPOINT_DIR="/datasets/zsuliman/msi_checkpoints/spatial_msipl/centremask_p50/${DATASET}_seed1/$ARM"
CHECKPOINT="$CHECKPOINT_DIR/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_DIR/checkpoint_latest.pt"
for required in "$INPUT" "$LEGACY_DIR/peak_metrics.json" "$LEGACY_DIR/learned_peaks.csv"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
mkdir -p "$RESULT_ROOT" "$CHECKPOINT_DIR"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

# K_bin must equal the legacy unique-bin count used by fair scoring.
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

# Synthetic checks of the masking path and the attention control wiring.
"$PYTHON" -m unittest -q spatial_msipl.tests.test_centre_masking \
    spatial_msipl.tests.test_attention_context_control

# --- Training (skipped only if a complete run already exists). ---
if [ -f "$CHECKPOINT" ] && grep -q '"status": "complete"' "$RESULT_ROOT/summary.json" 2>/dev/null; then
    echo "Training already complete"
elif [ -f "$CHECKPOINT" ]; then
    echo "Final checkpoint exists without a complete summary: $CHECKPOINT" >&2; exit 1
else
    RESUME_ARGUMENTS=()
    if [ -f "$LATEST_CHECKPOINT" ]; then
        RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
        echo "Resuming from the latest epoch checkpoint"
    fi
    "$PYTHON" -u scripts/train_spatial_msipl_production.py \
        --input "$INPUT" --output "$RESULT_ROOT" --checkpoint-output "$CHECKPOINT_DIR" \
        --variant "$VARIANT" --window-size 3 \
        --attention-dim 8 --attention-input-scale sqrt_bins --context-seed 1701 \
        --epochs 100 --batch-size 128 --hidden-dim 512 --latent-dim 5 \
        --learning-rate 0.001 --spatial-lambda 0 --seed 1 \
        --centre-mask-probability "$P" \
        --checkpoint-interval 5 --cache-spectra \
        "${RESUME_ARGUMENTS[@]}" > "$RESULT_ROOT/training_stdout.log"
    echo "Training finished"
fi

# Checkpoint must be the 100-epoch masked run of the requested arm.
"$PYTHON" - "$CHECKPOINT" "$VARIANT" "$P" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
checkpoint = torch.load(sys.argv[1], map_location="cpu", weights_only=False)
variant, p = sys.argv[2], float(sys.argv[3])
signature = checkpoint["resume_signature"]
neighbourhood = checkpoint["model_configuration"]["neighbourhood"]
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("not a complete 100-epoch checkpoint")
if signature.get("centre_mask_probability") != p or signature.get("seed") != 1:
    sys.exit("checkpoint is not the seed-1 centre-masked run")
expected = "uniform_mean" if variant == "uniform_mean" else "attention"
if neighbourhood.get("name") != expected:
    sys.exit("checkpoint aggregator does not match the arm")
if expected == "attention" and neighbourhood.get("input_scale_name") != "sqrt_bins":
    sys.exit("attention checkpoint is not the corrected sqrt_bins attention")
mode = checkpoint_input_spec(checkpoint)["context_mode"]
if mode != ("shuffled" if variant == "attention_shuffled" else "measured"):
    sys.exit("checkpoint context mode does not match the arm")
print("Checkpoint verified", flush=True)
PY

# --- Evaluation on the unmasked input, exactly as for the existing arms. ---
if [ ! -f "$RESULT_ROOT/reconstruction/reconstruction.json" ]; then
    "$PYTHON" -u scripts/evaluate_spatial_window_reconstruction.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" --output "$RESULT_ROOT/reconstruction" \
        --variant "$VARIANT" --batch-size 64 > "$RESULT_ROOT/reconstruction_stdout.log"
fi
if ! grep -q '"status": "valid"' "$RESULT_ROOT/attribution/summary.json" 2>/dev/null; then
    "$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RESULT_ROOT/attribution" --variant "$VARIANT" \
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

# --- Mechanism check (label-free; exploratory sections, attention arms). ---
if [ -n "$MECHANISM_ARM" ] && [[ "$DATASET" == 160TopL || "$DATASET" == GBM22_2 ]]; then
    if [ ! -f "$RESULT_ROOT/mechanism/attention_weights.json" ]; then
        "$PYTHON" -u scripts/audit_centremask_attention_weights.py \
            --input "$INPUT" --checkpoint "$CHECKPOINT" --arm "$MECHANISM_ARM" \
            --context-seed 1701 --output "$RESULT_ROOT/mechanism/attention_weights.json"
    fi
fi
echo "=== $DATASET $ARM complete ==="

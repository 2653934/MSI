#!/bin/bash
#SBATCH --job-name=attention-seed
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=16:00:00
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster59,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --array=0-7%2
#SBATCH --output=logs/attention-seed-%A_%a.out
#SBATCH --error=logs/attention-seed-%A_%a.err

set -eo pipefail

# Two outcome-known exploratory sections, two paired arms, training seeds 2/3.
# Evaluation/GMM/IG sampling stays at seed 1, matching the existing seed-1 pilot.
DATASETS=(160TopL 160TopL GBM22_2 GBM22_2 160TopL 160TopL GBM22_2 GBM22_2)
ARMS=(real_attention shuffled_attention real_attention shuffled_attention
      real_attention shuffled_attention real_attention shuffled_attention)
SEEDS=(2 2 2 2 3 3 3 3)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit this file through sbatch as an array}"
if (( TASK_ID < 0 || TASK_ID >= ${#DATASETS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2
    exit 2
fi
DATASET="${DATASETS[TASK_ID]}"
ARM="${ARMS[TASK_ID]}"
SEED="${SEEDS[TASK_ID]}"
case "$DATASET" in
    160TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5"
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/cac/160TopL"
        GMM_COMPONENTS=3
        MATCHED_COUNT=210 ;;
    GBM22_2)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5"
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/massnet/GBM22_2"
        GMM_COMPONENTS=2
        MATCHED_COUNT=464 ;;
esac
case "$ARM" in
    real_attention) VARIANT=attention ;;
    shuffled_attention) VARIANT=attention_shuffled ;;
esac

PROJECT_ROOT="$HOME/msi"
RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_attention_context_seed_stability/${DATASET}_seed${SEED}/$ARM"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context_seed_stability/${DATASET}_seed${SEED}/$ARM"
CHECKPOINT="$CHECKPOINT_ROOT/checkpoint.pt"
LATEST="$CHECKPOINT_ROOT/checkpoint_latest.pt"
ATTRIBUTION="$RESULT_ROOT/attribution"
EVALUATION="$RESULT_ROOT/peak_evaluation"
RECONSTRUCTION="$RESULT_ROOT/reconstruction"

echo "=== $DATASET $ARM training seed $SEED on ${SLURMD_NODENAME:-unknown} ==="
for required in "$INPUT" "$LEGACY_DIR/learned_peaks.csv" "$LEGACY_DIR/peak_metrics.json"; do
    if [ ! -f "$required" ]; then
        echo "Missing frozen input: $required" >&2
        exit 1
    fi
done
if ! mkdir -p "$RESULT_ROOT" "$CHECKPOINT_ROOT"; then
    # Concurrent sibling creation can report EEXIST on the shared filesystem.
    if [ ! -d "$RESULT_ROOT" ] || [ ! -d "$CHECKPOINT_ROOT" ]; then
        echo "Could not prepare both output directories for $DATASET $ARM seed $SEED" >&2
        exit 1
    fi
fi
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4

# This is an end-to-end GPU job; fail before model/data load on an unusable node.
python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; seed repeat stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

python -m unittest discover -s src/spatial_msipl/tests -p test_attention_context_control.py

if ! grep -q '"status": "complete"' "$RESULT_ROOT/summary.json" 2>/dev/null; then
    if [ -f "$CHECKPOINT" ]; then
        echo "Final checkpoint exists without complete training summary; refusing overwrite: $CHECKPOINT" >&2
        exit 1
    fi
    python -u scripts/validate_spatial_window_cache.py \
        --input "$INPUT" --window-size 3 --variant "$ARM"
    RESUME=()
    if [ -f "$LATEST" ]; then
        RESUME=(--resume-checkpoint "$LATEST")
        echo "Resuming from $LATEST"
    fi
    python -u scripts/train_spatial_msipl_production.py \
        --input "$INPUT" --output "$RESULT_ROOT" \
        --checkpoint-output "$CHECKPOINT_ROOT" \
        --variant "$VARIANT" --window-size 3 \
        --attention-dim 8 --attention-input-scale sqrt_bins \
        --context-seed 1701 --epochs 100 --batch-size 128 \
        --hidden-dim 512 --latent-dim 5 --learning-rate 0.001 \
        --spatial-lambda 0 --seed "$SEED" --checkpoint-interval 5 \
        --cache-spectra "${RESUME[@]}"
fi
if [ ! -f "$CHECKPOINT" ] || ! grep -q '"status": "complete"' "$RESULT_ROOT/summary.json"; then
    echo "Training is not complete; evaluation stopped" >&2
    exit 1
fi

python - "$CHECKPOINT" "$ARM" "$SEED" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
checkpoint = torch.load(sys.argv[1], map_location="cpu")
arm, seed = sys.argv[2], int(sys.argv[3])
spec = checkpoint_input_spec(checkpoint)
expected = "measured" if arm == "real_attention" else "shuffled"
if checkpoint.get("completed_epochs") != 100 or spec["context_mode"] != expected:
    sys.exit("Checkpoint epoch/context mismatch")
if checkpoint["model_configuration"]["neighbourhood"].get("name") != "attention":
    sys.exit("Checkpoint does not contain the attention aggregator")
if checkpoint["model_configuration"]["neighbourhood"].get("input_scale_name") != "sqrt_bins":
    sys.exit("Checkpoint attention scaling mismatch")
if checkpoint.get("resume_signature", {}).get("seed") != seed:
    sys.exit("Checkpoint training seed mismatch")
print(f"Checkpoint verified for training seed {seed}, {expected} context", flush=True)
PY

if [ ! -f "$RECONSTRUCTION/reconstruction.json" ]; then
    python -u scripts/evaluate_spatial_window_reconstruction.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RECONSTRUCTION" --variant "$VARIANT" --batch-size 64
fi
if ! grep -q '"status": "valid"' "$ATTRIBUTION/summary.json" 2>/dev/null; then
    python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$ATTRIBUTION" --variant "$VARIANT" \
        --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
        --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
        --ig-steps 64 --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 --random-repeats 10 \
        --top-candidates 50 --seed 1 --sampling-seed 1
fi
if ! grep -q '"status": "complete"' "$EVALUATION/summary.json" 2>/dev/null; then
    python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
        --input "$INPUT" --attribution-dir "$ATTRIBUTION" \
        --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
        --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
        --output "$EVALUATION" --matched-count "$MATCHED_COUNT" \
        --peak-tolerance-ppm 10 --consolidated-candidates 50 \
        --ion-images 12 --chunk-size 1024
fi
echo "Completed: $DATASET $ARM training seed $SEED"

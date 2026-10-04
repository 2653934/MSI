#!/bin/bash
#SBATCH --job-name=attention-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=08:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/attention-eval-%j.out
#SBATCH --error=logs/attention-eval-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 {160TopL|GBM22_2} {real_attention|shuffled_attention}" >&2
    exit 2
fi

DATASET="$1"
ARM="$2"
case "$DATASET" in
    160TopL)
        INPUT=/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/cac/160TopL"
        GMM_COMPONENTS=3
        MATCHED_COUNT=210 ;;
    GBM22_2)
        INPUT=/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/massnet/GBM22_2"
        GMM_COMPONENTS=2
        MATCHED_COUNT=464 ;;
    *) echo "Unsupported attention-context dataset: $DATASET" >&2; exit 2 ;;
esac
case "$ARM" in
    real_attention) VARIANT=attention ;;
    shuffled_attention) VARIANT=attention_shuffled ;;
    *) echo "Unsupported attention-context arm: $ARM" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${DATASET}_seed1/$ARM/checkpoint.pt"
RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_attention_context/${DATASET}_seed1/$ARM"
ATTRIBUTION_OUTPUT="$RESULT_ROOT/attribution"
EVALUATION_OUTPUT="$RESULT_ROOT/peak_evaluation"
RECONSTRUCTION_OUTPUT="$RESULT_ROOT/reconstruction"
if [ ! -f "$CHECKPOINT" ] || ! grep -q '"status": "complete"' "$RESULT_ROOT/summary.json" 2>/dev/null; then
    echo "Training is not complete for $DATASET $ARM; evaluation cannot start" >&2
    exit 1
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
    sys.exit("CUDA unavailable; evaluation stopped before model load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

python - "$CHECKPOINT" "$ARM" <<'PY'
import sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec

checkpoint = torch.load(sys.argv[1], map_location="cpu")
arm = sys.argv[2]
configuration = checkpoint["model_configuration"]
input_spec = checkpoint_input_spec(checkpoint)
expected_context = "measured" if arm == "real_attention" else "shuffled"
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("Evaluation requires a full 100-epoch checkpoint")
if configuration["neighbourhood"].get("name") != "attention":
    sys.exit("Checkpoint does not contain the attention aggregator")
if configuration["neighbourhood"].get("input_scale_name") != "sqrt_bins":
    sys.exit("Checkpoint does not use corrected sqrt_bins attention scaling")
if input_spec["context_mode"] != expected_context:
    sys.exit("Checkpoint context does not match the requested attention arm")
print(f"Checkpoint verified: {arm}, {expected_context} context, sqrt_bins scale", flush=True)
PY

if [ ! -f "$RECONSTRUCTION_OUTPUT/reconstruction.json" ]; then
    python -u scripts/evaluate_spatial_window_reconstruction.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$RECONSTRUCTION_OUTPUT" --variant "$VARIANT" --batch-size 64
fi

if ! grep -q '"status": "valid"' "$ATTRIBUTION_OUTPUT/summary.json" 2>/dev/null; then
    python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" --checkpoint "$CHECKPOINT" \
        --output "$ATTRIBUTION_OUTPUT" --variant "$VARIANT" \
        --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
        --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
        --ig-steps 64 --ig-internal-batch-size 8 \
        --deletion-budgets 32 128 512 --random-repeats 10 \
        --top-candidates 50 --seed 1 --sampling-seed 1
fi

if ! grep -q '"status": "complete"' "$EVALUATION_OUTPUT/summary.json" 2>/dev/null; then
    python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
        --input "$INPUT" --attribution-dir "$ATTRIBUTION_OUTPUT" \
        --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
        --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
        --output "$EVALUATION_OUTPUT" --matched-count "$MATCHED_COUNT" \
        --peak-tolerance-ppm 10 --consolidated-candidates 50 \
        --ion-images 12 --chunk-size 1024
fi

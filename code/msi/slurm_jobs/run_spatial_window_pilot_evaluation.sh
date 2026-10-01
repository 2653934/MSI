#!/bin/bash
#SBATCH --job-name=window-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/window-eval-%j.out
#SBATCH --error=logs/window-eval-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 {GBM108_positive|40TopL} {uniform_p5|zero_p3|shuffled_p3}" >&2
    exit 2
fi

DATASET="$1"
ARM="$2"
case "$DATASET" in
    GBM108_positive)
        INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/massnet/$DATASET"
        MATCHED_COUNT=530
        GMM_COMPONENTS=2
        ;;
    40TopL)
        INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5"
        LEGACY_DIR="$HOME/msi/results/baselines/msipl/cac/$DATASET"
        MATCHED_COUNT=315
        GMM_COMPONENTS=3
        ;;
    *) echo "Unknown pilot dataset: $DATASET" >&2; exit 2 ;;
esac
case "$ARM" in
    uniform_p5) VARIANT=uniform_mean ;;
    zero_p3) VARIANT=zero_context ;;
    shuffled_p3) VARIANT=shuffled_uniform ;;
    *) echo "Unknown pilot arm: $ARM" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${DATASET}_seed1/$ARM/checkpoint.pt"
RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_msipl_window_pilot/${DATASET}_seed1/$ARM"
ATTRIBUTION_OUTPUT="$RESULT_ROOT/attribution"
EVALUATION_OUTPUT="$RESULT_ROOT/peak_evaluation"
RECONSTRUCTION_OUTPUT="$RESULT_ROOT/reconstruction"
if [ ! -f "$CHECKPOINT" ]; then
    echo "Completed pilot checkpoint is missing: $CHECKPOINT" >&2
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
    sys.exit("CUDA unavailable; pilot evaluation stopped before model load")
device = torch.device("cuda:0")
probe = torch.ones((32, 32), device=device)
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(device)}: {float(probe.sum())}", flush=True)
PY

if [ ! -f "$RECONSTRUCTION_OUTPUT/reconstruction.json" ]; then
    python -u scripts/evaluate_spatial_window_reconstruction.py \
        --input "$INPUT" \
        --checkpoint "$CHECKPOINT" \
        --output "$RECONSTRUCTION_OUTPUT" \
        --variant "$VARIANT" \
        --batch-size 64
fi

if ! grep -q '"status": "valid"' "$ATTRIBUTION_OUTPUT/summary.json" 2>/dev/null; then
    python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
        --input "$INPUT" \
        --checkpoint "$CHECKPOINT" \
        --output "$ATTRIBUTION_OUTPUT" \
        --variant "$VARIANT" \
        --batch-size 64 \
        --gmm-components "$GMM_COMPONENTS" \
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

if ! grep -q '"status": "complete"' "$EVALUATION_OUTPUT/summary.json" 2>/dev/null; then
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
fi

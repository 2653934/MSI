#!/bin/bash
#SBATCH --job-name=attention-peak-all
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/attention-peak-all-%A_%a.out
#SBATCH --error=logs/attention-peak-all-%A_%a.err

set -euo pipefail

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
MATCHED_COUNTS=(315 210 221 255 245 247 133 232 530 458 453 478 589 464 686 523)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_spatial_attention_changed_peaks_campaign.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#DATASETS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2
    exit 2
fi
DATASET="${DATASETS[TASK_ID]}"
MATCHED_COUNT="${MATCHED_COUNTS[TASK_ID]}"
PROJECT_ROOT="$HOME/msi"
RANKING_DIR="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$DATASET"
ORIGINAL="$PROJECT_ROOT/results/experiments/spatial_attention_context/${DATASET}_seed1/real_attention/peak_evaluation/ig_matched_${MATCHED_COUNT}_bins.csv"
OUTPUT="$PROJECT_ROOT/results/diagnostics/spatial_attention_changed_peaks/$DATASET"
case "$DATASET" in
    *TopL) INPUT="/datasets/zsuliman/msi_data/cac_msipl/$DATASET.h5" ;;
    GBM*) INPUT="/datasets/zsuliman/msi_data/gbm_massnet/$DATASET.h5" ;;
esac

echo "=== $DATASET: CPU-only changed-peak audit on ${SLURMD_NODENAME:-unknown} ==="
if grep -q '"status": "valid"' "$OUTPUT/summary.json" 2>/dev/null &&
   [ -f "$OUTPUT/changed_bins.csv" ] &&
   [ -f "$OUTPUT/changed_bin_pcc.png" ] &&
   [ -f "$OUTPUT/changed_ion_images.png" ]; then
    echo "Already valid: $OUTPUT/summary.json"
    exit 0
fi
for required in "$INPUT" "$RANKING_DIR/summary.json" "$RANKING_DIR/rankings.npz" "$ORIGINAL"; do
    if [ ! -f "$required" ]; then
        echo "Missing frozen input: $required" >&2
        exit 1
    fi
done
if ! grep -q '"status": "valid"' "$RANKING_DIR/summary.json"; then
    echo "Frozen ranking is not valid: $RANKING_DIR/summary.json" >&2
    exit 1
fi

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
"$PYTHON" -m unittest discover -s src/spatial_msipl/tests -p test_attention_changed_peaks.py
"$PYTHON" -u scripts/audit_spatial_attention_changed_peaks.py \
    --input "$INPUT" --ranking-dir "$RANKING_DIR" \
    --original-peaks "$ORIGINAL" --output "$OUTPUT"

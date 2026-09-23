#!/bin/bash
# Re-evaluate frozen GBM rankings at the paper-aligned msiPL peak count.
# This job is CPU-only: it does not retrain a model or recompute attribution.
# It is restart-safe because completed dataset/variant outputs are skipped.
#SBATCH --job-name=gbm-tuned-count
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=48G
#SBATCH --open-mode=append
#SBATCH --output=logs/gbm-tuned-count-%j.out
#SBATCH --error=logs/gbm-tuned-count-%j.err

# Do not enable nounset here: this cluster's Conda activation hooks read
# optional variables that may legitimately be unset.
set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATA_ROOT="/datasets/zsuliman/msi_data/gbm_massnet"
TUNED_LEGACY_ROOT="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned"
ATTRIBUTION_ROOT="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients"
OUTPUT_ROOT="$PROJECT_ROOT/results/experiments/spatial_msipl_gbm_tuned_count_evaluation"
SUMMARY_ROOT="$PROJECT_ROOT/results/comparisons/spatial_msipl_gbm_tuned_counts"

DATASETS=(
    GBM108_positive
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)
VARIANTS=(central_only uniform_mean)

mkdir -p "$PROJECT_ROOT/logs" "$OUTPUT_ROOT" "$SUMMARY_ROOT"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
cd "$PROJECT_ROOT"

echo "=== TUNED-COUNT GBM EVALUATION ==="
echo "This reuses frozen rankings; no training or attribution is performed."

for dataset in "${DATASETS[@]}"; do
    legacy_dir="$TUNED_LEGACY_ROOT/$dataset"
    legacy_metrics="$legacy_dir/peak_metrics.json"
    legacy_peaks="$legacy_dir/learned_peaks.csv"
    input="$DATA_ROOT/$dataset.h5"

    if [ ! -f "$legacy_metrics" ] || [ ! -f "$legacy_peaks" ]; then
        echo "Missing tuned msiPL artifacts for $dataset" >&2
        exit 1
    fi

    matched_count=$(python - "$legacy_metrics" <<'PY'
import json
import sys
from pathlib import Path

metrics = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
count = int(metrics["unique_nearest_bins"])
if count < 1:
    raise SystemExit("invalid tuned peak count")
print(count)
PY
    )

    printf '\n%-18s tuned count = %s\n' "$dataset" "$matched_count"

    for variant in "${VARIANTS[@]}"; do
        attribution_dir="$ATTRIBUTION_ROOT/${dataset}_seed1/$variant"
        output="$OUTPUT_ROOT/${dataset}_seed1/$variant"

        if grep -q '"status": "complete"' "$output/summary.json" 2>/dev/null; then
            printf '  %-14s COMPLETE (skipped)\n' "$variant"
            continue
        fi
        if [ ! -f "$attribution_dir/attributions.npz" ] || \
           [ ! -f "$attribution_dir/coordinates_and_gmm.npz" ]; then
            echo "Missing frozen attribution for $dataset $variant: $attribution_dir" >&2
            exit 1
        fi

        printf '  %-14s evaluating...\n' "$variant"
        python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
            --input "$input" \
            --attribution-dir "$attribution_dir" \
            --legacy-peaks "$legacy_peaks" \
            --legacy-metrics "$legacy_metrics" \
            --output "$output" \
            --matched-count "$matched_count" \
            --peak-tolerance-ppm 10 \
            --consolidated-candidates 50 \
            --ion-images 12 \
            --chunk-size 1024
    done
done

python -u scripts/summarise_spatial_msipl_gbm_tuned_counts.py \
    --project-root "$PROJECT_ROOT" \
    --output "$SUMMARY_ROOT"

echo
echo "Tuned-count GBM evaluation complete."
echo "Summary: $SUMMARY_ROOT/summary.json"
echo "Figure:  $SUMMARY_ROOT/gbm_tuned_count_comparison.png"

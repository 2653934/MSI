#!/bin/bash
#SBATCH --job-name=gbm-ig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster83
#SBATCH --output=logs/gbm-ig-%j.out
#SBATCH --error=logs/gbm-ig-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 DATASET MATCHED_PEAK_COUNT" >&2
    exit 2
fi

DATASET="$1"
MATCHED_COUNT="$2"
case "$DATASET:$MATCHED_COUNT" in
    GBM108_negative:458|GBM12_1:453|GBM12_2:478|GBM22_1:589|GBM22_2:464|GBM39_1:686|GBM39_2:523) ;;
    *)
        echo "Unknown dataset/count pair: $DATASET:$MATCHED_COUNT" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/${DATASET}_seed1/uniform_mean/checkpoint.pt"
ATTRIBUTION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/uniform_mean"
LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet/$DATASET"
EVALUATION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed1/uniform_mean"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; GBM attribution stopped before loading the model.")'

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" \
    --checkpoint "$CHECKPOINT" \
    --output "$ATTRIBUTION_OUTPUT" \
    --batch-size 64 \
    --gmm-components 2 \
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

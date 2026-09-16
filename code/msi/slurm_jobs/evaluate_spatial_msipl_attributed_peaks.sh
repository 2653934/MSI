#!/bin/bash
#SBATCH --job-name=spatial-peak-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/spatial-peak-eval-%j.out
#SBATCH --error=logs/spatial-peak-eval-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
ATTRIBUTION_DIR="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/GBM108_positive_seed1/uniform_mean"
LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet/GBM108_positive"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1/uniform_mean"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$INPUT" \
    --attribution-dir "$ATTRIBUTION_DIR" \
    --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
    --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
    --output "$OUTPUT" \
    --matched-count 530 \
    --peak-tolerance-ppm 10 \
    --consolidated-candidates 50 \
    --ion-images 12 \
    --chunk-size 1024

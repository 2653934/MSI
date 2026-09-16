#!/bin/bash
#SBATCH --job-name=ig-stability
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/ig-stability-%j.out
#SBATCH --error=logs/ig-stability-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 SAMPLING_SEED" >&2
    exit 2
fi

SAMPLING_SEED="$1"
PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/GBM108_positive_seed1/uniform_mean/checkpoint.pt"
ATTRIBUTION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/GBM108_positive_seed1/sampling_seed${SAMPLING_SEED}"
LEGACY_DIR="$PROJECT_ROOT/results/baselines/msipl/massnet/GBM108_positive"
EVALUATION_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1/sampling_seed${SAMPLING_SEED}"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; stability repeat stopped before loading the model.")'

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
    --sampling-seed "$SAMPLING_SEED"

python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$INPUT" \
    --attribution-dir "$ATTRIBUTION_OUTPUT" \
    --legacy-peaks "$LEGACY_DIR/learned_peaks.csv" \
    --legacy-metrics "$LEGACY_DIR/peak_metrics.json" \
    --output "$EVALUATION_OUTPUT" \
    --matched-count 530 \
    --peak-tolerance-ppm 10 \
    --consolidated-candidates 50 \
    --ion-images 12 \
    --chunk-size 1024

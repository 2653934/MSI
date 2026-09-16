#!/bin/bash
#SBATCH --job-name=ig-summary
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=8G
#SBATCH --output=logs/ig-summary-%j.out
#SBATCH --error=logs/ig-summary-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
EVALUATION_ROOT="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1"
OUTPUT="$EVALUATION_ROOT/sampling_stability"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

cd "$PROJECT_ROOT"
python -u scripts/summarise_spatial_ig_stability.py \
    --run "$EVALUATION_ROOT/uniform_mean" \
    --run "$EVALUATION_ROOT/sampling_seed2" \
    --run "$EVALUATION_ROOT/sampling_seed3" \
    --run "$EVALUATION_ROOT/sampling_seed4" \
    --output "$OUTPUT"

#!/bin/bash
#SBATCH --job-name=window-score-audit
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=12G
#SBATCH --time=01:00:00
#SBATCH --output=logs/window-score-audit-%j.out
#SBATCH --error=logs/window-score-audit-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -m unittest discover -s src/spatial_msipl/tests -p test_window_peak_scoring_audit.py

DATASET=GBM22_2
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
WINDOW_ROOT="results/experiments/spatial_msipl_window_pilot/${DATASET}_seed1"
REFERENCE="results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed1/uniform_mean"
OUTPUT="results/diagnostics/spatial_window_scoring/${DATASET}.json"

python -u scripts/audit_window_peak_scoring.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    "$REFERENCE" \
    "$WINDOW_ROOT/uniform_p5/peak_evaluation" \
    "$WINDOW_ROOT/zero_p3/peak_evaluation" \
    "$WINDOW_ROOT/shuffled_p3/peak_evaluation"

#!/bin/bash
#SBATCH --job-name=gbm-context-summary
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=8G
#SBATCH --output=logs/gbm-context-summary-%j.out
#SBATCH --error=logs/gbm-context-summary-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gbm_validation/context_attribution_control"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -u scripts/summarise_spatial_gbm_context_attribution.py \
    --project-root "$PROJECT_ROOT" \
    --output "$OUTPUT"

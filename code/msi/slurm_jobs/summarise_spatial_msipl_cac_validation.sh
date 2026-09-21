#!/bin/bash
#SBATCH --job-name=cac-summary
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=4G
#SBATCH --output=logs/cac-summary-%j.out
#SBATCH --error=logs/cac-summary-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/comparisons/spatial_msipl_cac_validation"

mkdir -p "$PROJECT_ROOT/logs" "$OUTPUT"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -u scripts/summarise_spatial_msipl_cac_validation.py \
    --project-root "$PROJECT_ROOT" \
    --output "$OUTPUT"

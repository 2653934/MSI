#!/bin/bash
#SBATCH --job-name=seed-ig-summary
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=8G
#SBATCH --output=logs/seed-ig-summary-%j.out
#SBATCH --error=logs/seed-ig-summary-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
cd "$PROJECT_ROOT"

python -u scripts/summarise_spatial_msipl_training_seed_stability.py \
    --project-root "$PROJECT_ROOT" \
    --output "$PROJECT_ROOT/results/experiments/spatial_msipl_training_seed_stability_summary"

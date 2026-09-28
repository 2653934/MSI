#!/bin/bash
#SBATCH --job-name=spatial-cache-verify
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --output=logs/spatial-cache-verify-%j.out
#SBATCH --error=logs/spatial-cache-verify-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_cached_full/GBM108_positive_seed1/checkpoint_equivalence"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

for VARIANT in central_only uniform_mean; do
    if [ "$VARIANT" = central_only ]; then
        ORIGINAL="$CHECKPOINT_ROOT/reconstruction/GBM108_positive_seed1/central_only/checkpoint.pt"
    else
        ORIGINAL="$CHECKPOINT_ROOT/production/GBM108_positive_seed1/uniform_mean/checkpoint.pt"
    fi
    CACHED="$CHECKPOINT_ROOT/cache_validation/GBM108_positive_seed1/$VARIANT/checkpoint.pt"
    RESULT="$OUTPUT/$VARIANT.json"
    if [ -f "$RESULT" ]; then
        echo "Comparison already exists; leaving it unchanged: $RESULT"
        continue
    fi
    python -u scripts/compare_spatial_msipl_cache_checkpoints.py \
        --streaming "$ORIGINAL" \
        --cached "$CACHED" \
        --variant "$VARIANT" \
        --output "$RESULT"
done

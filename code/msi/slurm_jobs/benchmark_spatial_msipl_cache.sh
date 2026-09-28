#!/bin/bash
#SBATCH --job-name=spatial-cache
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=16G
#SBATCH --output=logs/spatial-cache-%j.out
#SBATCH --error=logs/spatial-cache-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_cache_benchmark"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -m unittest spatial_msipl.tests.test_preprocessing
python -u scripts/benchmark_spatial_msipl_cache.py \
    --input "$INPUT" \
    --output "$OUTPUT/cache-${SLURM_JOB_ID}.json" \
    --batch-size 128 \
    --batches 8 \
    --parity-samples 32

#!/bin/bash
#SBATCH --job-name=poisson-calibrate
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=16G
#SBATCH --output=logs/poisson-calibrate-%j.out
#SBATCH --error=logs/poisson-calibrate-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_poisson_calibration/GBM108_positive_seed1"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/calibrate_poisson_augmentation.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --effective-counts 10000 100000 1000000 \
    --samples 32 \
    --seed 1

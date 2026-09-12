#!/bin/bash
#SBATCH --job-name=spatial-gpu-check
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --output=logs/spatial-gpu-check-%j.out
#SBATCH --error=logs/spatial-gpu-check-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_gpu_feasibility/GBM108_positive"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable on this node; benchmark stopped before allocating the model.")'

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/benchmark_spatial_msipl_gpu_feasibility.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --epochs 1 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --attention-dim 8 \
    --maximum-samples 256 \
    --learning-rate 0.001 \
    --seed 1


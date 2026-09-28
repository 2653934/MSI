#!/bin/bash
#SBATCH --job-name=spatial-profile
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/spatial-profile-%j.out
#SBATCH --error=logs/spatial-profile-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_msipl_runtime_profile"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA unavailable; diagnostic stopped before loading the model")'
python -m py_compile scripts/profile_spatial_msipl_training.py

for VARIANT in central_only uniform_mean; do
    python -u scripts/profile_spatial_msipl_training.py \
        --input "$INPUT" \
        --output "$OUTPUT/${VARIANT}-${SLURM_JOB_ID}.json" \
        --variant "$VARIANT" \
        --batch-size 128 \
        --batches 4 \
        --device cuda
done

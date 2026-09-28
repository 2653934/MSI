#!/bin/bash
#SBATCH --job-name=s3pl-vae-phases
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/s3pl-vae-phases-%j.out
#SBATCH --error=logs/s3pl-vae-phases-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/validation/s3pl_cached_vae_phases/$SLURM_JOB_ID"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

printf 'Job: %s\nNode: %s\nStart UTC: %s\nInput: %s\n' \
    "$SLURM_JOB_ID" "$(hostname)" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$INPUT"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA unavailable; phase comparison stopped before loading models")'
python -m py_compile scripts/profile_s3pl_training.py scripts/profile_spatial_msipl_training.py

python -u scripts/profile_s3pl_training.py \
    --input "$INPUT" \
    --output "$OUTPUT/s3pl_p3.json" \
    --patch-size 3 \
    --batch-size 16 \
    --batches 8 \
    --device cuda

for VARIANT in central_only uniform_mean; do
    python -u scripts/profile_spatial_msipl_training.py \
        --input "$INPUT" \
        --output "$OUTPUT/${VARIANT}_cached.json" \
        --variant "$VARIANT" \
        --cache-spectra \
        --batch-size 128 \
        --batches 4 \
        --device cuda
done

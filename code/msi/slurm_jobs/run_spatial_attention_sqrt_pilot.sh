#!/bin/bash
#SBATCH --job-name=attention-pilot
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster45,mscluster50,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/attention-pilot-%j.out
#SBATCH --error=logs/attention-pilot-%j.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
OUTPUT="$PROJECT_ROOT/results/validation/spatial_attention_sqrt_pilot/job_$SLURM_JOB_ID"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/validation/attention_sqrt/job_$SLURM_JOB_ID"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; pilot stopped before loading the model.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_stability.py \
    --input /datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5 \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant attention \
    --attention-input-scale sqrt_bins \
    --epochs 5 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --attention-dim 8 \
    --learning-rate 0.001 \
    --seed 1

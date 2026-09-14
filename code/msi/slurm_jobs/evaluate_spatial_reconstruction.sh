#!/bin/bash
#SBATCH --job-name=recon-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/recon-eval-%j.out
#SBATCH --error=logs/recon-eval-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
CHECKPOINT_BASE="/datasets/zsuliman/msi_checkpoints/spatial_msipl"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_reconstruction/GBM108_positive_seed1/evaluation"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; reconstruction evaluation stopped.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_spatial_reconstruction.py \
    --input "$INPUT" \
    --checkpoint-base "$CHECKPOINT_BASE" \
    --output "$OUTPUT" \
    --batch-size 64

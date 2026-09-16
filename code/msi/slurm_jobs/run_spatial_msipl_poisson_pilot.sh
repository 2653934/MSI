#!/bin/bash
#SBATCH --job-name=poisson-pilot
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster74,mscluster83
#SBATCH --output=logs/poisson-pilot-%j.out
#SBATCH --error=logs/poisson-pilot-%j.err

set -eo pipefail

if [[ $# -ne 1 ]] || ! [[ "$1" =~ ^[0-9]+([.][0-9]+)?$ ]] || [[ "$1" == "0" ]]; then
    echo "Usage: sbatch $0 EFFECTIVE_ION_COUNT" >&2
    exit 2
fi

EFFECTIVE_COUNT="$1"
COUNT_LABEL="${EFFECTIVE_COUNT//./p}"
PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_poisson/GBM108_positive_seed1/uniform_mean_count_${COUNT_LABEL}_pilot"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/poisson/GBM108_positive_seed1/uniform_mean_count_${COUNT_LABEL}_pilot"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; Poisson pilot stopped before training.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant uniform_mean \
    --epochs 5 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda 0.0 \
    --spatial-loss-scale unit \
    --poisson-effective-count "$EFFECTIVE_COUNT" \
    --seed 1

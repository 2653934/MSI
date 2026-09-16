#!/bin/bash
#SBATCH --job-name=spatial-gmm-ig
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=04:00:00
#SBATCH --mem=48G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster50,mscluster51,mscluster65,mscluster83
#SBATCH --output=logs/spatial-gmm-ig-%j.out
#SBATCH --error=logs/spatial-gmm-ig-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM108_positive.h5"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/GBM108_positive_seed1/uniform_mean/checkpoint.pt"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/GBM108_positive_seed1/uniform_mean"

mkdir -p "$PROJECT_ROOT/logs"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; attribution stopped before loading the model.")'

cd "$PROJECT_ROOT"
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" \
    --checkpoint "$CHECKPOINT" \
    --output "$OUTPUT" \
    --batch-size 64 \
    --gmm-components 2 \
    --gmm-n-init 20 \
    --attribution-per-cluster 12 \
    --faithfulness-per-cluster 32 \
    --ig-steps 64 \
    --ig-internal-batch-size 8 \
    --deletion-budgets 32 128 512 \
    --random-repeats 10 \
    --top-candidates 50 \
    --seed 1

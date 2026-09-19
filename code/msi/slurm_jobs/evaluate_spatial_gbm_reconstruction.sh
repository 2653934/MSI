#!/bin/bash
#SBATCH --job-name=gbm-recon-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster83
#SBATCH --output=logs/gbm-recon-eval-%j.out
#SBATCH --error=logs/gbm-recon-eval-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 DATASET" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    GBM108_negative|GBM12_1|GBM12_2|GBM22_1|GBM22_2|GBM39_1|GBM39_2) ;;
    *)
        echo "Unknown validation dataset: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
CHECKPOINT_BASE="/datasets/zsuliman/msi_checkpoints/spatial_msipl"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_reconstruction/${DATASET}_seed1/evaluation"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; GBM reconstruction evaluation stopped.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_spatial_reconstruction.py \
    --input "$INPUT" \
    --checkpoint-base "$CHECKPOINT_BASE" \
    --output "$OUTPUT" \
    --models central_only uniform_mean \
    --batch-size 64

#!/bin/bash
#SBATCH --job-name=cac-recon
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=16G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/cac-recon-%j.out
#SBATCH --error=logs/cac-recon-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 DATASET" >&2
    exit 2
fi

DATASET="$1"
case "$DATASET" in
    40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL) ;;
    *)
        echo "Unknown CAC dataset: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5"
CHECKPOINT_BASE="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac"
OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_cac_reconstruction/${DATASET}_seed1/evaluation"

if grep -q '"status": "complete"' "$OUTPUT/comparison.json" 2>/dev/null; then
    echo "$DATASET already has a complete reconstruction evaluation; nothing to do."
    exit 0
fi

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; CAC reconstruction evaluation stopped.")'
python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/evaluate_spatial_reconstruction.py \
    --input "$INPUT" \
    --checkpoint-base "$CHECKPOINT_BASE" \
    --output "$OUTPUT" \
    --batch-size 64 \
    --models central_only uniform_mean

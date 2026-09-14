#!/bin/bash
#SBATCH --job-name=msipl-cac-data
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --partition=bigbatch
#SBATCH --time=00:30:00
#SBATCH --mem=16G
#SBATCH --output=logs/msipl-cac-data-%j.out
#SBATCH --error=logs/msipl-cac-data-%j.err

set -eo pipefail

DATASET="${1:-40TopL}"
case "$DATASET" in
    40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL) ;;
    *)
        echo "Unknown CAC dataset: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
SOURCE_ROOT="/datasets/zsuliman/msi_data/cac"
ADAPTER_ROOT="/datasets/zsuliman/msi_data/cac_msipl"
INPUT="$SOURCE_ROOT/$DATASET.imzML"
MASK="$SOURCE_ROOT/masks/${DATASET}_mask.npy"
OUTPUT="$ADAPTER_ROOT/$DATASET.h5"
AUDIT="$PROJECT_ROOT/results/validation/msipl_cac_adapter/$DATASET.json"

mkdir -p "$PROJECT_ROOT/logs" "$ADAPTER_ROOT" "$(dirname "$AUDIT")"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

python -c "import h5py, pyimzml; print('h5py:', h5py.__version__); print('pyimzML: available')"

python -m py_compile scripts/prepare_msipl_cac_h5.py
python scripts/prepare_msipl_cac_h5.py \
    --input "$INPUT" \
    --mask "$MASK" \
    --output "$OUTPUT" \
    --audit "$AUDIT"

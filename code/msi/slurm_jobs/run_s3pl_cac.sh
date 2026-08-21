#!/bin/bash
#SBATCH --job-name=s3pl-cac
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-cac-%j.out
#SBATCH --error=logs/s3pl-cac-%j.err

set -eo pipefail

DATASET="${1:-40TopL}"

case "$DATASET" in
    40TopL|160TopL|200TopL|240TopL|280TopL|360TopL|400TopL|520TopL)
        ;;
    *)
        echo "Unknown CAC section: $DATASET" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
S3PL_ROOT="$PROJECT_ROOT/baselines/s3pl"
DATA_PATH="/datasets/zsuliman/msi_data/cac/${DATASET}.imzML"

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

cd "$S3PL_ROOT"

python main.py \
    --data_dir "$DATA_PATH" \
    --artifact_root "$PROJECT_ROOT"

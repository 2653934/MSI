#!/bin/bash
#SBATCH --job-name=spatial-gbm-val
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=16:00:00
#SBATCH --mem=32G
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster83
#SBATCH --output=logs/spatial-gbm-val-%j.out
#SBATCH --error=logs/spatial-gbm-val-%j.err

set -eo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: sbatch $0 DATASET {uniform_mean|central_only}" >&2
    exit 2
fi

DATASET="$1"
VARIANT="$2"
case "$DATASET" in
    GBM108_negative|GBM12_1|GBM12_2|GBM22_1|GBM22_2|GBM39_1|GBM39_2) ;;
    *)
        echo "Unknown validation dataset: $DATASET" >&2
        exit 2
        ;;
esac
case "$VARIANT" in
    uniform_mean|central_only) ;;
    *)
        echo "Unknown validation variant: $VARIANT" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5"
if [ "$VARIANT" = "uniform_mean" ]; then
    RESULT_GROUP="spatial_msipl_neighbourhood"
    CHECKPOINT_GROUP="production"
else
    RESULT_GROUP="spatial_msipl_reconstruction"
    CHECKPOINT_GROUP="reconstruction"
fi
OUTPUT="$PROJECT_ROOT/results/experiments/$RESULT_GROUP/${DATASET}_seed1/$VARIANT"
CHECKPOINT_OUTPUT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/$CHECKPOINT_GROUP/${DATASET}_seed1/$VARIANT"
FINAL_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint.pt"
LATEST_CHECKPOINT="$CHECKPOINT_OUTPUT/checkpoint_latest.pt"

if [ ! -f "$INPUT" ]; then
    echo "Input does not exist: $INPUT" >&2
    exit 1
fi
if [ -f "$FINAL_CHECKPOINT" ]; then
    echo "Completed checkpoint already exists; nothing to do: $FINAL_CHECKPOINT"
    exit 0
fi

mkdir -p "$PROJECT_ROOT/logs"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; validation training stopped before loading the model.")'

RESUME_ARGUMENTS=()
if [ -f "$LATEST_CHECKPOINT" ]; then
    echo "Resuming $DATASET $VARIANT from: $LATEST_CHECKPOINT"
    RESUME_ARGUMENTS=(--resume-checkpoint "$LATEST_CHECKPOINT")
else
    echo "Starting frozen validation run: $DATASET $VARIANT"
fi

python -m unittest discover -s src/spatial_msipl/tests -v
python -u scripts/train_spatial_msipl_production.py \
    --input "$INPUT" \
    --output "$OUTPUT" \
    --checkpoint-output "$CHECKPOINT_OUTPUT" \
    --variant "$VARIANT" \
    --epochs 100 \
    --batch-size 128 \
    --hidden-dim 512 \
    --latent-dim 5 \
    --learning-rate 0.001 \
    --spatial-lambda 0 \
    --seed 1 \
    --checkpoint-interval 5 \
    "${RESUME_ARGUMENTS[@]}"

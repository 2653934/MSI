#!/bin/bash
#SBATCH --job-name=s3pl-imzml
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-imzml-pilot-%j.out
#SBATCH --error=logs/s3pl-imzml-pilot-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
SOURCE_ROOT="/datasets/zsuliman/msi_data/gbm_imzml"
DATASET="${1:?Usage: run_s3pl_gbm_imzml_pilot.sh DATASET}"

case "$DATASET" in
    GBM108_positive|GBM108_negative) ;;
    *)
        echo "Pilot is restricted to GBM108_positive and GBM108_negative: $DATASET" >&2
        exit 2
        ;;
esac

PILOT_ROOT="$PROJECT_ROOT/reproducibility/s3pl_gbm_imzml/${DATASET}_p3_seed1"
INPUT_ROOT="/datasets/zsuliman/msi_data/gbm_imzml_s3pl_pilot/$DATASET"
PROVENANCE_ROOT="$PILOT_ROOT/provenance"
DATA_PATH="$INPUT_ROOT/${DATASET}.imzML"

if [[ -d "$PILOT_ROOT/results" || -d "$PILOT_ROOT/checkpoints" ]]; then
    echo "Pilot artifacts already exist; refusing to overwrite: $PILOT_ROOT" >&2
    exit 1
fi

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

echo "Pilot dataset: $DATASET"
echo "Allocated node: $(hostname)"
echo "CUDA_VISIBLE_DEVICES: ${CUDA_VISIBLE_DEVICES:-not-set}"
nvidia-smi --query-gpu=name,uuid --format=csv,noheader || true

python -c 'import sys, torch; sys.exit(0 if torch.cuda.is_available() else "CUDA is unavailable; refusing to run S3PL on CPU.")'

mkdir -p "$PROVENANCE_ROOT"
cd "$PROJECT_ROOT"
sha256sum \
    scripts/prepare_s3pl_gbm_imzml_pilot.py \
    slurm_jobs/run_s3pl_gbm_imzml_pilot.sh \
    slurm_jobs/submit_s3pl_gbm_imzml_pilot.sh \
    > "$PROVENANCE_ROOT/scripts_sha256.txt"
python -u scripts/prepare_s3pl_gbm_imzml_pilot.py \
    --dataset "$DATASET" \
    --source-root "$SOURCE_ROOT" \
    --output-root "$INPUT_ROOT"

sha256sum \
    "$SOURCE_ROOT/${DATASET}.imzML" \
    "$SOURCE_ROOT/${DATASET}.ibd" \
    "$SOURCE_ROOT/masks/${DATASET}_mask.npy" \
    "$INPUT_ROOT/${DATASET}.imzML" \
    "$INPUT_ROOT/masks/${DATASET}_mask.npy" \
    > "$PROVENANCE_ROOT/input_sha256.txt"

{
    printf 'dataset=%s\n' "$DATASET"
    printf 'input_format=official_imzML\n'
    printf 'prepared_input_root=%s\n' "$INPUT_ROOT"
    printf 'normalization=reference_spatial_max\n'
    printf 'spectral_patch_size=3\n'
    printf 'epochs=10\n'
    printf 'random_seed=1\n'
    printf 'mask_encoding=0_normal_1_tumour_at_measured_coordinates\n'
    printf 'slurm_job_id=%s\n' "$SLURM_JOB_ID"
    printf 'created_utc=%s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
} > "$PROVENANCE_ROOT/manifest.txt"

cd "$PROJECT_ROOT/baselines/s3pl"
python main.py \
    --data_dir "$DATA_PATH" \
    --artifact_root "$PILOT_ROOT" \
    --number_classes 2 \
    --n_epochs 10 \
    --spectral_patch_size 3 \
    --normalization reference_spatial_max \
    --eval_picking

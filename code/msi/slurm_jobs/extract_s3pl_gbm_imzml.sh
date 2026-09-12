#!/bin/bash
#SBATCH --job-name=gbm-imzml-extract
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=2G
#SBATCH --output=logs/gbm-imzml-extract-%j.out
#SBATCH --error=logs/gbm-imzml-extract-%j.err

set -euo pipefail

ARCHIVE="/datasets/zsuliman/msi_data/zips/gbm_data.zip"
EXPECTED_SHA256="a69a42464932c5c2af95b7fb2259cf7fd9590ff86ff0e5f170398e9519aa097f"
DATA_ROOT="/datasets/zsuliman/msi_data"
DESTINATION="$DATA_ROOT/gbm_imzml"
STAGING="$DATA_ROOT/.gbm-imzml-extract-$SLURM_JOB_ID"
DATASETS=(
    GBM108_negative
    GBM108_positive
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)

if [[ ! -f "$ARCHIVE" ]]; then
    echo "Archive not found: $ARCHIVE" >&2
    exit 1
fi
if [[ -e "$DESTINATION" ]]; then
    echo "Destination already exists; refusing to overwrite: $DESTINATION" >&2
    exit 1
fi
if [[ -e "$STAGING" ]]; then
    echo "Staging path already exists; refusing to reuse it: $STAGING" >&2
    exit 1
fi

actual_sha256=$(sha256sum "$ARCHIVE" | awk '{print $1}')
if [[ "$actual_sha256" != "$EXPECTED_SHA256" ]]; then
    echo "Archive checksum mismatch" >&2
    echo "Expected: $EXPECTED_SHA256" >&2
    echo "Actual:   $actual_sha256" >&2
    exit 1
fi

mkdir "$STAGING"

echo "=========================================="
echo "       OFFICIAL GBM IMZML EXTRACTION"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Archive: $ARCHIVE"
echo "Verified SHA-256: $actual_sha256"
echo "Destination: $DESTINATION"
echo

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN=python3
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
else
    echo "Python is unavailable on the compute node." >&2
    exit 1
fi

echo "Extraction started: $(date)"
"$PYTHON_BIN" -m zipfile -e "$ARCHIVE" "$STAGING"
echo "Extraction finished: $(date)"

SOURCE="$STAGING/gbm_data"
if [[ ! -d "$SOURCE" ]]; then
    echo "Expected top-level archive directory not found: $SOURCE" >&2
    exit 1
fi

for dataset in "${DATASETS[@]}"; do
    for suffix in imzML ibd; do
        path="$SOURCE/$dataset.$suffix"
        if [[ ! -s "$path" ]]; then
            echo "Missing or empty data file: $path" >&2
            exit 1
        fi
    done

    mask="$SOURCE/masks/${dataset}_mask.npy"
    if [[ ! -s "$mask" ]]; then
        echo "Missing or empty mask: $mask" >&2
        exit 1
    fi
done

mv "$SOURCE" "$DESTINATION"
rmdir "$STAGING"

echo
echo "Validated all eight imzML/ibd pairs and masks."
du -sh "$DESTINATION"
find "$DESTINATION" -maxdepth 2 -type f -printf '%P %s bytes\n' | sort


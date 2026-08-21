#!/bin/bash
#SBATCH --job-name=massnet-extract
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=bigbatch
#SBATCH --time=01:00:00
#SBATCH --mem=4G
#SBATCH --output=logs/massnet-extract-%j.out
#SBATCH --error=logs/massnet-extract-%j.err

set -eo pipefail

DATA_ROOT="/datasets/zsuliman/msi_data"
ARCHIVE="$DATA_ROOT/zips/ST002045_massNet.7z"
DESTINATION="$DATA_ROOT/gbm_massnet"
STAGING="$DESTINATION/.extract-$SLURM_JOB_ID"

EXPECTED_FILES=(
    GBM108_negative.h5
    GBM108_positive.h5
    GBM12_1.h5
    GBM12_2.h5
    GBM22_1.h5
    GBM22_2.h5
    GBM39_1.h5
    GBM39_2.h5
)

if [[ ! -f "$ARCHIVE" ]]; then
    echo "Archive not found: $ARCHIVE" >&2
    exit 1
fi

mkdir -p "$DESTINATION" "$STAGING"

echo "=========================================="
echo "       MASSNET GBM EXTRACTION"
echo "=========================================="
echo "Date: $(date)"
echo "Job ID: $SLURM_JOB_ID"
echo "Node: $(hostname)"
echo "Archive: $ARCHIVE"
echo "Destination: $DESTINATION"
echo "Staging: $STAGING"
echo

source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate data_tools_env

echo "Extractor environment activated: $CONDA_DEFAULT_ENV"
echo "Starting archive extraction at $(date)..."

if command -v 7z >/dev/null 2>&1; then
    7z x -y "$ARCHIVE" "-o$STAGING"
elif command -v 7zz >/dev/null 2>&1; then
    7zz x -y "$ARCHIVE" "-o$STAGING"
elif command -v 7za >/dev/null 2>&1; then
    7za x -y "$ARCHIVE" "-o$STAGING"
elif command -v bsdtar >/dev/null 2>&1; then
    bsdtar -xf "$ARCHIVE" -C "$STAGING"
elif python -c "import py7zr" >/dev/null 2>&1; then
    python -c "import py7zr, sys; archive, destination = sys.argv[1:]; py7zr.SevenZipFile(archive, mode='r').extractall(path=destination)" "$ARCHIVE" "$STAGING" &
    EXTRACTOR_PID=$!

    while kill -0 "$EXTRACTOR_PID" 2>/dev/null; do
        EXTRACTED_SIZE=$(du -sh "$STAGING" 2>/dev/null | cut -f1)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Extracted so far: ${EXTRACTED_SIZE:-0}"
        sleep 30
    done

    wait "$EXTRACTOR_PID"
else
    echo "No 7z-compatible extractor is available in data_tools_env." >&2
    exit 1
fi

echo "Archive extraction finished at $(date)."
echo "Validating expected HDF5 files..."

SOURCE="$STAGING/massNet_Raw_h5"
if [[ ! -d "$SOURCE" ]]; then
    echo "Expected archive directory not found: $SOURCE" >&2
    exit 1
fi

for filename in "${EXPECTED_FILES[@]}"; do
    if [[ ! -s "$SOURCE/$filename" ]]; then
        echo "Missing or empty extracted file: $SOURCE/$filename" >&2
        exit 1
    fi
    if [[ -e "$DESTINATION/$filename" ]]; then
        echo "Destination already exists; refusing to overwrite: $DESTINATION/$filename" >&2
        exit 1
    fi
done

for filename in "${EXPECTED_FILES[@]}"; do
    mv "$SOURCE/$filename" "$DESTINATION/$filename"
done

rmdir "$SOURCE"
rmdir "$STAGING"

echo "MassNet GBM extraction complete:"
du -sh "$DESTINATION"
find "$DESTINATION" -maxdepth 1 -type f -name '*.h5' -printf '%f %s bytes\n' | sort

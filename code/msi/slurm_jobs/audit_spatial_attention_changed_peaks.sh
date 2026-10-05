#!/bin/bash
#SBATCH --job-name=attention-peak-audit
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=02:00:00
#SBATCH --output=logs/attention-peak-audit-%j.out
#SBATCH --error=logs/attention-peak-audit-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {160TopL|GBM22_2}" >&2
    exit 2
fi
case "$1" in
    160TopL)
        INPUT=/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5
        MATCHED_COUNT=210 ;;
    GBM22_2)
        INPUT=/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5
        MATCHED_COUNT=464 ;;
    *) echo "Unsupported section: $1" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
RANKING_DIR="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$1"
ORIGINAL="$PROJECT_ROOT/results/experiments/spatial_attention_context/${1}_seed1/real_attention/peak_evaluation/ig_matched_${MATCHED_COUNT}_bins.csv"
OUTPUT="$PROJECT_ROOT/results/diagnostics/spatial_attention_changed_peaks/$1"
for required in "$INPUT" "$RANKING_DIR/summary.json" "$RANKING_DIR/rankings.npz" "$ORIGINAL"; do
    if [ ! -f "$required" ]; then
        echo "Missing frozen input: $required" >&2
        exit 1
    fi
done

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4

"$HOME/miniconda3/envs/s3pl_env/bin/python" -m unittest discover \
    -s src/spatial_msipl/tests -p test_attention_changed_peaks.py

"$HOME/miniconda3/envs/s3pl_env/bin/python" -u scripts/audit_spatial_attention_changed_peaks.py \
    --input "$INPUT" --ranking-dir "$RANKING_DIR" \
    --original-peaks "$ORIGINAL" --output "$OUTPUT"

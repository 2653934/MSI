#!/bin/bash
#SBATCH --job-name=attention-edge-mass
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --output=logs/attention-edge-mass-%j.out
#SBATCH --error=logs/attention-edge-mass-%j.err

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 160TopL|GBM22_2" >&2
    exit 2
fi
case "$1" in
    160TopL) INPUT="/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5" ;;
    GBM22_2) INPUT="/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5" ;;
    *) echo "Initial audit is limited to 160TopL and GBM22_2" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
PRIOR="$PROJECT_ROOT/results/diagnostics/spatial_attention_boundary/$1/summary.json"
OUTPUT="$PROJECT_ROOT/results/diagnostics/spatial_attention_boundary_alignment/$1"
for required in "$INPUT" "$PRIOR"; do
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
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
"$PYTHON" -m unittest discover -s src/spatial_msipl/tests -p test_attention_boundary_alignment.py
"$PYTHON" -u scripts/audit_attention_boundary_alignment.py \
    --input "$INPUT" --boundary-summary "$PRIOR" --output "$OUTPUT"

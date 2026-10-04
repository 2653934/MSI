#!/bin/bash
#SBATCH --job-name=attention-swap
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/attention-swap-%j.out
#SBATCH --error=logs/attention-swap-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {160TopL|GBM22_2}" >&2
    exit 2
fi
case "$1" in
    160TopL) INPUT=/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5 ;;
    GBM22_2) INPUT=/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5 ;;
    *) echo "Unsupported section: $1" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${1}_seed1/real_attention/checkpoint.pt"
ATTRIBUTION="$PROJECT_ROOT/results/experiments/spatial_attention_context/${1}_seed1/real_attention/attribution"
OUTPUT="$PROJECT_ROOT/results/diagnostics/spatial_attention_input_swap/$1"
if [ ! -f "$INPUT" ] || [ ! -f "$CHECKPOINT" ] || [ ! -f "$ATTRIBUTION/gmm_parameters.npz" ]; then
    echo "Missing input, trained checkpoint or frozen attribution/GMM for $1" >&2
    exit 1
fi
if grep -q '"status": "valid"' "$OUTPUT/summary.json" 2>/dev/null; then
    echo "Already valid: $OUTPUT/summary.json"
    exit 0
fi

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4
export MKL_NUM_THREADS=4

python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; input-swap audit stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

python -m unittest discover -s src/spatial_msipl/tests -p test_attention_input_swap.py

python -u scripts/audit_spatial_attention_input_swap.py \
    --input "$INPUT" \
    --checkpoint "$CHECKPOINT" \
    --attribution-dir "$ATTRIBUTION" \
    --output "$OUTPUT" \
    --shuffle-seed 1701 --batch-size 64

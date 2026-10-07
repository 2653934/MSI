#!/bin/bash
#SBATCH --job-name=attention-weight-ablation
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --output=logs/attention-weight-ablation-%j.out
#SBATCH --error=logs/attention-weight-ablation-%j.err

set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {160TopL|GBM22_2}" >&2
    exit 2
fi
case "$1" in
    160TopL) INPUT=/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5; COUNT=210 ;;
    GBM22_2) INPUT=/datasets/zsuliman/msi_data/gbm_massnet/GBM22_2.h5; COUNT=464 ;;
    *) echo "Unsupported pilot section: $1" >&2; exit 2 ;;
esac

ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${1}_seed1/real_attention/checkpoint.pt"
REAL="$ROOT/results/experiments/spatial_attention_context/${1}_seed1/real_attention"
SWAP="$ROOT/results/diagnostics/spatial_attention_input_swap/$1/summary.json"
OUTPUT="$ROOT/results/diagnostics/spatial_attention_uniform_weight_ablation/$1"
for required in "$INPUT" "$CHECKPOINT" "$REAL/attribution/summary.json" \
    "$REAL/peak_evaluation/summary.json" "$SWAP"; do
    if [ ! -f "$required" ]; then
        echo "Missing frozen artifact: $required" >&2
        exit 1
    fi
done
if grep -q '"status": "valid"' "$OUTPUT/summary.json" 2>/dev/null &&
   [ -f "$OUTPUT/rankings.npz" ]; then
    echo "Already valid: $OUTPUT/summary.json"
    exit 0
fi

cd "$ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$ROOT/src:$ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4

python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; weight ablation stopped before data/model load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
print(f"CUDA warm-up passed on {torch.cuda.get_device_name(0)}: {float(probe.sum())}", flush=True)
PY

python -m unittest discover -s src/spatial_msipl/tests -p test_attention_frozen_ranking_swap.py
python -u scripts/evaluate_spatial_attention_frozen_ranking_swap.py \
    --input "$INPUT" --checkpoint "$CHECKPOINT" \
    --attribution-dir "$REAL/attribution" \
    --peak-evaluation-summary "$REAL/peak_evaluation/summary.json" \
    --input-swap-summary "$SWAP" --output "$OUTPUT" \
    --matched-count "$COUNT" --intervention uniform_weights

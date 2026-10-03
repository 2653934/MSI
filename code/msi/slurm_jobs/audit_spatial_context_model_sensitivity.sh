#!/bin/bash
#SBATCH --job-name=context-response
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster59,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/context-response-%j.out
#SBATCH --error=logs/context-response-%j.err

# Conda's activation hooks reference variables that may be unset.
# Keep strict error/pipe handling, but do not enable nounset before activation.
set -eo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: sbatch $0 {160TopL|GBM22_2}" >&2
    exit 2
fi
DATASET="$1"
case "$DATASET" in
    160TopL) INPUT="/datasets/zsuliman/msi_data/cac_msipl/${DATASET}.h5" ;;
    GBM22_2) INPUT="/datasets/zsuliman/msi_data/gbm_massnet/${DATASET}.h5" ;;
    *) echo "Unsupported pilot section: $DATASET" >&2; exit 2 ;;
esac

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4

python -m unittest discover -s src/spatial_msipl/tests -p test_spatial_context_model_sensitivity.py
python - <<'PY'
import sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; diagnostic stopped before loading a checkpoint")
probe = torch.ones((32, 32), device="cuda")
torch.cuda.synchronize()
print(f"CUDA warm-up passed: {torch.cuda.get_device_name(0)} {float(probe.sum())}", flush=True)
PY

CHECKPOINT_BASE="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${DATASET}_seed1"
if [[ "$DATASET" == *TopL ]]; then
    REAL_CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac/production/${DATASET}_seed1/uniform_mean/checkpoint.pt"
else
    REAL_CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/production/${DATASET}_seed1/uniform_mean/checkpoint.pt"
fi
SHUFFLED_CHECKPOINT="$CHECKPOINT_BASE/shuffled_p3/checkpoint.pt"
INPUT_AUDIT="results/diagnostics/spatial_context_information/${DATASET}_pixels.csv"
for path in "$INPUT" "$REAL_CHECKPOINT" "$SHUFFLED_CHECKPOINT" "$INPUT_AUDIT"; do
    if [[ ! -f "$path" ]]; then
        echo "Missing prerequisite: $path" >&2
        exit 1
    fi
done

python -u scripts/audit_spatial_context_model_sensitivity.py \
    --input "$INPUT" \
    --input-audit "$INPUT_AUDIT" \
    --real-checkpoint "$REAL_CHECKPOINT" \
    --shuffled-checkpoint "$SHUFFLED_CHECKPOINT" \
    --output-dir results/diagnostics/spatial_context_model_sensitivity \
    --batch-size 8

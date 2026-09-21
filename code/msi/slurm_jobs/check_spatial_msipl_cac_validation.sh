#!/bin/bash

set -eo pipefail

MODE="${1:-progress}"
case "$MODE" in
    progress|complete) ;;
    *)
        echo "Usage: bash $0 {progress|complete}" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/cac"
AUDIT_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_cac_validation/training_audit.json"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

echo "=== SLURM CAMPAIGN STATE ==="
squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R" || true

echo
echo "=== FATAL CAC LOG MARKERS ==="
matches=$(grep -H -E \
    'Traceback \(most recent call last\)|CUDA is unavailable|CUDA initialization.*unknown error|Killed|Out Of Memory|oom-kill' \
    logs/spatial-cac-val-*.err 2>/dev/null || true)
if [ -n "$matches" ]; then
    printf '%s\n' "$matches"
    echo "A failed first allocation may still be recovered by its continuation."
else
    echo "No fatal markers found."
fi

echo
echo "=== CHECKPOINT AND RESULT AUDIT ==="
arguments=(
    --project-root "$PROJECT_ROOT"
    --checkpoint-root "$CHECKPOINT_ROOT"
)
if [ "$MODE" = "complete" ]; then
    arguments+=(--require-complete --output "$AUDIT_OUTPUT")
fi
python -u scripts/audit_spatial_cac_validation_training.py "${arguments[@]}"

if [ "$MODE" = "progress" ]; then
    echo
    echo "Pilot success means both 40TopL variants reach 100/100 and COMPLETE."
else
    echo
    echo "Strict completion audit passed. Saved: $AUDIT_OUTPUT"
fi

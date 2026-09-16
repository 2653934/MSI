#!/bin/bash

set -eo pipefail

MODE="${1:-progress}"
case "$MODE" in
    preflight|progress|complete) ;;
    *)
        echo "Usage: bash $0 {preflight|progress|complete}" >&2
        exit 2
        ;;
esac

PROJECT_ROOT="$HOME/msi"
CHECKPOINT_ROOT="/datasets/zsuliman/msi_checkpoints/spatial_msipl"
AUDIT_OUTPUT="$PROJECT_ROOT/results/experiments/spatial_msipl_gbm_validation/training_audit.json"

cd "$PROJECT_ROOT"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env

echo "=== SLURM CAMPAIGN STATE ==="
squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R" || true

echo
echo "=== FATAL LOG MARKERS OBSERVED SO FAR ==="
fatal_matches=$(grep -H -E \
    'Traceback \(most recent call last\)|CUDA is unavailable|CUDA initialization.*unknown error|Killed|Out Of Memory|oom-kill' \
    logs/spatial-gbm-val-*.err 2>/dev/null || true)
if [ -n "$fatal_matches" ]; then
    printf '%s\n' "$fatal_matches"
    echo
    echo "A failed first allocation is not automatically fatal: its afterany continuation may recover it."
else
    echo "No fatal markers found in existing validation logs."
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
python -u scripts/audit_spatial_gbm_validation_training.py "${arguments[@]}"

if [ "$MODE" = "preflight" ]; then
    echo
    echo "Preflight interpretation: running or pending jobs are expected. Investigate only immediate failures without a viable continuation."
elif [ "$MODE" = "progress" ]; then
    echo
    echo "Progress interpretation: epochs should increase and checkpoint_latest.pt should appear after the first five epochs."
else
    echo
    echo "Strict completion audit passed. Saved: $AUDIT_OUTPUT"
fi

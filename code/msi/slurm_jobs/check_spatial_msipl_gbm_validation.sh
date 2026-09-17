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
echo "=== NEW FATAL LOG MARKERS ==="
acknowledged_failure_jobs=(
    55616 55618 55627 55628
    55631 55632 55633 55634 55635 55636 55637 55638
)

is_acknowledged_failure() {
    local candidate="$1"
    local acknowledged
    for acknowledged in "${acknowledged_failure_jobs[@]}"; do
        if [ "$candidate" = "$acknowledged" ]; then
            return 0
        fi
    done
    return 1
}

fatal_matches=""
for log_path in logs/spatial-gbm-val-*.err; do
    [ -e "$log_path" ] || continue
    job_id="${log_path%.err}"
    job_id="${job_id##*-}"
    if is_acknowledged_failure "$job_id"; then
        continue
    fi
    matches=$(grep -H -E \
        'Traceback \(most recent call last\)|CUDA is unavailable|CUDA initialization.*unknown error|Killed|Out Of Memory|oom-kill' \
        "$log_path" 2>/dev/null || true)
    if [ -n "$matches" ]; then
        fatal_matches+="${matches}"$'\n'
    fi
done
if [ -n "$fatal_matches" ]; then
    printf '%s\n' "$fatal_matches"
    echo
    echo "A failed allocation is not automatically fatal: its afterany continuation may recover it."
else
    echo "No new fatal markers found."
fi
echo "Acknowledged failed allocations suppressed: ${acknowledged_failure_jobs[*]}"

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

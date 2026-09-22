#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATASET="GBM108_positive"
VARIANTS=(central_only uniform_mean attention_sqrt_bins)
SEEDS=(1 2 3)

cd "$PROJECT_ROOT"

echo "=== ACTIVE SEED EVALUATION JOBS ==="
printf '%-18s %-30s %-2s %-10s %-24s\n' "JOBID" "NAME" "ST" "TIME" "NODELIST(REASON)"
active_jobs=$(squeue -h -u "$USER" -o "%.18i %.30j %.2t %.10M %.24R" | \
    grep -E 'ig-seed|gbm-ig' || true)
if [ -n "$active_jobs" ]; then
    printf '%s\n' "$active_jobs"
else
    echo "No active seed-evaluation jobs."
fi

echo
echo "=== ATTRIBUTION AND PEAK-EVALUATION AUDIT ==="
printf '%-22s %-8s %-14s %-14s\n' "VARIANT" "SEED" "ATTRIBUTION" "PEAK_EVAL"
complete=0
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        attribution="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed${seed}/${variant}/summary.json"
        evaluation="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed${seed}/${variant}/summary.json"
        attr_status="MISSING"
        eval_status="MISSING"
        if grep -q '"status": "valid' "$attribution" 2>/dev/null; then
            attr_status="COMPLETE"
        fi
        if grep -q '"status": "complete"' "$evaluation" 2>/dev/null; then
            eval_status="COMPLETE"
            complete=$((complete + 1))
        fi
        printf '%-22s %-8s %-14s %-14s\n' "$variant" "$seed" "$attr_status" "$eval_status"
    done
done

echo
echo "Complete model evaluations: $complete/9 (three variants x three training seeds)"
if [ "$complete" -eq 9 ]; then
    echo "All seed-stability evaluations are complete."
else
    echo "Seeds 2 and 3 are new; seed 1 should already be complete from the frozen pilot."
fi

echo
echo "=== RECENT FATAL MARKERS ==="
fatal=$(grep -H -E 'CUDA is unavailable|Traceback|FileNotFoundError|RuntimeError|FAILED' \
    logs/gbm-ig-*-seed*-*.err 2>/dev/null | tail -n 20 || true)
if [ -n "$fatal" ]; then
    printf '%s\n' "$fatal"
else
    echo "No matching fatal markers found."
fi

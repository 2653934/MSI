#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATASET="GBM108_positive"
VARIANTS=(central_only uniform_mean depthwise attention attention_sqrt_bins)

cd "$PROJECT_ROOT"

echo "=== ACTIVE JOBS ==="
squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R" || true

echo
echo "=== RESULT AUDIT ==="
printf '%-22s %-12s %-12s\n' "VARIANT" "ATTRIBUTION" "PEAK_EVAL"
incomplete=0
for variant in "${VARIANTS[@]}"; do
    attribution="$PROJECT_ROOT/results/experiments/spatial_msipl_gmm_integrated_gradients/${DATASET}_seed1/${variant}/summary.json"
    evaluation="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed1/${variant}/summary.json"

    attribution_status="MISSING"
    evaluation_status="MISSING"
    if grep -Eq '"status": "(valid|valid_pilot)"' "$attribution" 2>/dev/null; then
        attribution_status="VALID"
    fi
    if grep -q '"status": "complete"' "$evaluation" 2>/dev/null; then
        evaluation_status="COMPLETE"
    fi
    if [ "$attribution_status" != "VALID" ] || [ "$evaluation_status" != "COMPLETE" ]; then
        incomplete=$((incomplete + 1))
    fi
    printf '%-22s %-12s %-12s\n' "$variant" "$attribution_status" "$evaluation_status"
done

echo
if (( incomplete == 0 )); then
    echo "All five matched neighbourhood attribution evaluations are complete."
else
    echo "$incomplete variant(s) remain incomplete."
fi

echo
echo "=== RECENT FATAL MARKERS ==="
if ! grep -H -E \
    'Traceback|CUDA is unavailable|CUDA warm-up failed|Required 100-epoch checkpoint is missing|needs_more_ig_steps' \
    logs/neighbourhood-peak-*.err 2>/dev/null | tail -n 30; then
    echo "No matching fatal markers found."
fi

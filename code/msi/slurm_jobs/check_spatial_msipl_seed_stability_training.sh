#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
VARIANTS=(central_only uniform_mean attention_sqrt_bins)
SEEDS=(2 3)

cd "$PROJECT_ROOT"

echo "=== ACTIVE JOBS ==="
squeue -u "$USER" -o "%.18i %.26j %.2t %.10M %.24R" || true

echo
echo "=== TRAINING-SEED AUDIT ==="
printf '%-22s %-8s %-10s %-14s\n' "VARIANT" "SEED" "EPOCHS" "STATUS"
complete=0
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        progress="$PROJECT_ROOT/results/experiments/spatial_msipl_training_seed_stability/GBM108_positive_seed${seed}/${variant}/progress.json"
        epochs=0
        status="NOT_STARTED"
        if [ -f "$progress" ]; then
            epochs=$(sed -n 's/.*"completed_epochs": *\([0-9][0-9]*\).*/\1/p' "$progress" | head -n 1)
            epochs=${epochs:-0}
            status=$(sed -n 's/.*"status": *"\([^"]*\)".*/\1/p' "$progress" | head -n 1)
            status=${status:-UNKNOWN}
        fi
        if [ "$epochs" = "100" ]; then
            complete=$((complete + 1))
        fi
        printf '%-22s %-8s %-10s %-14s\n' "$variant" "$seed" "$epochs/100" "$status"
    done
done

echo
echo "Complete configurations: $complete/6"
echo
echo "=== RECENT FATAL MARKERS ==="
fatal_found=0
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        latest_log=$(ls -1t \
            logs/spatial-seed-"${variant}"-s"${seed}"-*.err \
            2>/dev/null | head -n 1 || true)
        if [ -n "$latest_log" ] && grep -H -E \
            'CUDA is unavailable; seed-stability|CUDA warm-up failed|RuntimeError:|ValueError:|FileNotFoundError:|OSError:' \
            "$latest_log"; then
            fatal_found=1
        fi
    done
done
if [ "$fatal_found" -eq 0 ]; then
    echo "No matching fatal markers found."
fi

echo
echo "Note: bare Traceback lines are intentionally ignored because some unit tests"
echo "exercise expected exception paths. Use sacct to determine job success or failure."

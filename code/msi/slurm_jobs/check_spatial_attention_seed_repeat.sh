#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
echo "=== ACTIVE JOBS ==="
squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R" | grep -E 'JOBID|attention-seed' || true
echo
echo "=== TRAINING-SEED REPEAT AUDIT ==="
printf '%-10s %-19s %-5s %-10s %-10s %-10s\n' SECTION ARM SEED TRAIN ATTRIBUTION PEAK_EVAL
complete=0
for seed in 2 3; do
    for section in 160TopL GBM22_2; do
        for arm in real_attention shuffled_attention; do
            root="$PROJECT_ROOT/results/experiments/spatial_attention_context_seed_stability/${section}_seed${seed}/$arm"
            checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context_seed_stability/${section}_seed${seed}/$arm/checkpoint.pt"
            train=missing
            attribution=missing
            eval=missing
            if [ -f "$checkpoint" ] && grep -q '"status": "complete"' "$root/summary.json" 2>/dev/null; then train=complete; fi
            if grep -q '"status": "valid"' "$root/attribution/summary.json" 2>/dev/null; then attribution=valid; fi
            if grep -q '"status": "complete"' "$root/peak_evaluation/summary.json" 2>/dev/null; then
                eval=complete
                complete=$((complete + 1))
            fi
            printf '%-10s %-19s %-5s %-10s %-10s %-10s\n' "$section" "$arm" "$seed" "$train" "$attribution" "$eval"
        done
    done
done
echo "New repeat evaluations complete: $complete/8; existing seed 1 is separate."
echo "Resubmit only a missing or failed array index; completed stages are reused."

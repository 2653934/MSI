#!/bin/bash
set -eo pipefail

PROJECT_ROOT="$HOME/msi"
printf '%-10s %-19s %-11s %-9s %-9s %-9s\n' DATASET ARM TRAIN RECON IG PEAK_EVAL
for dataset in 160TopL GBM22_2; do
    for arm in real_attention shuffled_attention; do
        root="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/$arm"
        checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${dataset}_seed1/$arm/checkpoint.pt"
        train=missing
        recon=missing
        ig=missing
        peak=missing
        if [ -f "$checkpoint" ] && grep -q '"status": "complete"' "$root/summary.json" 2>/dev/null; then
            train=complete
        elif [ -f "$root/summary.json" ] || [ -f "${checkpoint%.pt}_latest.pt" ]; then
            train=partial
        fi
        if [ -f "$root/reconstruction/reconstruction.json" ]; then recon=complete; fi
        if grep -q '"status": "valid"' "$root/attribution/summary.json" 2>/dev/null; then ig=complete; fi
        if grep -q '"status": "complete"' "$root/peak_evaluation/summary.json" 2>/dev/null; then peak=complete; fi
        printf '%-10s %-19s %-11s %-9s %-9s %-9s\n' "$dataset" "$arm" "$train" "$recon" "$ig" "$peak"
    done
done
echo
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R'

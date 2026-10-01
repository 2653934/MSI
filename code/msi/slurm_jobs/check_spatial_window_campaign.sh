#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
ARMS=(uniform_p5 zero_p3 shuffled_p3)
complete_train=0
complete_eval=0
missing_train=()
missing_eval=()

printf '%-5s %-18s %-13s %-10s %-10s\n' ID DATASET ARM TRAIN EVAL
for index in $(seq 0 47); do
    dataset="${DATASETS[index / 3]}"
    arm="${ARMS[index % 3]}"
    checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_pilot/${dataset}_seed1/$arm/checkpoint.pt"
    root="$PROJECT_ROOT/results/experiments/spatial_msipl_window_pilot/${dataset}_seed1/$arm"
    train=missing
    eval=missing
    if [ -f "$checkpoint" ] && grep -q '"status": "complete"' "$root/summary.json" 2>/dev/null; then
        train=complete
        ((complete_train+=1))
    else
        missing_train+=("$index")
    fi
    if grep -q '"status": "complete"' "$root/peak_evaluation/summary.json" 2>/dev/null && \
       grep -q '"status": "valid"' "$root/attribution/summary.json" 2>/dev/null && \
       [ -f "$root/reconstruction/reconstruction.json" ]; then
        eval=complete
        ((complete_eval+=1))
    else
        missing_eval+=("$index")
    fi
    printf '%-5s %-18s %-13s %-10s %-10s\n' "$index" "$dataset" "$arm" "$train" "$eval"
done
echo "Training complete: $complete_train/48 (including the 3 pilot configurations)"
echo "Evaluation complete: $complete_eval/48 (including the 3 pilot configurations)"
echo "Missing training array indices: ${missing_train[*]:-none}"
echo "Missing evaluation array indices: ${missing_eval[*]:-none}"
echo "Check active jobs before resubmitting any missing indices."
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R'

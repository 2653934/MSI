#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
training_complete=0
audit_complete=0
printf '%-18s %-12s %-12s\n' SECTION TRAINING INPUT_SWAP
for dataset in "${DATASETS[@]}"; do
    checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${dataset}_seed1/real_attention/checkpoint.pt"
    training="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/real_attention/summary.json"
    audit="$PROJECT_ROOT/results/diagnostics/spatial_attention_input_swap/$dataset/summary.json"
    training_status=missing
    audit_status=missing
    if [ -f "$checkpoint" ] && grep -q '"status": "complete"' "$training" 2>/dev/null; then
        training_status=complete
        training_complete=$((training_complete + 1))
    elif [ -f "$training" ]; then
        training_status=partial
    fi
    if grep -q '"status": "valid"' "$audit" 2>/dev/null; then
        audit_status=valid
        audit_complete=$((audit_complete + 1))
    elif [ -f "$audit" ]; then
        audit_status=partial
    fi
    printf '%-18s %-12s %-12s\n' "$dataset" "$training_status" "$audit_status"
done
echo "Complete training: $training_complete/16; valid input-swap audits: $audit_complete/16"
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R' | head -n 30

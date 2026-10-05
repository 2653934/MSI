#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
complete=0
printf '%-3s %-18s %-12s %-12s %-12s\n' ID SECTION REAL_IG PEAK_EVAL RANK_SWAP
for index in "${!DATASETS[@]}"; do
    dataset="${DATASETS[index]}"
    real="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/real_attention"
    swap="$PROJECT_ROOT/results/diagnostics/spatial_attention_frozen_ranking_swap/$dataset"
    ig=missing
    eval=missing
    rank=missing
    if grep -q '"status": "valid"' "$real/attribution/summary.json" 2>/dev/null; then ig=valid; fi
    if grep -q '"status": "complete"' "$real/peak_evaluation/summary.json" 2>/dev/null; then eval=complete; fi
    if grep -q '"status": "valid"' "$swap/summary.json" 2>/dev/null &&
       [ -f "$swap/rankings.npz" ]; then
        rank=valid
        complete=$((complete + 1))
    fi
    printf '%-3s %-18s %-12s %-12s %-12s\n' "$index" "$dataset" "$ig" "$eval" "$rank"
done
echo "Valid frozen ranking swaps: $complete/16"
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R'
if [ "${1:-progress}" = complete ] && [ "$complete" -ne 16 ]; then
    exit 1
fi

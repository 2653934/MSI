#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

datasets=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
variants=(uniform_mean central_only)
complete=0
expected=24

printf '%-12s %-16s %-12s\n' "DATASET" "EVALUATION" "STATUS"
for dataset in "${datasets[@]}"; do
    reconstruction="results/experiments/spatial_msipl_cac_reconstruction/${dataset}_seed1/evaluation/comparison.json"
    if grep -q '"status": "complete"' "$reconstruction" 2>/dev/null; then
        status="COMPLETE"
        complete=$((complete + 1))
    else
        status="INCOMPLETE"
    fi
    printf '%-12s %-16s %-12s\n' "$dataset" "reconstruction" "$status"

    for variant in "${variants[@]}"; do
        attribution="results/experiments/spatial_msipl_cac_gmm_integrated_gradients/${dataset}_seed1/${variant}/summary.json"
        evaluation="results/experiments/spatial_msipl_cac_attributed_peak_evaluation/${dataset}_seed1/${variant}/summary.json"
        if grep -q '"status": "valid"' "$attribution" 2>/dev/null \
            && grep -q '"status": "complete"' "$evaluation" 2>/dev/null; then
            status="COMPLETE"
            complete=$((complete + 1))
        else
            status="INCOMPLETE"
        fi
        printf '%-12s %-16s %-12s\n' "$dataset" "$variant" "$status"
    done
done

echo
echo "Complete evaluations: $complete/$expected"
if [ "$complete" -eq "$expected" ]; then
    echo "All CAC reconstruction and attribution evaluations are complete."
else
    echo "Wait for active jobs, then inspect failed jobs before resubmitting anything."
fi

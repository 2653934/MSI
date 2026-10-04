#!/bin/bash
set -eo pipefail

if [ "$#" -ne 0 ]; then
    echo "Usage: bash $0" >&2
    exit 2
fi

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
if squeue -u "$USER" -h -o '%j' | grep -Fxq 'attention-context'; then
    echo 'An attention-context job is already active or pending; wait before submitting again.' >&2
    exit 1
fi
for dataset in 160TopL GBM22_2; do
    for arm in real_attention shuffled_attention; do
        output="$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/$arm/summary.json"
        checkpoint="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${dataset}_seed1/$arm/checkpoint.pt"
        if [ -f "$checkpoint" ] && grep -q '"status": "complete"' "$output" 2>/dev/null; then
            printf '%-10s %-19s %s\n' "$dataset" "$arm" COMPLETE
            continue
        fi
        mkdir -p "${output%/summary.json}" "${checkpoint%/checkpoint.pt}"
        submission=$(sbatch slurm_jobs/run_spatial_attention_context_training.sh "$dataset" "$arm")
        printf '%-10s %-19s %s\n' "$dataset" "$arm" "$submission"
    done
done

echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'

#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
VARIANTS=(central_only uniform_mean attention_sqrt_bins)
SEEDS=(2 3)

cd "$PROJECT_ROOT"
mkdir -p logs

EXCLUDE=""
if [ -f "$QUARANTINE_FILE" ]; then
    EXCLUDE=$(sed \
        -e 's/\r$//' \
        -e 's/#.*$//' \
        -e '/^[[:space:]]*$/d' \
        "$QUARANTINE_FILE" | sort -u | paste -sd, -)
fi

printf '%-22s %-8s %-12s\n' "VARIANT" "SEED" "JOB_ID"
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        progress="$PROJECT_ROOT/results/experiments/spatial_msipl_training_seed_stability/GBM108_positive_seed${seed}/${variant}/progress.json"
        if grep -q '"completed_epochs": 100' "$progress" 2>/dev/null; then
            printf '%-22s %-8s %-12s\n' "$variant" "$seed" "COMPLETE"
            continue
        fi

        arguments=(
            --job-name="seed-${variant}-s${seed}"
            --output="logs/spatial-seed-${variant}-s${seed}-%j.out"
            --error="logs/spatial-seed-${variant}-s${seed}-%j.err"
        )
        if [ -n "$EXCLUDE" ]; then
            arguments+=(--exclude="$EXCLUDE")
        fi
        submission=$(sbatch \
            "${arguments[@]}" \
            slurm_jobs/run_spatial_msipl_seed_stability_training.sh \
            "$variant" "$seed")
        job_id=${submission##* }
        printf '%-22s %-8s %-12s\n' "$variant" "$seed" "$job_id"
    done
done

echo
echo "Submitted the six targeted training-seed stability runs."
echo "Monitor with: bash slurm_jobs/check_spatial_msipl_seed_stability_training.sh"


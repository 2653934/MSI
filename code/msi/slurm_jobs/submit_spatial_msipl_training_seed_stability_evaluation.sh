#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
DATASET="GBM108_positive"
MATCHED_COUNT=530
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

gate_ids=()
printf '%-22s %-8s %-12s %-12s\n' "VARIANT" "SEED" "WORKER" "GATE"
for variant in "${VARIANTS[@]}"; do
    for seed in "${SEEDS[@]}"; do
        summary="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed${seed}/${variant}/summary.json"
        job_name="ig-seed-${variant}-s${seed}"

        if grep -q '"status": "complete"' "$summary" 2>/dev/null; then
            printf '%-22s %-8s %-12s %-12s\n' "$variant" "$seed" "COMPLETE" "-"
            continue
        fi

        active_job=$(squeue -h -n "$job_name" -o "%i" | head -n 1)
        if [ -n "$active_job" ]; then
            printf '%-22s %-8s %-12s %-12s\n' "$variant" "$seed" "ACTIVE:$active_job" "-"
            continue
        fi

        gate_submission=$(sbatch \
            --hold \
            --job-name="ig-seed-gate" \
            --nodes=1 \
            --ntasks=1 \
            --cpus-per-task=1 \
            --partition=bigbatch \
            --time=00:01:00 \
            --mem=256M \
            --output="logs/ig-seed-gate-%j.out" \
            --error="logs/ig-seed-gate-%j.err" \
            --wrap='true')
        gate_id=${gate_submission##* }

        arguments=(
            --export="ALL,GBM_GATE_JOB_ID=$gate_id"
            --job-name="$job_name"
            --output="logs/gbm-ig-${variant}-seed${seed}-%j.out"
            --error="logs/gbm-ig-${variant}-seed${seed}-%j.err"
        )
        if [ -n "$EXCLUDE" ]; then
            arguments+=(--exclude="$EXCLUDE")
        fi

        if ! worker_submission=$(sbatch \
            "${arguments[@]}" \
            slurm_jobs/run_spatial_msipl_gbm_attribution.sh \
            "$DATASET" "$MATCHED_COUNT" "$variant" "$seed")
        then
            scancel "$gate_id" || true
            exit 1
        fi
        worker_id=${worker_submission##* }
        scontrol update JobId="$gate_id" Dependency="afterok:$worker_id"
        scontrol release "$gate_id"
        gate_ids+=("$gate_id")
        printf '%-22s %-8s %-12s %-12s\n' "$variant" "$seed" "$worker_id" "$gate_id"
    done
done

if (( ${#gate_ids[@]} > 0 )); then
    dependency=$(IFS=:; echo "${gate_ids[*]}")
    summary_submission=$(sbatch --dependency="afterok:$dependency" \
        slurm_jobs/summarise_spatial_msipl_training_seed_stability.sh)
else
    summary_submission=$(sbatch \
        slurm_jobs/summarise_spatial_msipl_training_seed_stability.sh)
fi
summary_job_id=${summary_submission##* }

echo
echo "Submitted the incomplete seed-2/3 evaluations with evaluation randomness fixed at seed 1."
echo "CUDA quarantine: ${EXCLUDE:-none}"
echo "Summary job: $summary_job_id"
echo 'Monitor with: bash slurm_jobs/check_spatial_msipl_training_seed_stability_evaluation.sh'

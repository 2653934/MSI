#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

CUDA_QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
if [ ! -f "$CUDA_QUARANTINE_FILE" ]; then
    echo "Missing CUDA quarantine file: $CUDA_QUARANTINE_FILE" >&2
    exit 1
fi
BASE_EXCLUDES=$(sed -e 's/\r$//' \
    -e 's/#.*$//' \
    -e '/^[[:space:]]*$/d' \
    "$CUDA_QUARANTINE_FILE" | sort -u | paste -sd, -)
if [ -z "$BASE_EXCLUDES" ]; then
    echo "CUDA quarantine file did not contain any nodes." >&2
    exit 1
fi

datasets=(
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)
counts=(458 453 478 589 464 686 523)

worker_ids=()
gate_ids=()
printf '%-18s %-14s %-12s %-12s\n' \
    "DATASET" "MATCHED_PEAKS" "WORKER" "GATE"
for index in "${!datasets[@]}"; do
    dataset="${datasets[$index]}"
    count="${counts[$index]}"
    summary="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${dataset}_seed1/uniform_mean/summary.json"
    if grep -q '"status": "complete"' "$summary" 2>/dev/null; then
        printf '%-18s %-14s %-12s %-12s\n' \
            "$dataset" "$count" "COMPLETE" "-"
        continue
    fi

    gate_submission=$(sbatch \
        --hold \
        --job-name="ig-gate-${dataset}" \
        --nodes=1 \
        --ntasks=1 \
        --cpus-per-task=1 \
        --partition=bigbatch \
        --time=00:01:00 \
        --mem=256M \
        --output="logs/ig-gate-%j.out" \
        --error="logs/ig-gate-%j.err" \
        --wrap='true')
    gate_id=${gate_submission##* }

    if ! worker_submission=$(sbatch \
        --exclude="$BASE_EXCLUDES" \
        --export="ALL,GBM_GATE_JOB_ID=$gate_id" \
        --job-name="ig-${dataset}" \
        slurm_jobs/run_spatial_msipl_gbm_attribution.sh "$dataset" "$count")
    then
        scancel "$gate_id" || true
        exit 1
    fi
    worker_id=${worker_submission##* }

    scontrol update JobId="$gate_id" Dependency="afterok:$worker_id"
    scontrol release "$gate_id"
    worker_ids+=("$worker_id")
    gate_ids+=("$gate_id")
    printf '%-18s %-14s %-12s %-12s\n' \
        "$dataset" "$count" "$worker_id" "$gate_id"
done

if (( ${#gate_ids[@]} > 0 )); then
    dependency=$(IFS=:; echo "${gate_ids[*]}")
    summary_submission=$(sbatch --dependency="afterok:$dependency" \
        slurm_jobs/summarise_spatial_msipl_gbm_attribution.sh)
else
    summary_submission=$(sbatch \
        slurm_jobs/summarise_spatial_msipl_gbm_attribution.sh)
fi
summary_job_id=${summary_submission##* }

echo
echo "Submitted ${#worker_ids[@]} incomplete whole-GBM attribution evaluations."
echo "GBM108_positive reuses the completed frozen evaluation."
echo "Production CUDA quarantine: $BASE_EXCLUDES"
echo "Each gate follows its dataset's current retry job."
echo "Summary job: $summary_job_id (runs after every dataset gate succeeds)"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'

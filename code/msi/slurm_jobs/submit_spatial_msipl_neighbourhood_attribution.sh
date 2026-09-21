#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
QUARANTINE_FILE="$PROJECT_ROOT/slurm_jobs/gpu_cuda_quarantine.txt"
DATASET="GBM108_positive"
MATCHED_PEAKS=530
VARIANTS=(depthwise attention attention_sqrt_bins)

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

printf '%-22s %-12s\n' "VARIANT" "JOB_ID"
for variant in "${VARIANTS[@]}"; do
    result="$PROJECT_ROOT/results/experiments/spatial_msipl_attributed_peak_evaluation/${DATASET}_seed1/${variant}/summary.json"
    if grep -q '"status": "complete"' "$result" 2>/dev/null; then
        printf '%-22s %-12s\n' "$variant" "COMPLETE"
        continue
    fi

    arguments=(
        --job-name="peak-${variant}"
        --output="logs/neighbourhood-peak-${variant}-%j.out"
        --error="logs/neighbourhood-peak-${variant}-%j.err"
    )
    if [ -n "$EXCLUDE" ]; then
        arguments+=(--exclude="$EXCLUDE")
    fi

    submission=$(sbatch \
        "${arguments[@]}" \
        slurm_jobs/run_spatial_msipl_gbm_attribution.sh \
        "$DATASET" "$MATCHED_PEAKS" "$variant")
    job_id=${submission##* }
    printf '%-22s %-12s\n' "$variant" "$job_id"
done

echo
echo "Centre-only and uniform-mean evaluations are already complete."
echo "Monitor with: squeue -u \"\$USER\" -o \"%.18i %.24j %.2t %.10M %.24R\""

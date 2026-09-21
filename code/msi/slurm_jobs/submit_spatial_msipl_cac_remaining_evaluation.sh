#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

datasets=(160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
declare -A matched_counts=(
    [160TopL]=210
    [200TopL]=221
    [240TopL]=255
    [280TopL]=245
    [360TopL]=247
    [400TopL]=133
    [520TopL]=232
)

printf '%-12s %-12s %-12s %-12s\n' \
    "DATASET" "RECON_JOB" "SPATIAL_IG" "CENTRAL_IG"
for dataset in "${datasets[@]}"; do
    count="${matched_counts[$dataset]}"
    reconstruction=$(sbatch \
        --job-name="recon-${dataset}" \
        slurm_jobs/evaluate_spatial_msipl_cac_reconstruction.sh \
        "$dataset")
    spatial=$(sbatch \
        --job-name="igs-${dataset}" \
        slurm_jobs/run_spatial_msipl_cac_attribution.sh \
        "$dataset" "$count" uniform_mean)
    central=$(sbatch \
        --job-name="igc-${dataset}" \
        slurm_jobs/run_spatial_msipl_cac_attribution.sh \
        "$dataset" "$count" central_only)
    printf '%-12s %-12s %-12s %-12s\n' \
        "$dataset" "${reconstruction##* }" "${spatial##* }" "${central##* }"
done

echo
echo "Submitted 7 reconstruction and 14 matched attribution evaluations."
echo "The attribution workers automatically retry a failed CUDA warm-up."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'

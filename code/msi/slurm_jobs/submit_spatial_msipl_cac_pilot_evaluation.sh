#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

reconstruction=$(sbatch \
    slurm_jobs/evaluate_spatial_msipl_cac_reconstruction.sh 40TopL)
spatial=$(sbatch \
    --job-name="cac-ig-40-spatial" \
    slurm_jobs/run_spatial_msipl_cac_attribution.sh \
    40TopL 315 uniform_mean)
central=$(sbatch \
    --job-name="cac-ig-40-central" \
    slurm_jobs/run_spatial_msipl_cac_attribution.sh \
    40TopL 315 central_only)

printf '%-24s %s\n' "EVALUATION" "JOB_ID"
printf '%-24s %s\n' "deterministic_recon" "${reconstruction##* }"
printf '%-24s %s\n' "spatial_ig" "${spatial##* }"
printf '%-24s %s\n' "centre_only_ig" "${central##* }"
echo
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'

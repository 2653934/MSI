#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

printf '%-12s %-12s\n' "LAMBDA" "JOB_ID"
for spatial_lambda in 0.01 0.1 1.0; do
    submission=$(sbatch slurm_jobs/run_spatial_msipl_lambda_pilot.sh "$spatial_lambda")
    job_id=${submission##* }
    printf '%-12s %-12s\n' "$spatial_lambda" "$job_id"
done

echo
echo "Submitted 3 independent five-epoch spatial-loss pilots."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'

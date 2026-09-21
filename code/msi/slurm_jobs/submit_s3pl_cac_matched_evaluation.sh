#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)

cd "$PROJECT_ROOT"
mkdir -p logs

printf '%-12s %-12s\n' "DATASET" "JOB_ID"
for dataset in "${DATASETS[@]}"; do
    submission=$(sbatch \
        --job-name="s3pl-match-${dataset}" \
        --output="logs/s3pl-match-${dataset}-%j.out" \
        --error="logs/s3pl-match-${dataset}-%j.err" \
        slurm_jobs/run_s3pl_cac_matched_evaluation.sh \
        "$dataset")
    job_id=${submission##* }
    printf '%-12s %-12s\n' "$dataset" "$job_id"
done

echo
echo "Submitted eight evaluation-only S3PL jobs; existing checkpoints are reused."
echo "No S3PL model training will be repeated."

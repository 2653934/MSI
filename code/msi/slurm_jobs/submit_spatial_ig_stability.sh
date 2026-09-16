#!/bin/bash

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"

job_ids=()
printf '%-16s %-12s\n' "SAMPLING_SEED" "JOB_ID"
for sampling_seed in 2 3 4; do
    submission=$(sbatch slurm_jobs/run_spatial_ig_stability_repeat.sh "$sampling_seed")
    job_id=${submission##* }
    job_ids+=("$job_id")
    printf '%-16s %-12s\n' "$sampling_seed" "$job_id"
done

dependency=$(IFS=:; echo "${job_ids[*]}")
summary_submission=$(sbatch --dependency="afterok:$dependency" slurm_jobs/summarise_spatial_ig_stability.sh)
summary_job_id=${summary_submission##* }

echo
echo "Submitted 3 attribution-sampling repeats with the model and GMM seed fixed."
echo "Summary job: $summary_job_id (runs only after all 3 repeats succeed)"
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'

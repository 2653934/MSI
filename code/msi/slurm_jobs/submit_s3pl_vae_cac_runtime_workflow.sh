#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
runner="slurm_jobs/run_s3pl_vae_cac_runtime_workflow.sh"
bash -n "$runner" slurm_jobs/submit_s3pl_vae_cac_runtime_workflow.sh \
    slurm_jobs/check_s3pl_vae_cac_runtime_workflow.sh
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
    slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

submission="$(sbatch --parsable --partition=batch --exclude="$exclude" "$runner")"
job_id="${submission%%;*}"
echo "Submitted isolated 160TopL S3PL-versus-VAE runtime workflow as job $job_id on batch."
echo "Monitor: squeue -j $job_id -o '%.18i %.24j %.2t %.10M %.24R'"
echo "Check: bash slurm_jobs/check_s3pl_vae_cac_runtime_workflow.sh $job_id"

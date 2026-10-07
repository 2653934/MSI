#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi
pilot_submission="$(sbatch --parsable --exclude="$exclude" --array=1 slurm_jobs/audit_s3pl_cac_frozen_topology.sh)"
pilot_id="${pilot_submission%%;*}"
rest_submission="$(sbatch --parsable --exclude="$exclude" --dependency="afterok:${pilot_id}" --array=0,2-7 slurm_jobs/audit_s3pl_cac_frozen_topology.sh)"
rest_id="${rest_submission%%;*}"
echo "160TopL frozen-topology pilot: $pilot_id"
echo "Other seven sections (only after pilot success): $rest_id"
echo "No training or existing checkpoint changes; each section compares three inputs in its own job."
echo "Monitor: squeue -j $pilot_id,$rest_id -o '%.18i %.24j %.2t %.10M %.24R'"

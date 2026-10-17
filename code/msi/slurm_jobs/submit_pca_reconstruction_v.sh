#!/bin/bash
# Login-node submitter for the Test V PCA reconstruction addendum. Each use
# requires Zayd's explicit OK. The run script fixes the required batch partition.
set -euo pipefail
cd "$HOME/msi"
runner=slurm_jobs/run_pca_reconstruction_v.sh
bash -n "$runner"
root=results/diagnostics/pca_reconstruction_V
mkdir -p logs "$root/provenance"
job="$(sbatch --parsable --array=0-23%4 "$runner")"
echo "${job%%;*} indices=0-23 concurrency=4 partition=batch" \
    | tee -a "$root/provenance/slurm_job_ids.txt"


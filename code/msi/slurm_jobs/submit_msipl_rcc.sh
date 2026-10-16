#!/bin/bash
# Login-node submitter for overnight item 4 (legacy msiPL on RCC): file checks, mkdir and sbatch only.
#   bash slurm_jobs/submit_msipl_rcc.sh [--indices LIST] [--concurrency N]
# Default: all 8 runs, at most 2 running. CPU (TensorFlow legacy env), bigbatch --exclusive
# as the CAC legacy job.
set -euo pipefail
cd "$HOME/msi"
concurrency=2
indices="0-7"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_msipl_rcc.sh
bash -n "$runner"
mkdir -p logs results/baselines/msipl/rcc results/baselines/msipl/rcc_fixed_beta \
         results/baselines/msipl/rcc_provenance
job="$(sbatch --parsable --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} indices=$indices" | tee -a results/baselines/msipl/rcc_provenance/slurm_job_ids.txt

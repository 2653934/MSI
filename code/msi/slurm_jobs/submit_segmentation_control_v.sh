#!/bin/bash
# Login-node submitter for Test V (protocol 18 Section 6.4): file checks, mkdir and
# sbatch only. Each submission needs Zayd's OK. Test R keeps priority on bigbatch,
# whose QOS allows 48 submitted and 6 running jobs per user (each array task counts).
#   SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_segmentation_control_v.sh \
#       [--indices LIST] [--concurrency N]
# Default: all 24 tasks (0-7 GBM, 8-15 CAC, 16-23 RCC), at most 2 running (12:42).
set -euo pipefail
cd "$HOME/msi"
concurrency=""
indices="0-23"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
concurrency="${concurrency:-2}"
runner=slurm_jobs/run_segmentation_control_v.sh
bash -n "$runner"
source slurm_jobs/rcc_sections.sh
root=results/diagnostics/segmentation_control_V
mkdir -p logs "$root/provenance"
# Pre-create every section parent (concurrent mkdir race, 66114 / 69570_1).
for section in GBM108_negative GBM108_positive GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2; do
    mkdir -p "$root/GBM/${section}_seed1"
done
for section in 40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL; do
    mkdir -p "$root/CAC/${section}_seed1"
done
for section in "${RCC_SECTIONS[@]}"; do
    mkdir -p "$root/RCC/${section}_seed1"
done
job="$(sbatch --parsable --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} indices=$indices concurrency=$concurrency partition=${SBATCH_PARTITION:-script default}" \
    | tee -a "$root/provenance/slurm_job_ids.txt"

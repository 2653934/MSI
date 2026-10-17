#!/bin/bash
# Login-node submitter for Test S (protocol 18 Section 6.2): file checks, mkdir and
# sbatch only. Each submission needs Zayd's OK.
#   SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_spatial_segmentation_s.sh \
#       [--indices LIST] [--concurrency N]
# Default: all 24 tasks (0-7 GBM, 8-15 CAC, 16-23 RCC), at most 4 running.
set -euo pipefail
cd "$HOME/msi"
concurrency=4
indices="0-23"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_spatial_segmentation_s.sh
bash -n "$runner"
source slurm_jobs/rcc_sections.sh
root=results/diagnostics/spatial_segmentation_S
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
echo "${job%%;*} indices=$indices partition=${SBATCH_PARTITION:-script default}" \
    | tee -a "$root/provenance/slurm_job_ids.txt"

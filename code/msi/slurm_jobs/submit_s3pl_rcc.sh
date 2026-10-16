#!/bin/bash
# Login-node submitter for overnight item 3 (S3PL on RCC): file checks, mkdir and sbatch only.
#   bash slurm_jobs/submit_s3pl_rcc.sh gate                     CPU staging + adapter gate
#   bash slurm_jobs/submit_s3pl_rcc.sh train [--indices LIST] [--concurrency N]
# train refuses unless the gate passed; default all 24 tasks (seeds 1-3), at most 2 running.
# The CPU gate takes its partition from SBATCH_PARTITION (bigbatch while batch is down).
set -euo pipefail
cd "$HOME/msi"
stage="${1:?Usage: $0 gate|train [options]}"; shift
concurrency=2
indices="0-23"
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
mkdir -p logs reproducibility/s3pl_rcc/provenance results/validation/s3pl_rcc_adapter_gate
case "$stage" in
    gate)
        bash -n slurm_jobs/run_s3pl_rcc_gate.sh
        job="$(sbatch --parsable slurm_jobs/run_s3pl_rcc_gate.sh)" ;;
    train)
        bash -n slurm_jobs/run_s3pl_rcc.sh
        grep -q '"status": "passed"' results/validation/s3pl_rcc_adapter_gate/gate.json \
            || { echo "Adapter gate has not passed; training refused" >&2; exit 1; }
        exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
        [[ -n "$exclude" ]] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
        for seed in 1 2 3; do
            root="reproducibility/s3pl_rcc/seed${seed}_released"
            mkdir -p "$root/checkpoints/baselines/s3pl" "$root/logs/s3pl" \
                     "$root/results/baselines/s3pl" "$root/run_logs" "$root/provenance"
            if [[ ! -f "$root/provenance/manifest.txt" ]]; then
                {
                    echo "purpose=overnight item 3: S3PL on RCC, paper settings (supervisor chat 2026-10-16 22:07)"
                    echo "random_seed=$seed; released RNG path"
                    echo "settings=p 5, z 1024, d1 51, d2 1, 10 epochs, batch 16, lr 1e-2, reference_spatial_max, n = num_GT_peaks, 3 classes"
                    echo "input=/datasets/zsuliman/msi_data/rcc_s3pl (staged copies, adapter gate passed)"
                    echo "excluded_nodes=$exclude"
                    echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
                } > "$root/provenance/manifest.txt"
            fi
        done
        job="$(sbatch --parsable --exclude="$exclude" --array="${indices}%${concurrency}" \
            slurm_jobs/run_s3pl_rcc.sh)" ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
echo "${job%%;*} stage=$stage indices=$indices" | tee -a reproducibility/s3pl_rcc/provenance/slurm_job_ids.txt

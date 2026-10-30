#!/bin/bash
# Login-node submitter for the IG completeness reruns (protocol 18 Section 6.3
# amendment "30 October: IG completeness reruns"): file checks, mkdir and sbatch
# only. Each submission needs Zayd's OK.
#   bash slurm_jobs/submit_ig_steps.sh ig INDICES [--concurrency N]
#       GPU (bigbatch, quarantine excluded, no --exclusive): IG + matched evaluation.
#       0-11 first (128-step reruns, 64- and 128-step controls); 12-15 (256 steps)
#       only for arms that fail at 128.
#   bash slurm_jobs/submit_ig_steps.sh fair INDICES [--concurrency N] [--after JOBID]
#       CPU (batch): fair scoring of the same rows.
# INDICES is a list such as "0-11" or "12,14". Refuses any row whose output exists.
set -euo pipefail
cd "$HOME/msi"
stage="${1:?Usage: $0 ig|fair INDICES [options]}"
indices="${2:?Usage: $0 ig|fair INDICES [options]}"
shift 2
source slurm_jobs/ig_steps_sections.sh
concurrency=""
after=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --after) after="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
expanded="$(test_r_expand_indices "$indices")"
[ -n "$expanded" ] || { echo "Empty index list" >&2; exit 2; }
sbatch_options=()
case "$stage" in
    ig)
        [ -z "$after" ] || { echo "ig takes no dependency" >&2; exit 2; }
        runner=slurm_jobs/run_ig_steps_rerun.sh
        concurrency="${concurrency:-4}"
        exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
                   slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
        [ -n "$exclude" ] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
        sbatch_options+=(--exclude="$exclude") ;;
    fair)
        runner=slurm_jobs/run_ig_steps_fair_scoring.sh
        concurrency="${concurrency:-4}"
        [ -z "$after" ] || sbatch_options+=(--dependency="afterok:$after") ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
provenance="$IG_STEPS_RESULTS/ig_steps_rerun_20261030/provenance"
mkdir -p logs "$provenance"
# Shared parents are created here, before any array task starts (mkdir race, 66114);
# the per-task folders themselves must not exist yet.
for index in $expanded; do
    ig_steps_task "$index"
    root="$(ig_steps_result_root "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM" "$TASK_STEPS" "$TASK_KIND")"
    if [ "$stage" = ig ]; then
        [ ! -e "$root/attribution" ] || { echo "Task $index output exists: $root" >&2; exit 3; }
        mkdir -p "$(dirname "$root")"
    else
        for scope in bin_level_only with_approved_partitions; do
            output="$(ig_steps_fair_output "$scope" "$TASK_SECTION" "$TASK_SEED" "$TASK_ARM" "$TASK_STEPS")"
            [ ! -e "$output" ] || { echo "Task $index output exists: $output" >&2; exit 3; }
            mkdir -p "$(dirname "$output")"
        done
    fi
done
bash -n "$runner"
job="$(sbatch --parsable ${sbatch_options[@]+"${sbatch_options[@]}"} --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} stage=$stage indices=$indices after=${after:-none} excluded=${exclude:-none} partition=${SBATCH_PARTITION:-script default} submitted_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    | tee -a "$provenance/slurm_job_ids.txt"

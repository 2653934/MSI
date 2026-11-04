#!/bin/bash
# Login-node submitter for the label-free K analysis (protocol 18 Section 6.10; D56):
# file checks, mkdir and sbatch only. Each submission needs Zayd's OK.
#   bash slurm_jobs/submit_label_free_k.sh bic INDICES [options]
#       CPU (batch): BIC selection for LFK_BIC_TASKS rows (0-27).
#   bash slurm_jobs/submit_label_free_k.sh ig STEPS INDICES [options]
#       GPU (bigbatch unless --partition): GMM at the label-free K, IG, matched
#       evaluation, section-arms 0-47. STEPS 64 first; 128/256/512/1024 only for rows
#       whose previous step count is needs_more_ig_steps.
#   bash slurm_jobs/submit_label_free_k.sh fair INDICES [options]
#       CPU (batch): fair scoring of the decisive step count, section-arms 0-47.
# Options: --concurrency N (default 4), --partition P and --after JOBID, all passed on
# the sbatch command line (never as environment variables). GPU jobs always get
# --exclude = the CUDA quarantine plus mscluster144, and never --exclusive.
# INDICES is a list such as "0-47" or "3,9". Refuses any row whose output exists.
set -euo pipefail
cd "$HOME/msi"
usage="Usage: $0 bic INDICES | ig STEPS INDICES | fair INDICES [--concurrency N] [--partition P] [--after JOBID]"
stage="${1:?$usage}"; shift
steps=""
if [ "$stage" = ig ]; then steps="${1:?$usage}"; shift; fi
indices="${1:?$usage}"; shift
source slurm_jobs/label_free_k_sections.sh
concurrency=4
partition=""
after=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --partition) partition="${2:?}"; shift 2 ;;
        --after) after="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
expanded="$(test_r_expand_indices "$indices")"
[ -n "$expanded" ] || { echo "Empty index list" >&2; exit 2; }
sbatch_options=()
[ -z "$partition" ] || sbatch_options+=(--partition="$partition")
[ -z "$after" ] || sbatch_options+=(--dependency="afterok:$after")
runner_arguments=()
exclude=""
case "$stage" in
    bic)
        runner=slurm_jobs/run_label_free_k_bic.sh
        for index in $expanded; do
            lfk_bic_task "$index"
            selection="$(lfk_bic_selection "$TASK_SECTION" "$TASK_ARM")"
            [ ! -e "$selection" ] || { echo "Row $index output exists: $selection" >&2; exit 3; }
            mkdir -p "$(dirname "$(dirname "$selection")")"
        done ;;
    ig)
        lfk_check_steps "$steps"
        runner=slurm_jobs/run_label_free_k_ig.sh
        runner_arguments=("$steps")
        exclude="$( (sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
                     slurm_jobs/gpu_cuda_quarantine.txt; echo mscluster144) | sort -u | paste -sd, -)"
        sbatch_options+=(--exclude="$exclude")
        for index in $expanded; do
            lfk_task "$index"
            root="$(lfk_result_root "$TASK_SECTION" "$TASK_ARM" "$steps")"
            [ ! -e "$root" ] || { echo "Row $index output exists: $root" >&2; exit 3; }
            if [ "$steps" != 64 ]; then
                previous="$(lfk_result_root "$TASK_SECTION" "$TASK_ARM" "$(lfk_previous_steps "$steps")")"
                grep -q '"status": "needs_more_ig_steps"' "$previous/attribution/summary.json" 2>/dev/null \
                    || { echo "Row $index: $previous is not needs_more_ig_steps" >&2; exit 2; }
            fi
            # Shared parents are created here, before any array task starts (66114).
            mkdir -p "$(dirname "$root")"
        done ;;
    fair)
        runner=slurm_jobs/run_label_free_k_fair_scoring.sh
        for index in $expanded; do
            lfk_task "$index"
            mkdir -p "$LFK_FAIR/${TASK_SECTION}_seed1/$TASK_ARM"
        done ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
provenance="$LFK_EXPERIMENTS/provenance"
mkdir -p logs "$provenance"
bash -n "$runner"
job="$(sbatch --parsable ${sbatch_options[@]+"${sbatch_options[@]}"} \
       --array="${indices}%${concurrency}" "$runner" ${runner_arguments[@]+"${runner_arguments[@]}"})"
echo "${job%%;*} stage=$stage steps=${steps:-none} indices=$indices after=${after:-none} excluded=${exclude:-none} partition=${partition:-script default} submitted_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    | tee -a "$provenance/slurm_job_ids.txt"

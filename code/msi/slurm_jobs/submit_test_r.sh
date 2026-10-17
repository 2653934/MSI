#!/bin/bash
# Login-node submitter for Test R (protocol 18 Section 6.3): file checks, mkdir,
# sacct and sbatch only. Each submission needs Zayd's OK.
# Training runs in two phases, because a single array does not order its tasks
# (09:45 "RCC and CAC first, then GBM"; Codex review 10:11):
#   bash slurm_jobs/submit_test_r.sh train-first SEED [--indices LIST] [--concurrency N]
#       GPU, RCC and CAC (tasks 0-31).
#   bash slurm_jobs/submit_test_r.sh train-gbm SEED --after FIRST_JOBID [...]
#       GPU, GBM (tasks 32-47), held until every first-phase task of FIRST_JOBID
#       succeeded (afterok).
#   bash slurm_jobs/submit_test_r.sh train-gbm SEED --after-reviewed FIRST_JOBID [...]
#       The same, without a dependency, only once sacct shows every task of
#       FIRST_JOBID finished (none pending or running). For the case where a
#       first-phase task ended in a predeclared "not done" (exit 4), which keeps an
#       afterok dependency from ever being met; use it only after that review.
#   SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_test_r.sh fair SEED \
#       [--indices LIST] [--concurrency N] [--after JOBID]
#       CPU, 24 tasks (one per section, both arms).
# GPU stages exclude the CUDA quarantine with sbatch --exclude (Slurm does not read
# SBATCH_EXCLUDE) and default to at most 3 running per seed (2 seeds x 3 <= 6).
set -euo pipefail
cd "$HOME/msi"
stage="${1:?Usage: $0 train-first|train-gbm|fair SEED [options]}"
seed="${2:?Usage: $0 train-first|train-gbm|fair SEED [options]}"
shift 2
source slurm_jobs/test_r_sections.sh
test_r_check_seed "$seed"
concurrency=""
indices=""
after=""
reviewed=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        --after) after="${2:?}"; shift 2 ;;
        --after-reviewed) reviewed="${2:?}"; shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
sbatch_options=()
case "$stage" in
    train-first)
        [ -z "$after$reviewed" ] || { echo "train-first takes no dependency" >&2; exit 2; }
        indices="${indices:-$TEST_R_PHASE_FIRST}"
        test_r_indices_in_phase first "$indices" ;;
    train-gbm)
        indices="${indices:-$TEST_R_PHASE_GBM}"
        test_r_indices_in_phase gbm "$indices"
        if [ -n "$after" ] && [ -z "$reviewed" ]; then
            sbatch_options+=(--dependency="afterok:$after")
        elif [ -n "$reviewed" ] && [ -z "$after" ]; then
            states="$(sacct -j "$reviewed" -X -n -o State | sed 's/[[:space:]]//g' | sort -u)"
            [ -n "$states" ] || { echo "No sacct record for job $reviewed" >&2; exit 1; }
            if grep -qE 'PENDING|RUNNING|REQUEUED|SUSPENDED' <<<"$states"; then
                echo "First phase $reviewed has not finished: $states" >&2; exit 1
            fi
        else
            echo "train-gbm needs exactly one of --after FIRST_JOBID or --after-reviewed FIRST_JOBID" >&2
            exit 2
        fi ;;
    fair)
        [ -z "$reviewed" ] || { echo "fair takes --after, not --after-reviewed" >&2; exit 2; }
        indices="${indices:-0-23}"
        [ -z "$after" ] || sbatch_options+=(--dependency="afterok:$after") ;;
    train)
        echo "Use train-first, then train-gbm (the phases are separate submissions)" >&2; exit 2 ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
provenance="$TEST_R_RESULTS/provenance"
mkdir -p logs "$provenance"
# Shared parents are created here, before any array task starts (mkdir race, 66114).
for section in "${TEST_R_SECTIONS[@]}"; do
    [ -f "$(test_r_input_for "$section")" ] || { echo "Missing input for $section" >&2; exit 1; }
    mkdir -p "$TEST_R_RESULTS/${section}_seed${seed}" "$TEST_R_CHECKPOINTS/${section}_seed${seed}"
    for scope in bin_level_only with_approved_partitions; do
        mkdir -p "$TEST_R_FAIR/$scope/${section}_seed${seed}"
    done
done
if [ "$stage" = fair ]; then
    runner=slurm_jobs/run_test_r_fair_scoring.sh
    concurrency="${concurrency:-4}"
else
    runner=slurm_jobs/run_test_r_campaign.sh
    concurrency="${concurrency:-3}"
    exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' \
               slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
    [ -n "$exclude" ] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
    sbatch_options+=(--exclude="$exclude")
    manifest="$provenance/manifest_seed${seed}.txt"
    if [[ ! -f "$manifest" ]]; then
        {
            echo "purpose=Test R training-seed replication (protocol 18 Section 6.3; supervisor chat 2026-10-17 09:45)"
            echo "training_seed=$seed (model initialisation and sample order); GMM seed 1; IG sampling seed 1"
            echo "training=3x3, 100 epochs, batch 128, hidden 512, latent 5, lr 1e-3, spatial_lambda 0, cached loader"
            echo "phases=first $TEST_R_PHASE_FIRST (RCC, CAC), then gbm $TEST_R_PHASE_GBM"
            echo "sections=${TEST_R_SECTIONS[*]}"
            echo "excluded_nodes=$exclude"
            echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
        } > "$manifest"
    fi
fi
bash -n "$runner"
job="$(sbatch --parsable ${sbatch_options[@]+"${sbatch_options[@]}"} --array="${indices}%${concurrency}" "$runner" "$seed")"
echo "${job%%;*} stage=$stage seed=$seed indices=$indices after=${after:-none} reviewed=${reviewed:-none} partition=${SBATCH_PARTITION:-script default}" \
    | tee -a "$provenance/slurm_job_ids.txt"

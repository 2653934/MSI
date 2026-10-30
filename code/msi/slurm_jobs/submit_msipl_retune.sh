#!/bin/bash
# Login-node submitter for the msiPL Beta re-tune (protocol 18 Section 6.8): file
# checks, mkdir and sbatch only. Each submission needs Zayd's OK.
#   bash slurm_jobs/submit_msipl_retune.sh sweep INDICES [--concurrency N]
#       CPU sweep (msipl_legacy). Pilot first: index 5 (GBM22_2).
#   bash slurm_jobs/submit_msipl_retune.sh score INDICES [--concurrency N] [--after JOBID]
#       CPU count-matched scoring (s3pl_env), both seed-1 arms per section.
# INDICES is a list such as "5" or "0-4,6-23". Refuses any row whose output exists.
set -euo pipefail
cd "$HOME/msi"
stage="${1:?Usage: $0 sweep|score INDICES [options]}"
indices="${2:?Usage: $0 sweep|score INDICES [options]}"
shift 2
source slurm_jobs/msipl_retune_sections.sh
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
    sweep)
        [ -z "$after" ] || { echo "sweep takes no dependency" >&2; exit 2; }
        runner=slurm_jobs/run_msipl_retune_sweep.sh
        concurrency="${concurrency:-6}" ;;
    score)
        runner=slurm_jobs/run_msipl_retune_scoring.sh
        concurrency="${concurrency:-6}"
        [ -z "$after" ] || sbatch_options+=(--dependency="afterok:$after") ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
provenance="$MSIPL_RETUNE_ROOT/provenance"
mkdir -p logs "$provenance"
# Shared parents are created here, before any array task starts (mkdir race, 66114).
for index in $expanded; do
    section="$(msipl_retune_section "$index")"
    if [ "$stage" = sweep ]; then
        output="$(msipl_retune_output "$section")"
        [ ! -e "$output/summary.json" ] && [ ! -e "$output/sweep.csv" ] \
            || { echo "Row $index output exists: $output" >&2; exit 3; }
        mkdir -p "$(dirname "$output")"
    else
        for arm in "${MSIPL_RETUNE_ARMS[@]}"; do
            output="$(msipl_retune_score_output "$section" "$arm")"
            [ ! -e "$output/summary.json" ] || { echo "Row $index output exists: $output" >&2; exit 3; }
            mkdir -p "$(dirname "$output")"
        done
    fi
done
bash -n "$runner"
job="$(sbatch --parsable ${sbatch_options[@]+"${sbatch_options[@]}"} --array="${indices}%${concurrency}" "$runner")"
echo "${job%%;*} stage=$stage indices=$indices after=${after:-none} partition=${SBATCH_PARTITION:-script default} submitted_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')" \
    | tee -a "$provenance/slurm_job_ids.txt"

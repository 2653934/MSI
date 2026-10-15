#!/bin/bash
# Login-node submitter for run_fair_scoring_extra_arm.sh: file checks, mkdir and
# sbatch only.
#   [SBATCH_PARTITION=bigbatch] bash slurm_jobs/submit_fair_scoring_extra_arm.sh ARM \
#        pilot|all|INDEX[,INDEX...] [--max-concurrent N] [--after JOBID]
# pilot = GBM22_2 (index 5; the largest section, and for ARM=attention it also
# exercises the A(b) reproduction and A(a) re-evaluation). G3 uses 5,9 only.
set -euo pipefail
cd "$HOME/msi"
source slurm_jobs/fair_scoring_sections.sh
arm="${1:?Usage: $0 ARM pilot|all|LIST [--max-concurrent N] [--after JOBID]}"
selection="${2:?Usage: $0 ARM pilot|all|LIST [--max-concurrent N] [--after JOBID]}"
shift 2
throttle=""
dependency=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --max-concurrent) throttle="%${2:?}"; shift 2 ;;
        --after) dependency=(--dependency="afterok:${2:?}"); shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
case "$arm" in
    attention|attention_centremask_p50|uniform_centremask_p50|uniform_p5|uniform_p7|uniform_p9) ;;
    shuffled_attention_centremask_p50)
        [[ "$selection" =~ ^(5|9|5,9|9,5)$ ]] || { echo "G3 exists for indices 5 (GBM22_2) and 9 (160TopL) only" >&2; exit 2; } ;;
    *) echo "Unknown arm: $arm" >&2; exit 2 ;;
esac
case "$selection" in
    pilot) indices="$FAIR_PILOT_INDEX" ;;
    all) indices="0-$(( ${#FAIR_SECTIONS[@]} - 1 ))" ;;
    *) [[ "$selection" =~ ^[0-9]+(,[0-9]+)*$ ]] || { echo "Bad index list" >&2; exit 2; }
       indices="$selection" ;;
esac
approval="results/diagnostics/peak_partition_audit/partition_approval.json"
[ -f "$approval" ] || { echo "Missing $approval" >&2; exit 1; }
root="results/diagnostics/fair_scoring_baselines/extra_arms"
# Shared parent folders first: concurrent tasks raced on mkdir in 66114.
for scope in bin_level_only with_approved_partitions; do
    for section in "${FAIR_SECTIONS[@]}"; do
        mkdir -p "$root/$scope/${section}_seed1"
    done
done
mkdir -p logs
bash -n slurm_jobs/run_fair_scoring_extra_arm.sh
job="$(sbatch --parsable --array="${indices}${throttle}" ${dependency[@]+"${dependency[@]}"} \
    slurm_jobs/run_fair_scoring_extra_arm.sh "$arm")"
job_id="${job%%;*}"
echo "$job_id $arm indices=$indices ${dependency[*]:-}" | tee -a "$root/slurm_job_ids.txt"
echo "Resources: sacct -j $job_id --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode"

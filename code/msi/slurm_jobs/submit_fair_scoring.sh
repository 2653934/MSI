#!/bin/bash
# Login-node submitter: file checks and sbatch only; no data processing.
#
#   bash slurm_jobs/submit_fair_scoring.sh pilot|all|INDEX[,INDEX...] \
#        [--approval /path/partition_approval.json] [--max-concurrent N]
#
# Each array task scores one section (both arms). Without --max-concurrent,
# Slurm/QOS limits apply. Run 'pilot' first and check sacct Elapsed/MaxRSS.
# The decision table is a separate job: run_fair_scoring_summary.sh.
set -euo pipefail
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source slurm_jobs/fair_scoring_sections.sh

selection="${1:?Usage: $0 pilot|all|INDEX[,INDEX...] [--approval FILE] [--max-concurrent N]}"
shift
throttle=""
approval=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --max-concurrent)
            [[ "${2:-}" =~ ^[1-9][0-9]*$ ]] || { echo "--max-concurrent needs a positive integer" >&2; exit 2; }
            throttle="%$2"; shift 2 ;;
        --approval)
            approval="$(readlink -f "${2:?--approval needs a file}")"
            [ -f "$approval" ] || { echo "Approval file not found: $2" >&2; exit 1; }
            shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
case "$selection" in
    pilot) indices="$FAIR_PILOT_INDEX" ;;
    all) indices="0-$(( ${#FAIR_SECTIONS[@]} - 1 ))" ;;
    *) [[ "$selection" =~ ^[0-9]+(,[0-9]+)*$ ]] || { echo "Bad index list" >&2; exit 2; }
       indices="$selection" ;;
esac

missing=0
for dataset in "${FAIR_SECTIONS[@]}"; do
    [ -f "$(fair_input_for "$dataset")" ] || { echo "Missing input for $dataset" >&2; missing=1; }
    if [ -n "$approval" ] && [ ! -f "results/diagnostics/peak_partition_audit/$dataset/partitions.npz" ]; then
        echo "Missing partition audit for $dataset" >&2; missing=1
    fi
done
[ "$missing" -eq 0 ] || exit 1

sbatch --array="${indices}${throttle}" --export=ALL,PARTITION_APPROVAL="$approval" \
    slurm_jobs/run_fair_scoring_array.sh
echo "Submitted fair-scoring indices ${indices}${throttle:+ (throttle ${throttle#%})}${approval:+ with approval $approval}."
echo "Then: sacct -j JOBID --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode"
echo "Decision table (separate job): sbatch slurm_jobs/run_fair_scoring_summary.sh [bin_level_only|with_approved_partitions]"

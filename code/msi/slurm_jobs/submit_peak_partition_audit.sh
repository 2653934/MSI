#!/bin/bash
# Login-node submitter: file checks and sbatch only; no data processing.
#
#   bash slurm_jobs/submit_peak_partition_audit.sh pilot          # GBM22_2 only
#   bash slurm_jobs/submit_peak_partition_audit.sh all [--max-concurrent N]
#   bash slurm_jobs/submit_peak_partition_audit.sh 0,3,9 [--max-concurrent N]
#
# Without --max-concurrent, Slurm/QOS limits apply; give N only to protect the
# shared filesystem deliberately. Run the pilot first and read its Elapsed and
# MaxRSS before submitting the remaining sections:
#   (the submitter prints the exact sacct command with the job ID)
set -euo pipefail
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
source slurm_jobs/fair_scoring_sections.sh

selection="${1:?Usage: $0 pilot|all|INDEX[,INDEX...] [--max-concurrent N]}"
shift
throttle=""
if [ "${1:-}" = "--max-concurrent" ]; then
    [[ "${2:-}" =~ ^[1-9][0-9]*$ ]] || { echo "--max-concurrent needs a positive integer" >&2; exit 2; }
    throttle="%$2"
elif [ "$#" -gt 0 ]; then
    echo "Unknown argument: $1" >&2; exit 2
fi
case "$selection" in
    pilot) indices="$FAIR_PILOT_INDEX" ;;
    all) indices="0-$(( ${#FAIR_SECTIONS[@]} - 1 ))" ;;
    *) [[ "$selection" =~ ^[0-9]+(,[0-9]+)*$ ]] || { echo "Bad index list" >&2; exit 2; }
       indices="$selection" ;;
esac

missing=0
for dataset in "${FAIR_SECTIONS[@]}"; do
    input="$(fair_input_for "$dataset")"
    [ -f "$input" ] || { echo "Missing input: $input" >&2; missing=1; }
done
[ "$missing" -eq 0 ] || exit 1

submission="$(sbatch --parsable --array="${indices}${throttle}" slurm_jobs/run_peak_partition_audit_array.sh)"
job_id="${submission%%;*}"
echo "Submitted partition audit job $job_id, indices ${indices}${throttle:+ (throttle ${throttle#%})}."
echo "Monitor: squeue -j $job_id"
echo "Resources: sacct -j $job_id --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode"
echo "Outputs: results/diagnostics/peak_partition_audit/<section>/summary.json"
echo "Review the S1 verdict (hard) and S2/S3 diagnostics before writing partition_approval.json."

#!/bin/bash
# Submit the three matched restartable 100-epoch production jobs.

set -euo pipefail

PROJECT_ROOT="${HOME}/msi"
RUNNER="${PROJECT_ROOT}/slurm_jobs/run_spatial_msipl_production.sh"
VARIANTS=(uniform_mean depthwise attention)

if [[ ! -f "$RUNNER" ]]; then
    echo "Runner not found: $RUNNER" >&2
    exit 1
fi

mkdir -p "${PROJECT_ROOT}/logs"
cd "$PROJECT_ROOT"

printf '%-18s %-12s %s\n' "VARIANT" "JOB_ID" "NODE SHARING"
for variant in "${VARIANTS[@]}"; do
    submission="$(sbatch --parsable "$RUNNER" "$variant")"
    job_id="${submission%%;*}"
    if ! [[ "$job_id" =~ ^[0-9]+$ ]]; then
        echo "Unexpected sbatch response for ${variant}: ${submission}" >&2
        exit 1
    fi
    printf '%-18s %-12s %s\n' "$variant" "$job_id" "exclusive"
done

echo
echo "Submitted ${#VARIANTS[@]} matched restartable production jobs."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'
echo "If a job stops after a periodic checkpoint, resubmit only that variant."

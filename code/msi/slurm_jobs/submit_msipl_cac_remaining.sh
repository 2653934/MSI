#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
RUNNER="$PROJECT_ROOT/slurm_jobs/run_msipl_cac_section.sh"
DATASETS=(160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)

cd "$PROJECT_ROOT"
mkdir -p logs

printf "%-12s %-12s %-12s\n" "DATASET" "JOB_ID" "TARGET_PEAKS"
for dataset in "${DATASETS[@]}"; do
    case "$dataset" in
        160TopL) target=199 ;;
        200TopL) target=214 ;;
        240TopL) target=257 ;;
        280TopL) target=238 ;;
        360TopL) target=246 ;;
        400TopL) target=137 ;;
        520TopL) target=257 ;;
    esac
    submission=$(sbatch "$RUNNER" "$dataset")
    job_id="${submission##* }"
    printf "%-12s %-12s %-12s\n" "$dataset" "$job_id" "$target"
done

echo
echo "Submitted 7 independent CAC legacy msiPL jobs."
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.20j %.2t %.10M %.20R"'
echo "Slurm may leave jobs pending because of the per-user job limit."

#!/bin/bash
# Login-safe status check: file existence and status strings only. Provenance
# validity is decided inside the Slurm jobs, not here.
#   bash slurm_jobs/check_fair_scoring_campaign.sh [bin_level_only|with_approved_partitions]
set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/fair_scoring_sections.sh"
VARIANT="${1:-bin_level_only}"
printf '%-4s %-16s %-10s %-14s %-14s\n' IDX SECTION AUDIT central_only uniform_mean
for index in "${!FAIR_SECTIONS[@]}"; do
    dataset="${FAIR_SECTIONS[index]}"
    audit="$PROJECT_ROOT/results/diagnostics/peak_partition_audit/$dataset/summary.json"
    a=$(grep -q '"status": "complete"' "$audit" 2>/dev/null && echo complete || echo -)
    states=()
    for arm in "${FAIR_ARMS[@]}"; do
        f="$PROJECT_ROOT/results/diagnostics/fair_scoring_baselines/$VARIANT/${dataset}_seed1/$arm/summary.json"
        states+=("$(grep -q '"status": "complete"' "$f" 2>/dev/null && echo complete || echo -)")
    done
    printf '%-4s %-16s %-10s %-14s %-14s\n' "$index" "$dataset" "$a" "${states[0]}" "${states[1]}"
done

#!/bin/bash
# Login-safe status listing for item G: prints status strings only, no scores.
# Exits 1 unless all 34 section-arms are complete.
set -uo pipefail
cd "$HOME/msi"
source slurm_jobs/fair_scoring_sections.sh
root="results/experiments/spatial_centremask_p50"
status_of() {
    grep -o '"status": "[a-z_]*"' "$1" 2>/dev/null | head -1 | cut -d'"' -f4
}
done_count=0
total=0
check() {
    local section="$1" arm="$2" folder="$root/${1}_seed1/$2"
    local training attribution evaluation mechanism="-"
    training="$(status_of "$folder/summary.json")"
    attribution="$(status_of "$folder/attribution/summary.json")"
    evaluation="$(status_of "$folder/peak_evaluation/summary.json")"
    if [[ "$arm" != uniform_centremask_p50 && ( "$section" == 160TopL || "$section" == GBM22_2 ) ]]; then
        mechanism="$(status_of "$folder/mechanism/attention_weights.json")"
        mechanism="${mechanism:-missing}"
    fi
    printf '%-16s %-36s train=%-9s ig=%-9s eval=%-9s mechanism=%s\n' "$section" "$arm" \
        "${training:-missing}" "${attribution:-missing}" "${evaluation:-missing}" "$mechanism"
    total=$((total + 1))
    if [[ "$training" == complete && "$attribution" == valid && "$evaluation" == complete \
          && ( "$mechanism" == - || "$mechanism" == valid ) ]]; then
        done_count=$((done_count + 1))
    fi
}
for section in "${FAIR_SECTIONS[@]}"; do check "$section" attention_centremask_p50; done
for section in "${FAIR_SECTIONS[@]}"; do check "$section" uniform_centremask_p50; done
for section in 160TopL GBM22_2; do check "$section" shuffled_attention_centremask_p50; done
echo "complete: $done_count/$total"
[[ "$done_count" -eq "$total" ]]

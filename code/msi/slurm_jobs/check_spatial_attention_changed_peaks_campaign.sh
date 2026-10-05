#!/bin/bash
set -euo pipefail

PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
complete=0
printf '%-3s %-18s %-12s\n' ID SECTION AUDIT
for index in "${!DATASETS[@]}"; do
    dataset="${DATASETS[index]}"
    output="$PROJECT_ROOT/results/diagnostics/spatial_attention_changed_peaks/$dataset"
    status=missing
    if grep -q '"status": "valid"' "$output/summary.json" 2>/dev/null &&
       [ -f "$output/changed_bins.csv" ] &&
       [ -f "$output/changed_bin_pcc.png" ] &&
       [ -f "$output/changed_ion_images.png" ]; then
        status=valid
        complete=$((complete + 1))
    elif [ -f "$output/summary.json" ]; then
        status=partial
    fi
    printf '%-3s %-18s %-12s\n' "$index" "$dataset" "$status"
done
echo "Valid changed-peak audits: $complete/16"
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R'
if [ "${1:-progress}" = complete ] && [ "$complete" -ne 16 ]; then
    exit 1
fi

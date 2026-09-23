#!/bin/bash
# Audit the GBM tuned-count evaluation campaign without changing any results.

set -euo pipefail

PROJECT_ROOT="$HOME/msi"
TUNED_LEGACY_ROOT="$PROJECT_ROOT/results/baselines/msipl/massnet_paper_aligned"
RESULT_ROOT="$PROJECT_ROOT/results/experiments/spatial_msipl_gbm_tuned_count_evaluation"
SUMMARY_ROOT="$PROJECT_ROOT/results/comparisons/spatial_msipl_gbm_tuned_counts"

DATASETS=(
    GBM108_positive
    GBM108_negative
    GBM12_1
    GBM12_2
    GBM22_1
    GBM22_2
    GBM39_1
    GBM39_2
)
VARIANTS=(central_only uniform_mean)

cd "$PROJECT_ROOT"

echo "=== ACTIVE TUNED-COUNT JOBS ==="
active_jobs=$(squeue -u "$USER" -h -n gbm-tuned-count \
    -o "%.18i %.24j %.2t %.10M %.24R")
printf '%18s %24s %2s %10s %24s\n' \
    "JOBID" "NAME" "ST" "TIME" "NODELIST(REASON)"
if [ -n "$active_jobs" ]; then
    printf '%s\n' "$active_jobs"
else
    echo "No active gbm-tuned-count job."
fi

echo
echo "=== RECENT FATAL MARKERS ==="
fatal=$(grep -EHi 'Traceback|FileNotFoundError|ValueError|RuntimeError|Killed|out of memory|No such file' \
    logs/gbm-tuned-count-*.err 2>/dev/null || true)
if [ -n "$fatal" ]; then
    printf '%s\n' "$fatal" | tail -n 30
else
    echo "No matching fatal markers found."
fi

echo
echo "=== RESULT AUDIT ==="
printf '%-18s %-8s %-14s %-14s\n' "DATASET" "COUNT" "CENTRE" "UNIFORM"
complete=0
for dataset in "${DATASETS[@]}"; do
    metrics="$TUNED_LEGACY_ROOT/$dataset/peak_metrics.json"
    if [ -f "$metrics" ]; then
        count=$(python - "$metrics" <<'PY'
import json
import sys
from pathlib import Path

print(int(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["unique_nearest_bins"]))
PY
        )
    else
        count="MISSING"
    fi

    statuses=()
    for variant in "${VARIANTS[@]}"; do
        summary="$RESULT_ROOT/${dataset}_seed1/$variant/summary.json"
        if [ -f "$summary" ]; then
            result_status=$(python - "$summary" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("status", "missing"))
PY
            )
        else
            result_status="missing"
        fi
        if [ "$result_status" = "complete" ]; then
            statuses+=("COMPLETE")
            complete=$((complete + 1))
        elif [ -f "$summary" ]; then
            statuses+=("INCOMPLETE")
        else
            statuses+=("MISSING")
        fi
    done
    printf '%-18s %-8s %-14s %-14s\n' \
        "$dataset" "$count" "${statuses[0]}" "${statuses[1]}"
done

echo
echo "Complete evaluations: $complete/16"
aggregate_status="missing"
if [ -f "$SUMMARY_ROOT/summary.json" ]; then
    aggregate_status=$(python - "$SUMMARY_ROOT/summary.json" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")).get("status", "missing"))
PY
    )
fi
if [ "$complete" -eq 16 ] && [ "$aggregate_status" = "complete" ]; then
    echo "Campaign and aggregate summary are complete."
    echo "Figure: $SUMMARY_ROOT/gbm_tuned_count_comparison.png"
else
    echo "The campaign is incomplete. The evaluation script is restart-safe:"
    echo "  sbatch slurm_jobs/run_spatial_msipl_gbm_tuned_count_evaluation.sh"
fi

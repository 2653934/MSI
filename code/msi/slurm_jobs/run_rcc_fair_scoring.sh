#!/bin/bash
# RCC step 5 (protocol 18 Section 6.1, item D step 2): fair scoring of both arms
# of one run with evaluate_fair_scoring_baselines.py --no-legacy, at bin level and,
# in mode p1, under the reviewer-approved RCC P1 partition. Each scope is scored
# twice: the primary (all three classes) and the secondary "sensitivity,
# cancer/normal classes only" (--class-subset 0 1; same rankings, same K_bin).
#   sbatch --array=0-7 slurm_jobs/run_rcc_fair_scoring.sh p1|bin-only   (via submit_rcc.sh)
# p1 requires results/diagnostics/peak_partition_audit_rcc/partition_approval.json;
# bin-only is used only if P1 failed S1 on RCC (recorded in Section 10).
# CPU only. Scores go to files; the Slurm .out holds status lines only.
#SBATCH --job-name=rcc-fair
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: the evaluator peaked at 0.91 GB on GBM22_2 (4,524 px x 85,062 bins);
# RCC runs are at most 3,564 px x 10,200 bins.
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/rcc-fair-%A_%a.out
#SBATCH --error=logs/rcc-fair-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
RESULTS="$PROJECT_ROOT/results"
source "$PROJECT_ROOT/slurm_jobs/rcc_sections.sh"
MODE="${1:?Usage: sbatch --array=0-7 $0 p1|bin-only}"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_rcc.sh}"
DATASET="${RCC_SECTIONS[TASK_ID]}"
INPUT="$(rcc_input_for "$DATASET")"
SECTION_ROOT="$RESULTS/experiments/rcc_spatial_msipl/${DATASET}_seed1"
BUDGET="$SECTION_ROOT/released_target_budget.json"
APPROVAL="$RESULTS/diagnostics/peak_partition_audit_rcc/partition_approval.json"
case "$MODE" in
    p1) [ -f "$APPROVAL" ] || { echo "Mode p1 needs $APPROVAL" >&2; exit 1; }
        SCOPES=(bin_level_only with_approved_partitions) ;;
    bin-only) SCOPES=(bin_level_only) ;;
    *) echo "Unknown mode: $MODE" >&2; exit 2 ;;
esac

cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET RCC fair scoring ($MODE) on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="

for arm in "${RCC_ARMS[@]}"; do
    attribution="$SECTION_ROOT/$arm/attribution"
    saved="$SECTION_ROOT/$arm/peak_evaluation_released_target"
    if ! grep -q '"status": "valid"' "$attribution/summary.json" 2>/dev/null \
            || ! grep -q '"status": "complete"' "$saved/summary.json" 2>/dev/null; then
        echo "$arm: not done (IG not valid or matched evaluation missing); not scored"
        continue
    fi
    for analysis in primary cancer_normal; do
        case "$analysis" in
            primary) root="$RESULTS/diagnostics/fair_scoring_baselines/rcc"; subset_args=() ;;
            # shellcheck disable=SC2206
            cancer_normal) root="$RESULTS/diagnostics/fair_scoring_baselines/rcc_cancer_normal_sensitivity"
                           subset_args=(--class-subset $RCC_SENSITIVITY_CLASSES) ;;
        esac
        for scope in "${SCOPES[@]}"; do
            output="$root/$scope/${DATASET}_seed1/$arm"
            mkdir -p "$output"
            partition_args=()
            if [ "$scope" = with_approved_partitions ]; then
                partition_args=(--partition-dir "$RESULTS/diagnostics/peak_partition_audit_rcc/$DATASET"
                                --partition-approval "$APPROVAL")
            fi
            "$PYTHON" -u scripts/evaluate_fair_scoring_baselines.py \
                --input "$INPUT" --attribution-dir "$attribution" \
                --saved-evaluation-dir "$saved" --no-legacy --reference-budget "$BUDGET" \
                --output "$output" --random-draws 100 --chunk-size 1024 \
                ${subset_args[@]+"${subset_args[@]}"} ${partition_args[@]+"${partition_args[@]}"} \
                > "$output/evaluator_stdout.log"
            echo "$arm $analysis $scope: $(grep -o '"status": "[a-z]*"' "$output/summary.json" | head -1)"
        done
    done
done

#!/bin/bash
# Count-matched scoring of the re-tuned msiPL lists (protocol 18 Section 6.8). One
# array task per MSIPL_RETUNE_SECTIONS row, both seed-1 IG arms:
#   bash slurm_jobs/submit_msipl_retune.sh score INDICES   (each submission needs Zayd's OK)
# score_msipl_retune.py rebuilds every ranking with the fair evaluator's functions,
# reproduces the saved posterior, lists, mSCF1 and rankings prefixes (else it stops),
# checks GBM/CAC m = 1 against the saved legacy metrics, then scores legacy and every
# ranking at each re-tuned list's unique-bin count. Exit 3: output exists.
# Memory: the fair-scoring evaluator peaked at 0.91 GB on GBM22_2; rankings are rebuilt
# here the same way.
#SBATCH --job-name=msipl-retune-score
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/msipl-retune-score-%A_%a.out
#SBATCH --error=logs/msipl-retune-score-%A_%a.err

set -euo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/msipl_retune_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_msipl_retune.sh}"
DATASET="$(msipl_retune_section "$TASK_ID")"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
RETUNE="$(msipl_retune_output "$DATASET")"
for arm in "${MSIPL_RETUNE_ARMS[@]}"; do
    output="$(msipl_retune_score_output "$DATASET" "$arm")"
    if [ -e "$output/summary.json" ]; then
        echo "Output already exists: $output (never overwritten)" >&2; exit 3
    fi
done
grep -q '"status": "complete"' "$RETUNE/summary.json" 2>/dev/null \
    || { echo "Re-tune not complete for $DATASET: $RETUNE" >&2; exit 1; }
LEGACY_ARGUMENTS=()
if [ "$COLLECTION" != RCC ]; then
    LEGACY_ARGUMENTS=(--legacy-metrics "$(msipl_retune_saved_dir "$DATASET")/peak_metrics.json")
fi
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET msiPL re-tune scoring on ${SLURMD_NODENAME:-unknown} (job ${SLURM_ARRAY_JOB_ID}_${TASK_ID}) ==="
for arm in "${MSIPL_RETUNE_ARMS[@]}"; do
    output="$(msipl_retune_score_output "$DATASET" "$arm")"
    mkdir -p "$output"
    "$PYTHON" -u scripts/score_msipl_retune.py --input "$INPUT" \
        --attribution-dir "$(msipl_retune_attribution "$DATASET" "$arm")" \
        --saved-evaluation-dir "$(msipl_retune_evaluation "$DATASET" "$arm")" \
        --saved-fair-dir "$(msipl_retune_saved_fair "$DATASET" "$arm")" \
        --retune-dir "$RETUNE" ${LEGACY_ARGUMENTS[@]+"${LEGACY_ARGUMENTS[@]}"} \
        --output "$output" --chunk-size 1024 > "$output/scorer_stdout.log"
    echo "$arm: $(grep -o '"status": "[a-z]*"' "$output/summary.json" | head -1)"
done

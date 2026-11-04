#!/bin/bash
# Label-free K (protocol 18 Section 6.10; D56), step 1: BIC selection of the GMM K
# for the 28 section-arms without one (LFK_BIC_TASKS in label_free_k_sections.sh).
# The unchanged select_gmm_k_bic.py with the gate (d) settings (candidates 1-6,
# seed 1, n_init 20, dBIC < 10 tie rule, production-K refit ARI >= 0.999 first) on
# the saved seed-1 production latent. No sensitivity follow-up: the scores at the
# label-free K come from the IG and fair-scoring steps. CPU only; no labels read.
#   bash slurm_jobs/submit_label_free_k.sh bic INDICES   (each submission needs Zayd's OK)
# Exit 3: output already exists (never overwritten).
#SBATCH --job-name=lfk-bic
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory and time as the gate (d)/RCC BIC jobs (tasks took 1.5-2.5 min).
#SBATCH --mem=4G
#SBATCH --time=01:00:00
#SBATCH --output=logs/lfk-bic-%A_%a.out
#SBATCH --error=logs/lfk-bic-%A_%a.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/label_free_k_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_label_free_k.sh}"
lfk_bic_task "$TASK_ID"
DATASET="$TASK_SECTION"; ARM="$TASK_ARM"
PRODUCTION="$(lfk_production_attribution "$DATASET" "$ARM")"
PRODUCTION_K="$(test_r_gmm_components "$DATASET")"
SELECTION="$(lfk_bic_selection "$DATASET" "$ARM")"
OUT="$(dirname "$SELECTION")"
case "$OUT" in
    "$LFK_BIC_NEW"/*) ;;
    *) echo "Refusing to write outside the new BIC root: $OUT" >&2; exit 2 ;;
esac
[ ! -e "$SELECTION" ] || { echo "Output already exists: $SELECTION (never overwritten)" >&2; exit 3; }
for required in "$PRODUCTION/latent_mean.npy" "$PRODUCTION/coordinates_and_gmm.npz"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
mkdir -p "$OUT"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 MKL_NUM_THREADS=2 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "Task $TASK_ID: $DATASET / $ARM, production K=$PRODUCTION_K, node $(hostname)"
# Status lines only; the outcome is read from the JSON after the sync.
"$PYTHON" -u scripts/select_gmm_k_bic.py --attribution-dir "$PRODUCTION" \
    --production-k "$PRODUCTION_K" --seed 1 --n-init 20 --output "$OUT" > /dev/null
echo "BIC selection written: $SELECTION"

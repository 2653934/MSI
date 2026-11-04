#!/bin/bash
# Label-free K (protocol 18 Section 6.10; D56), step 2: GMM at the label-free K, IG
# and the matched evaluation, from the saved seed-1 production checkpoint (no
# retraining). One array task per section-arm (label_free_k_sections.sh, 0-47):
#   bash slurm_jobs/submit_label_free_k.sh ig STEPS INDICES   (each needs Zayd's OK)
# The K is read from the BIC selection by resolve_label_free_k.py (latent hash must
# match). The IG call is the production campaign call except --gmm-components and,
# above 64 steps, --ig-steps and --align-gmm-labels-to-production <this arm's 64-step
# label-free folder>, with gate v2 (check_ig_steps_gate.py, D33) against that folder.
# Escalation (D27, D37 as extended by D56): 64 -> 128 -> 256 -> 512 -> 1024; a step
# count above 64 runs only if the previous one exists and is needs_more_ig_steps.
# Exit codes: 3 output exists (never overwritten); 4 IG completeness fails at this
# step count (no evaluation); 5 identity gate failed (model state, K or gate v2: stop
# and post); 6 a GMM component is under 44 px ("not done", no fallback).
# No --exclusive: no timing from these runs enters the report.
#SBATCH --job-name=lfk-ig
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
# Memory: GBM IG used 24G in gate (d) (GBM108_positive); RCC/CAC need far less.
#SBATCH --mem=24G
# Time: 64-step IG took 4-12 min per arm at K = 2-3; K = 6 has 2-3x the IG targets.
#SBATCH --time=03:00:00
#SBATCH --output=logs/lfk-ig-%A_%a.out
#SBATCH --error=logs/lfk-ig-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/label_free_k_sections.sh"
STEPS="${1:?Usage: run_label_free_k_ig.sh STEPS (through submit_label_free_k.sh)}"
lfk_check_steps "$STEPS"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_label_free_k.sh}"
lfk_task "$TASK_ID"
DATASET="$TASK_SECTION"; ARM="$TASK_ARM"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
PRODUCTION="$(lfk_production_attribution "$DATASET" "$ARM")"
SELECTION="$(lfk_bic_selection "$DATASET" "$ARM")"
ROOT="$(lfk_result_root "$DATASET" "$ARM" "$STEPS")"
FIRST="$(lfk_result_root "$DATASET" "$ARM" 64)"
# Never overwrite: any earlier output of this task stops it before anything runs.
if [ -e "$ROOT/attribution" ] || [ -e "$ROOT/label_free_k.json" ] || [ -e "$ROOT/gmm_gate_v2.json" ]; then
    echo "Output already exists: $ROOT (move it aside; never overwritten)" >&2; exit 3
fi
for required in "$INPUT" "$SELECTION" "$PRODUCTION/summary.json" "$PRODUCTION/latent_mean.npy"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
if [ "$STEPS" != 64 ]; then
    PREVIOUS="$(lfk_result_root "$DATASET" "$ARM" "$(lfk_previous_steps "$STEPS")")"
    grep -q '"status": "needs_more_ig_steps"' "$PREVIOUS/attribution/summary.json" 2>/dev/null \
        || { echo "Escalation refused: $PREVIOUS is not needs_more_ig_steps" >&2; exit 2; }
fi
if [ "$COLLECTION" = RCC ]; then
    BUDGET="$(test_r_rcc_budget "$DATASET")"
    grep -q '"status": "complete"' "$BUDGET" 2>/dev/null \
        || { echo "RCC released-target budget missing: $BUDGET" >&2; exit 1; }
else
    LEGACY_DIR="$(test_r_legacy_dir "$DATASET")"
    for required in "$LEGACY_DIR/peak_metrics.json" "$LEGACY_DIR/learned_peaks.csv"; do
        [ -f "$required" ] || { echo "Missing legacy input: $required" >&2; exit 1; }
    done
fi
mkdir -p "$ROOT"
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 MPLBACKEND=Agg
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
echo "=== $DATASET $ARM seed 1, label-free K, $STEPS IG steps (task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

# The label-free K, from the BIC record (never typed); above 64 steps it must equal
# the K of this arm's 64-step run.
GMM_COMPONENTS="$("$PYTHON" scripts/resolve_label_free_k.py --bic-selection "$SELECTION" \
    --production-attribution "$PRODUCTION" --output "$ROOT/label_free_k.json")" \
    || { echo "Label-free K not resolved (stop and post)" >&2; exit 5; }
if [ "$STEPS" != 64 ]; then
    "$PYTHON" - "$FIRST/label_free_k.json" "$GMM_COMPONENTS" <<'PY' || exit 5
import json, sys
first = int(json.load(open(sys.argv[1]))["label_free_k"])
if first != int(sys.argv[2]):
    sys.exit(f"label-free K {sys.argv[2]} differs from the 64-step run's K {first}")
PY
fi
CHECKPOINT="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["checkpoint"])' "$PRODUCTION/summary.json")"
[ -f "$CHECKPOINT" ] || { echo "Missing checkpoint: $CHECKPOINT" >&2; exit 1; }
echo "K = $GMM_COMPONENTS; checkpoint $CHECKPOINT"

if [ "$COLLECTION" = RCC ]; then
    K_BIN="$("$PYTHON" -c 'import json,sys; print(int(json.load(open(sys.argv[1]))["K_bin"]))' "$BUDGET")"
else
    K_BIN="$(test_r_k_bin "$DATASET")"
    "$PYTHON" - "$LEGACY_DIR/peak_metrics.json" "$K_BIN" <<'PY'
import json, sys
count = int(json.load(open(sys.argv[1]))["unique_nearest_bins"])
if count != int(sys.argv[2]):
    sys.exit(f"legacy unique_nearest_bins {count} != K_bin {sys.argv[2]}")
PY
fi
echo "K_bin = $K_BIN"

# Real CUDA warm-up; records the node and device.
"$PYTHON" - "$ROOT/node_record.json" <<'PY'
import json, os, socket, sys
import torch
if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; stopped before model or data load")
probe = torch.ones((32, 32), device="cuda:0")
torch.cuda.synchronize()
job = os.environ.get("SLURM_ARRAY_JOB_ID", "") + "_" + os.environ.get("SLURM_ARRAY_TASK_ID", "")
record = {"node": socket.gethostname(), "gpu_model": torch.cuda.get_device_name(0),
          "torch_version": torch.__version__, "slurm_job": job}
with open(sys.argv[1], "a", encoding="utf-8") as stream:
    stream.write(json.dumps(record) + "\n")
print(f"CUDA warm-up passed on {record['gpu_model']}: {float(probe.sum())}", flush=True)
PY

ALIGN_ARGUMENTS=()
[ "$STEPS" = 64 ] || ALIGN_ARGUMENTS=(--align-gmm-labels-to-production "$FIRST/attribution")
set +e
"$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" --checkpoint "$CHECKPOINT" \
    --output "$ROOT/attribution" --variant "$ARM" \
    --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
    --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
    --ig-steps "$STEPS" --ig-internal-batch-size 8 \
    --deletion-budgets 32 128 512 --random-repeats 10 \
    --top-candidates 50 --seed 1 --sampling-seed 1 \
    ${ALIGN_ARGUMENTS[@]+"${ALIGN_ARGUMENTS[@]}"} \
    > "$ROOT/attribution_stdout.log" 2> "$ROOT/attribution_stderr.log"
status=$?
set -e
if [ "$status" -ne 0 ]; then
    if grep -q "pixels; 44 required" "$ROOT/attribution_stderr.log"; then
        echo "{\"status\": \"not_done\", \"reason\": \"GMM component under 44 px at K = $GMM_COMPONENTS\"}" \
            > "$ROOT/not_done.json"
        echo "not done: a GMM component is under 44 px at K = $GMM_COMPONENTS (no fallback)" >&2; exit 6
    elif [ "$status" -eq 5 ]; then
        echo "GMM alignment to the 64-step label-free run failed (stop and post)" >&2; exit 5
    fi
    echo "IG stopped with exit $status (see attribution_stderr.log)" >&2; exit 1
fi

# Identity with production: same model state as the saved seed-1 run, and the
# label-free K and step count recorded by the IG script.
"$PYTHON" - "$ROOT/attribution/summary.json" "$PRODUCTION/summary.json" \
    "$GMM_COMPONENTS" "$STEPS" "$ROOT/identity_check.json" <<'PY' || exit 5
import json, sys
new, production = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
k, steps = int(sys.argv[3]), int(sys.argv[4])
record = {
    "model_state_equal_to_production": new["model_state_sha256"] == production["model_state_sha256"],
    "gmm_components_recorded": new["gmm"]["components"],
    "steps_recorded": new["integrated_gradients"]["steps"],
    "status": new["status"],
}
record["passed"] = bool(record["model_state_equal_to_production"]
                        and record["gmm_components_recorded"] == k
                        and record["steps_recorded"] == steps)
json.dump(record, open(sys.argv[5], "w"), indent=2)
print(json.dumps(record), flush=True)
if not record["passed"]:
    sys.exit("identity check failed (stop and post)")
PY
if [ "$STEPS" != 64 ]; then
    "$PYTHON" -u scripts/check_ig_steps_gate.py --new-attribution "$ROOT/attribution" \
        --saved-attribution "$FIRST/attribution" --steps "$STEPS" --output "$ROOT/gmm_gate_v2.json" \
        || { echo "GMM gate v2 failed (stop and post)" >&2; exit 5; }
fi
grep -q '"status": "valid"' "$ROOT/attribution/summary.json" \
    || { echo "IG completeness fails at $STEPS steps: not done at this step count; no evaluation" >&2; exit 4; }

if [ "$COLLECTION" = RCC ]; then
    EVALUATION="$ROOT/peak_evaluation_released_target"
    LEGACY_ARGUMENTS=(--no-legacy)
else
    EVALUATION="$ROOT/peak_evaluation"
    LEGACY_ARGUMENTS=(--legacy-peaks "$LEGACY_DIR/learned_peaks.csv"
                      --legacy-metrics "$LEGACY_DIR/peak_metrics.json")
fi
"$PYTHON" -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$INPUT" --attribution-dir "$ROOT/attribution" "${LEGACY_ARGUMENTS[@]}" \
    --no-component-mapping \
    --output "$EVALUATION" --matched-count "$K_BIN" \
    --peak-tolerance-ppm 10 --consolidated-candidates 50 \
    --ion-images 12 --chunk-size 1024 > "$EVALUATION.stdout.log"
echo "=== $DATASET $ARM label-free K = $GMM_COMPONENTS, $STEPS steps complete ==="

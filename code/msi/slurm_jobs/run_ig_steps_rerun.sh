#!/bin/bash
# IG completeness reruns (protocol 18 Section 6.3 amendment "30 October: IG
# completeness reruns"; supervisor chat 2026-10-30 12:58 item 1 and 13:30 ruling).
# One array task per row of IG_STEPS_TASKS (ig_steps_sections.sh):
#   bash slurm_jobs/submit_ig_steps.sh ig INDICES   (each submission needs Zayd's OK)
# IG is rerun from the saved checkpoint (no retraining) with the campaign's IG call
# unchanged except --ig-steps and --align-gmm-labels-to-production <saved 64-step
# folder>. GMM gate (13:30, answer 1): the alignment must succeed (identical hard
# assignment, posterior within 1e-4; otherwise the IG script exits 5 before writing
# anything), the permutation must be the identity, and the model state must equal
# the saved one; latent and GMM parameter differences are recorded descriptively in
# gmm_gate.json. Then the matched evaluation into the same new root: RCC at the
# released target without legacy, GBM/CAC at the production K_bin with the legacy
# list (as run_test_r_campaign.sh).
# Exit codes: 3 output already exists (never overwritten); 4 IG completeness fails
# at this step count (no evaluation); 5 GMM gate failed (stop and post).
# No --exclusive: no timing from these runs enters the report (13:30 ruling).
#SBATCH --job-name=ig-steps
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
# Memory: GBM IG used 24G in gate (d) (GBM108_positive); RCC/CAC need far less.
#SBATCH --mem=24G
# Time: 64-step IG took 4-12 min per arm (saved runtime_seconds); 256 steps is
# about 4x the IG part, plus the matched evaluation.
#SBATCH --time=03:00:00
#SBATCH --output=logs/ig-steps-%A_%a.out
#SBATCH --error=logs/ig-steps-%A_%a.err

set -eo pipefail
PROJECT_ROOT="$HOME/msi"
source "$PROJECT_ROOT/slurm_jobs/ig_steps_sections.sh"
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit through submit_ig_steps.sh}"
ig_steps_task "$TASK_ID"
DATASET="$TASK_SECTION"; SEED="$TASK_SEED"; ARM="$TASK_ARM"; STEPS="$TASK_STEPS"
COLLECTION="$(test_r_collection "$DATASET")"
INPUT="$(test_r_input_for "$DATASET")"
GMM_COMPONENTS="$(test_r_gmm_components "$DATASET")"
ROOT="$(ig_steps_result_root "$DATASET" "$SEED" "$ARM" "$STEPS" "$TASK_KIND")"
SAVED="$(ig_steps_saved_attribution "$DATASET" "$SEED" "$ARM")"
CHECKPOINT="$(ig_steps_checkpoint "$DATASET" "$SEED" "$ARM")"
# Never overwrite: any earlier output of this task stops it before anything runs.
if [ -e "$ROOT/attribution" ] || [ -e "$ROOT/gmm_gate.json" ]; then
    echo "Output already exists: $ROOT (move it aside; never overwritten)" >&2; exit 3
fi
for required in "$INPUT" "$CHECKPOINT" "$SAVED/summary.json" "$SAVED/coordinates_and_gmm.npz" \
                 "$SAVED/gmm_parameters.npz" "$SAVED/latent_mean.npy"; do
    [ -f "$required" ] || { echo "Missing input: $required" >&2; exit 1; }
done
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
echo "=== $DATASET $ARM seed $SEED, $STEPS IG steps ($TASK_KIND; task $TASK_ID) on ${SLURMD_NODENAME:-unknown}, job ${SLURM_ARRAY_JOB_ID}_${TASK_ID} ==="

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

# The checkpoint must be the one the saved 64-step run used: the complete 100-epoch,
# unmasked 3x3 model of this arm at this training seed.
"$PYTHON" - "$CHECKPOINT" "$ARM" "$SEED" "$SAVED/summary.json" <<'PY'
import json, sys
import torch
from spatial_msipl.preprocessing import checkpoint_input_spec
path, arm, seed, saved = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
if json.load(open(saved))["checkpoint"] != path:
    sys.exit("checkpoint differs from the one recorded in the saved 64-step summary")
checkpoint = torch.load(path, map_location="cpu", weights_only=False)
spec = checkpoint_input_spec(checkpoint)
configuration = checkpoint["model_configuration"]
if int(checkpoint.get("completed_epochs", 0)) != 100:
    sys.exit("not a complete 100-epoch checkpoint")
if arm == "central_only":
    if configuration.get("input_mode") != "central_only" or "neighbourhood" in configuration:
        sys.exit("checkpoint is not a central_only model")
elif configuration.get("neighbourhood", {}).get("name") != "uniform_mean":
    sys.exit("checkpoint is not a uniform_mean model")
if spec["window_size"] != 3 or spec["context_mode"] != "measured":
    sys.exit("checkpoint window or context does not match the arm")
signature = checkpoint.get("resume_signature")
if signature is not None and (signature.get("seed") != seed or "centre_mask_probability" in signature):
    sys.exit(f"checkpoint is not the seed-{seed} unmasked run")
print("Checkpoint verified" + ("" if signature is not None else " (no resume signature saved)"), flush=True)
PY

set +e
"$PYTHON" -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$INPUT" --checkpoint "$CHECKPOINT" \
    --output "$ROOT/attribution" --variant "$ARM" \
    --batch-size 64 --gmm-components "$GMM_COMPONENTS" --gmm-n-init 20 \
    --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
    --ig-steps "$STEPS" --ig-internal-batch-size 8 \
    --deletion-budgets 32 128 512 --random-repeats 10 \
    --top-candidates 50 --seed 1 --sampling-seed 1 \
    --align-gmm-labels-to-production "$SAVED" > "$ROOT/attribution_stdout.log"
status=$?
set -e
if [ "$status" -eq 5 ]; then
    echo "GMM gate failed: the refit GMM does not match the saved GMM (stop and post)" >&2; exit 5
elif [ "$status" -ne 0 ]; then
    echo "IG stopped with exit $status (see attribution_stdout.log)" >&2; exit 1
fi

# GMM gate, part 2: identity permutation, same model state and step count; the
# latent and GMM parameter differences are descriptive.
"$PYTHON" - "$ROOT/attribution" "$SAVED" "$STEPS" "$ROOT/gmm_gate.json" <<'PY'
import json, sys
from pathlib import Path
import numpy as np
new, saved, steps, output = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
new_summary = json.loads((new / "summary.json").read_text())
saved_summary = json.loads((saved / "summary.json").read_text())
alignment = new_summary.get("gmm_label_alignment", {})
new_parameters, saved_parameters = np.load(new / "gmm_parameters.npz"), np.load(saved / "gmm_parameters.npz")
new_gmm, saved_gmm = np.load(new / "coordinates_and_gmm.npz"), np.load(saved / "coordinates_and_gmm.npz")
record = {
    "identity_permutation": alignment.get("identity") is True,
    "alignment_max_posterior_diff": alignment.get("max_posterior_diff"),
    "model_state_equal": new_summary["model_state_sha256"] == saved_summary["model_state_sha256"],
    "steps_recorded": new_summary["integrated_gradients"]["steps"],
    "hard_assignment_equal": bool(np.array_equal(new_gmm["component"], saved_gmm["component"])),
    "descriptive": {
        "latent_mean_max_abs_diff": float(np.max(np.abs(
            np.load(new / "latent_mean.npy").astype(np.float64)
            - np.load(saved / "latent_mean.npy").astype(np.float64)))),
        "gmm_parameters_max_abs_diff": {
            name: float(np.max(np.abs(new_parameters[name] - saved_parameters[name])))
            for name in saved_parameters.files},
        "assigned_posterior_max_abs_diff": float(np.max(np.abs(
            new_gmm["assigned_posterior"] - saved_gmm["assigned_posterior"]))),
    },
    "saved_attribution": str(saved),
    "saved_completeness": saved_summary["integrated_gradients"]["completeness"],
    "new_completeness": new_summary["integrated_gradients"]["completeness"],
    "new_status": new_summary["status"],
}
record["passed"] = bool(record["identity_permutation"] and record["model_state_equal"]
                        and record["hard_assignment_equal"] and record["steps_recorded"] == steps)
Path(output).write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps({key: record[key] for key in ("passed", "identity_permutation",
                  "model_state_equal", "hard_assignment_equal", "new_status")}), flush=True)
sys.exit(0 if record["passed"] else 5)
PY
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
    --output "$EVALUATION" --matched-count "$K_BIN" \
    --peak-tolerance-ppm 10 --consolidated-candidates 50 \
    --ion-images 12 --chunk-size 1024 > "$EVALUATION.stdout.log"
echo "=== $DATASET $ARM seed $SEED, $STEPS steps complete ==="

#!/bin/bash
# S3PL CAC retrained-centre control, second seed (supervisor chat 2026-10-15,
# item 2; decision rule predeclared there before any seed-2 output existed).
# One array task per section-arm: tasks 0-7 real patch input, 8-15 centre-tiled
# input (_train_tile_centre), sections in the order below. Everything matches
# seed 1 (10 epochs, patch size 9, reference_spatial_max, matched peak counts)
# except the initialization seed, which is 2. The sample order uses the
# controlled stream with seed 1, as the GBM initialization screen did.
# Artifacts go under reproducibility/s3pl_cac_centre_control/seed2_init2_order1,
# never over the seed-1 checkpoints. Submit with submit_s3pl_cac_centre_control_seed2.sh.
#SBATCH --job-name=s3pl-centre-seed2
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-centre-seed2-%A_%a.out
#SBATCH --error=logs/s3pl-centre-seed2-%A_%a.err

set -euo pipefail

sections=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
counts=(315 210 221 255 245 247 133 232)
task_id="${SLURM_ARRAY_TASK_ID:?Submit this as a Slurm array task}"
if ! [[ "$task_id" =~ ^([0-9]|1[0-5])$ ]]; then
    echo "Invalid array index (0-15): $task_id" >&2
    exit 2
fi
section="${sections[$((task_id % 8))]}"
count="${counts[$((task_id % 8))]}"
initialization_seed=2
sample_order_seed=1
project_root="$HOME/msi"
root="$project_root/reproducibility/s3pl_cac_centre_control/seed2_init${initialization_seed}_order${sample_order_seed}"
base="${section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
if [ "$task_id" -lt 8 ]; then
    arm=real; mode=none; training_name="$base"
else
    arm=tile_centre; mode=tile_centre; training_name="${base}_train_tile_centre"
fi
weights="$root/checkpoints/baselines/s3pl/${training_name}.pt"
config="$root/logs/s3pl/${training_name}.json"
metrics="$root/results/baselines/s3pl/${training_name}/metrics.json"
# The released ("none") path does not refuse to overwrite, so check here for both arms.
if [[ -e "$weights" || -e "$config" || -e "$metrics" ]]; then
    echo "Seed-2 artifacts already exist; refusing to overwrite: $training_name" >&2
    exit 1
fi

set +u  # Conda activation hooks may reference optional unset variables.
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
set -u
export OMP_NUM_THREADS=4
cd "$project_root/baselines/s3pl"

SOURCE_CONFIG="$project_root/logs/s3pl/${base}.json" python - <<'PY'
import json
import os
from pathlib import Path

source = json.loads(Path(os.environ["SOURCE_CONFIG"]).read_text())
current = json.loads(Path("config.json").read_text())
matched = (
    "number_classes", "evaluate_peak_picking", "peaks_per_spectral_patch",
    "spectral_patch_size", "kernel_depth_d1", "kernel_depth_d2",
    "n_epochs", "batch_size", "learning_rate", "dropout", "random_seed",
)
different = [key for key in matched if source.get(key) != current.get(key)]
if source.get("normalization", "reference_spatial_max") != current.get(
    "normalization", "reference_spatial_max"
):
    different.append("normalization")
if different:
    raise SystemExit(f"Source S3PL training settings changed: {different}")
print("Source S3PL training settings match the seed-1 baseline", flush=True)
PY

python -m py_compile main.py train.py test.py
python -m unittest discover -s tests -p 'test_frozen_patch_context.py' -v
python - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable; control stopped before model or data load")
device = torch.device("cuda")
assert torch.ones(1, device=device).item() == 1.0
print("CUDA warm-up passed on", torch.cuda.get_device_name(0), flush=True)
PY

echo "Training $section seed 2 ($arm input): real-patch reconstruction target, matched count $count, node $(hostname)"
python -u main.py \
    --data_dir "/datasets/zsuliman/msi_data/cac/${section}.imzML" \
    --artifact_root "$root" \
    --number_peaks "$count" \
    --initialization_seed "$initialization_seed" \
    --sample_order_seed "$sample_order_seed" \
    --input-context-mode "$mode" > "$root/run_logs/${training_name}.log" 2>&1 \
    || { echo "Training failed; see $root/run_logs/${training_name}.log" >&2; exit 1; }

test -s "$weights"
test -s "$config"
test -s "$metrics"
echo "Seed-2 run complete: $section ($arm)"

#!/bin/bash
# Test N (protocol 18 Section 6.5; supervisor chat 2026-10-17 13:04): S3PL retrained
# on CAC with shuffled nonlocal neighbours (input context mode shuffle_nonlocal), at
# training and inference. One array task per section-seed:
#   tasks 0-7  seed 1, the released code path (global RNG, random_seed 1);
#   tasks 8-15 seed 2, the controlled stream (initialization_seed 2, sample_order_seed 1),
# the same seed conventions as the retrained centre-tiled control. Released CAC
# settings (p 9, z 256, d1 51, d2 1, 10 epochs, batch 16, lr 1e-2,
# reference_spatial_max) from config.json, checked against the seed-1 real config;
# matched peak counts as s3pl_cac_controls.csv. Every non-central patch position is a
# nonlocal measured pixel (map seed 1701); the centre is real; the reconstruction
# target is the (shuffled) input patch. Artifacts go to new roots under
# reproducibility/s3pl_cac_shuffle_control/ and never overwrite anything.
# Submit with submit_s3pl_cac_shuffle_control.sh.
#SBATCH --job-name=s3pl-shuffle
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-shuffle-%A_%a.out
#SBATCH --error=logs/s3pl-shuffle-%A_%a.err

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
project_root="$HOME/msi"
if [ "$task_id" -lt 8 ]; then
    seed=1; root="$project_root/reproducibility/s3pl_cac_shuffle_control/seed1_released"
    seed_arguments=()
else
    seed=2; root="$project_root/reproducibility/s3pl_cac_shuffle_control/seed2_init2_order1"
    seed_arguments=(--initialization_seed 2 --sample_order_seed 1)
fi
base="${section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
training_name="${base}_train_shuffle_nonlocal"
weights="$root/checkpoints/baselines/s3pl/${training_name}.pt"
config="$root/logs/s3pl/${training_name}.json"
metrics="$root/results/baselines/s3pl/${training_name}/metrics.json"
if [[ -e "$weights" || -e "$config" || -e "$metrics" ]]; then
    echo "Test N artifacts already exist; refusing to overwrite: $root $training_name" >&2
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
print("Source S3PL training settings match the seed-1 real baseline", flush=True)
PY

python -m py_compile main.py train.py test.py utils/data_source.py utils/nonlocal_shuffle.py
python -m unittest tests.test_nonlocal_shuffle tests.test_frozen_patch_context -v
python - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable; control stopped before model or data load")
device = torch.device("cuda")
assert torch.ones(1, device=device).item() == 1.0
print("CUDA warm-up passed on", torch.cuda.get_device_name(0), flush=True)
PY

echo "Training $section seed $seed: shuffled nonlocal neighbours (map seed 1701), real centre, shuffled-patch target, matched count $count, node $(hostname)"
python -u main.py \
    --data_dir "/datasets/zsuliman/msi_data/cac/${section}.imzML" \
    --artifact_root "$root" \
    --number_peaks "$count" \
    ${seed_arguments[@]+"${seed_arguments[@]}"} \
    --input-context-mode shuffle_nonlocal > "$root/run_logs/${training_name}.log" 2>&1 \
    || { echo "Training failed; see $root/run_logs/${training_name}.log" >&2; exit 1; }

test -s "$weights"
test -s "$config"
test -s "$metrics"
echo "Test N run complete: $section seed $seed"

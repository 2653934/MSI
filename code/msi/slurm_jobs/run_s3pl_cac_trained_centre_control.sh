#!/bin/bash
#SBATCH --job-name=s3pl-centre-train
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-centre-train-%A_%a.out
#SBATCH --error=logs/s3pl-centre-train-%A_%a.err

set -euo pipefail

sections=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
counts=(315 210 221 255 245 247 133 232)
task_id="${SLURM_ARRAY_TASK_ID:?Submit this as a Slurm array task}"
if ! [[ "$task_id" =~ ^[0-7]$ ]]; then
    echo "Invalid CAC array index: $task_id" >&2
    exit 2
fi
section="${sections[$task_id]}"
count="${counts[$task_id]}"
project_root="$HOME/msi"
training_name="${section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9_train_tile_centre"
weights="$project_root/checkpoints/baselines/s3pl/${training_name}.pt"
config="$project_root/logs/s3pl/${training_name}.json"
if [[ -e "$weights" || -e "$config" ]]; then
    echo "Control artifacts already exist; refusing to overwrite: $training_name" >&2
    exit 1
fi

set +u  # Conda activation hooks may reference optional unset variables.
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
set -u
export OMP_NUM_THREADS=4
cd "$project_root/baselines/s3pl"

SOURCE_CONFIG="$project_root/logs/s3pl/${section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9.json" \
python - <<'PY'
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
print("Source S3PL training settings match the frozen baseline", flush=True)
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

echo "Training $section: real-patch reconstruction target, centre-tiled input, matched count $count"
python -u main.py \
    --data_dir "/datasets/zsuliman/msi_data/cac/${section}.imzML" \
    --artifact_root "$project_root" \
    --number_peaks "$count" \
    --input-context-mode tile_centre

test -s "$weights"
test -s "$config"
test -s "$project_root/results/baselines/s3pl/${training_name}/metrics.json"
echo "Control complete: $section"

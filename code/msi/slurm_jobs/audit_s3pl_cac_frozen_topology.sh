#!/bin/bash
#SBATCH --job-name=s3pl-topology
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=bigbatch
#SBATCH --time=02:00:00
#SBATCH --mem=32G
#SBATCH --output=logs/s3pl-topology-%A_%a.out
#SBATCH --error=logs/s3pl-topology-%A_%a.err

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
training_name="${section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"

cd "$project_root"
set +u  # Conda's MKL hook reads optional unset variables.
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
set -u
export OMP_NUM_THREADS=4

python -m py_compile baselines/s3pl/test.py scripts/evaluate_s3pl_cac_frozen_topology.py
python -m unittest discover -s baselines/s3pl/tests -p 'test_frozen_patch_context.py' -v
python - <<'PY'
import torch
if not torch.cuda.is_available():
    raise SystemExit("CUDA unavailable; topology audit stopped before model or data load")
assert torch.ones(1, device="cuda").item() == 1.0
print("CUDA warm-up passed on", torch.cuda.get_device_name(0), flush=True)
PY

python -u scripts/evaluate_s3pl_cac_frozen_topology.py \
    --config "$project_root/logs/s3pl/${training_name}.json" \
    --number-peaks "$count" \
    --output "$project_root/results/diagnostics/s3pl_cac_frozen_topology/${section}.json"

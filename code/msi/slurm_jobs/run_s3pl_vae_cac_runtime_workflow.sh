#!/bin/bash
# Diagnostic full-workflow cost comparison on one CAC section and one node.
# Scientific outputs are isolated from all existing production artifacts.
#SBATCH --job-name=cac-runtime
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=batch
#SBATCH --time=04:00:00
#SBATCH --mem=24G
#SBATCH --exclusive
#SBATCH --output=logs/cac-runtime-%j.out
#SBATCH --error=logs/cac-runtime-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
SECTION=160TopL
COUNT=210
IMZML="/datasets/zsuliman/msi_data/cac/${SECTION}.imzML"
H5="/datasets/zsuliman/msi_data/cac_msipl/${SECTION}.h5"
LEGACY="$PROJECT_ROOT/results/baselines/msipl/cac/$SECTION"
ROOT="$PROJECT_ROOT/results/validation/s3pl_vae_cac_runtime/${SLURM_JOB_ID:?}"
S3PL_ARTIFACT="$ROOT/s3pl"
VAE_RESULT="$ROOT/vae_training"
VAE_CHECKPOINT="/datasets/zsuliman/msi_checkpoints/runtime_workflow/${SLURM_JOB_ID}/${SECTION}_uniform_mean"
ATTRIBUTION="$ROOT/vae_attribution"
EVALUATION="$ROOT/vae_peak_evaluation"

for path in "$IMZML" "$H5" "$LEGACY/learned_peaks.csv" "$LEGACY/peak_metrics.json"; do
    if [[ ! -f "$path" ]]; then
        echo "Required input is missing: $path" >&2
        exit 1
    fi
done
if [[ -e "$ROOT" || -e "$VAE_CHECKPOINT" ]]; then
    echo "Benchmark output already exists; refusing to overwrite: $ROOT" >&2
    exit 1
fi
mkdir -p "$ROOT" "$VAE_CHECKPOINT"
cd "$PROJECT_ROOT"
git rev-parse HEAD > "$ROOT/git_revision.txt" 2>/dev/null || echo unavailable > "$ROOT/git_revision.txt"
sha256sum \
    baselines/s3pl/train.py baselines/s3pl/test.py \
    scripts/train_spatial_msipl_production.py \
    scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    scripts/evaluate_spatial_msipl_attributed_peaks.py \
    slurm_jobs/run_s3pl_vae_cac_runtime_workflow.sh \
    > "$ROOT/source_sha256.txt"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4

command -v nvidia-smi >/dev/null
test -x /usr/bin/time
python -m py_compile \
    baselines/s3pl/main.py \
    scripts/train_spatial_msipl_production.py \
    scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    scripts/evaluate_spatial_msipl_attributed_peaks.py
python - "$ROOT/environment.json" <<'PY'
import json
import os
import platform
import sys
from pathlib import Path

import torch

if not torch.cuda.is_available():
    sys.exit("CUDA unavailable; benchmark stopped before model or data load")
value = torch.ones(1, device="cuda").item()
if value != 1.0:
    sys.exit("CUDA allocation check failed")
try:
    from threadpoolctl import threadpool_info
    pools = threadpool_info()
except ImportError:
    pools = None
report = {
    "purpose": "isolated native-workflow resource diagnostic, not a scientific rerun",
    "section": "160TopL",
    "matched_peak_count": 210,
    "node": platform.node(),
    "python": sys.version,
    "pytorch": torch.__version__,
    "torch_cuda_build": torch.version.cuda,
    "gpu": torch.cuda.get_device_name(0),
    "torch_cpu_threads": torch.get_num_threads(),
    "allocated_cpu_cores": os.environ.get("SLURM_CPUS_PER_TASK"),
    "OMP_NUM_THREADS": os.environ.get("OMP_NUM_THREADS"),
    "MKL_NUM_THREADS": os.environ.get("MKL_NUM_THREADS"),
    "OPENBLAS_NUM_THREADS": os.environ.get("OPENBLAS_NUM_THREADS"),
    "threadpools": pools,
    "input_note": "S3PL reads original imzML; VAE reads the adapted HDF5 from the same section.",
    "protocol_note": "S3PL 10 epochs and VAE 100 epochs are native protocols, not equal-work budgets; optional VAE ion-image rendering is excluded.",
}
Path(sys.argv[1]).write_text(json.dumps(report, indent=2, default=str) + "\n")
print(json.dumps({"gpu": report["gpu"], "node": report["node"]}), flush=True)
PY
nvidia-smi --query-gpu=name,driver_version,memory.total \
    --format=csv,noheader > "$ROOT/gpu_hardware.csv"

run_stage() {
    local stage="$1"
    shift
    local started finished status sampler
    started="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    echo "=== $stage started $started ===" >&2
    nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used \
        --format=csv,noheader,nounits -l 1 > "$ROOT/${stage}.gpu_samples.csv" 2> "$ROOT/${stage}.gpu_sampler.err" &
    sampler=$!
    set +e
    /usr/bin/time -f 'elapsed_seconds=%e\nuser_cpu_seconds=%U\nsystem_cpu_seconds=%S\nmax_rss_kib=%M' \
        -o "$ROOT/${stage}.resources.txt" \
        "$@" > "$ROOT/${stage}.out" 2> "$ROOT/${stage}.err"
    status=$?
    set -e
    kill "$sampler" 2>/dev/null || true
    wait "$sampler" 2>/dev/null || true
    finished="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    printf '%s\t%s\t%s\t%s\n' "$stage" "$started" "$finished" "$status" >> "$ROOT/stages.tsv"
    echo "=== $stage finished $finished (exit $status) ===" >&2
    if (( status != 0 )); then
        echo "Inspect $ROOT/${stage}.err and $ROOT/${stage}.out" >&2
        exit "$status"
    fi
}

printf 'stage\tstart_utc\tend_utc\texit_code\n' > "$ROOT/stages.tsv"

cd "$PROJECT_ROOT/baselines/s3pl"
run_stage s3pl_full python -u main.py \
    --data_dir "$IMZML" --artifact_root "$S3PL_ARTIFACT" \
    --number_classes 3 --number_peaks "$COUNT" --eval_picking \
    --n_epochs 10 --spectral_patch_size 9 --peaks_per_spectral_patch 256 \
    --batch_size 16 --learning_rate 0.01 --kernel_depth_d1 51 \
    --kernel_depth_d2 1 --dropout 0 --random_seed 1 \
    --normalization reference_spatial_max --input-context-mode none

cd "$PROJECT_ROOT"
run_stage vae_train python -u scripts/train_spatial_msipl_production.py \
    --input "$H5" --output "$VAE_RESULT" \
    --checkpoint-output "$VAE_CHECKPOINT" \
    --variant uniform_mean --epochs 100 --batch-size 128 \
    --hidden-dim 512 --latent-dim 5 --learning-rate 0.001 \
    --spatial-lambda 0 --seed 1 --checkpoint-interval 5

run_stage vae_attribution python -u scripts/run_spatial_msipl_gmm_integrated_gradients.py \
    --input "$H5" --checkpoint "$VAE_CHECKPOINT/checkpoint.pt" \
    --output "$ATTRIBUTION" --variant uniform_mean \
    --batch-size 64 --gmm-components 3 --gmm-n-init 20 \
    --attribution-per-cluster 12 --faithfulness-per-cluster 32 \
    --ig-steps 64 --ig-internal-batch-size 8 \
    --deletion-budgets 32 128 512 --random-repeats 10 \
    --top-candidates 50 --seed 1 --sampling-seed 1

run_stage vae_peak_evaluation python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$H5" --attribution-dir "$ATTRIBUTION" \
    --legacy-peaks "$LEGACY/learned_peaks.csv" \
    --legacy-metrics "$LEGACY/peak_metrics.json" \
    --output "$EVALUATION" --matched-count "$COUNT" \
    --peak-tolerance-ppm 10 --consolidated-candidates 50 \
    --ion-images 0 --chunk-size 1024

echo "Full runtime diagnostic complete: $ROOT"

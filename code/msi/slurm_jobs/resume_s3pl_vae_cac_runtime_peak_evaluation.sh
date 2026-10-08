#!/bin/bash
# Resume only the optional final stage of an otherwise complete runtime workflow.
# Usage: sbatch slurm_jobs/resume_s3pl_vae_cac_runtime_peak_evaluation.sh ORIGINAL_JOB_ID
#SBATCH --job-name=cac-runtime-eval
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --partition=batch
#SBATCH --time=00:30:00
#SBATCH --mem=24G
#SBATCH --exclusive
#SBATCH --output=logs/cac-runtime-eval-%j.out
#SBATCH --error=logs/cac-runtime-eval-%j.err

set -eo pipefail

if [[ "$#" -ne 1 || ! "$1" =~ ^[0-9]+$ ]]; then
    echo "Usage: sbatch $0 ORIGINAL_JOB_ID" >&2
    exit 2
fi

project_root="$HOME/msi"
original_job_id="$1"
root="$project_root/results/validation/s3pl_vae_cac_runtime/$original_job_id"
input="/datasets/zsuliman/msi_data/cac_msipl/160TopL.h5"
legacy="$project_root/results/baselines/msipl/cac/160TopL"
attribution="$root/vae_attribution"
evaluation="$root/vae_peak_evaluation"

for path in "$root/stages.tsv" "$attribution/summary.json" \
    "$legacy/learned_peaks.csv" "$legacy/peak_metrics.json"; do
    if [[ ! -f "$path" ]]; then
        echo "Required completed input is missing: $path" >&2
        exit 1
    fi
done
if ! grep -q $'^vae_attribution\t.*\t0$' "$root/stages.tsv"; then
    echo "The attribution stage is not recorded as complete; refusing final-stage-only resume." >&2
    exit 1
fi

cd "$project_root"
source "$HOME/miniconda3/etc/profile.d/conda.sh"
conda activate s3pl_env
export PYTHONPATH="$project_root/src:$project_root/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export OPENBLAS_NUM_THREADS=4

started="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
nvidia-smi --query-gpu=timestamp,utilization.gpu,memory.used \
    --format=csv,noheader,nounits -l 1 \
    > "$root/vae_peak_evaluation.gpu_samples.csv" \
    2> "$root/vae_peak_evaluation.gpu_sampler.err" &
sampler=$!
set +e
/usr/bin/time -f 'elapsed_seconds=%e\nuser_cpu_seconds=%U\nsystem_cpu_seconds=%S\nmax_rss_kib=%M' \
    -o "$root/vae_peak_evaluation.resources.txt" \
    python -u scripts/evaluate_spatial_msipl_attributed_peaks.py \
    --input "$input" --attribution-dir "$attribution" \
    --legacy-peaks "$legacy/learned_peaks.csv" \
    --legacy-metrics "$legacy/peak_metrics.json" \
    --output "$evaluation" --matched-count 210 \
    --peak-tolerance-ppm 10 --consolidated-candidates 50 \
    --ion-images 0 --chunk-size 1024 \
    > "$root/vae_peak_evaluation.out" \
    2> "$root/vae_peak_evaluation.err"
status=$?
set -e
kill "$sampler" 2>/dev/null || true
wait "$sampler" 2>/dev/null || true
finished="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
printf '%s\t%s\t%s\t%s\n' vae_peak_evaluation "$started" "$finished" "$status" \
    >> "$root/stages.tsv"
if (( status != 0 )); then
    echo "Peak evaluation failed again; inspect $root/vae_peak_evaluation.err" >&2
    exit "$status"
fi
echo "Completed the final runtime-workflow stage for original job $original_job_id."

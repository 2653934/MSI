#!/bin/bash
# Login-node submitter for item E (uniform 7x7 / 9x9): file checks, mkdir and sbatch only.
#   bash slurm_jobs/submit_window_e79_campaign.sh                 pilot only: task 8 (40TopL p7)
#   bash slurm_jobs/submit_window_e79_campaign.sh --indices LIST  [--after JOBID] [--concurrency N]
# The pilot is submitted alone because bigbatch allows 48 submitted jobs per user.
set -euo pipefail
cd "$HOME/msi"
concurrency=8
indices=""
dependency=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        --after) dependency=(--dependency="afterok:${2:?}"); shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
runner=slurm_jobs/run_window_e79_campaign.sh
bash -n "$runner"
for section in 40TopL 280TopL GBM108_positive GBM22_2; do
    grep -q '"status": "valid"' "results/diagnostics/spatial_msipl_data_contract_windows/$section/summary.json" \
        || { echo "7x7/9x9 audit not valid for $section" >&2; exit 1; }
done
exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
[[ -n "$exclude" ]] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
root="results/experiments/spatial_window_e79"
checkpoints="/datasets/zsuliman/msi_checkpoints/spatial_msipl/window_e79"
mkdir -p "$root/provenance" "$checkpoints" logs
source slurm_jobs/fair_scoring_sections.sh
for section in "${FAIR_SECTIONS[@]}"; do
    mkdir -p "$root/${section}_seed1" "$checkpoints/${section}_seed1"
done
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=item E: uniform 7x7 and 9x9 windows (supervisor chat 2026-10-15 13:00, 15:35)"
        echo "arms=uniform_p7 (tasks 0-15), uniform_p9 (tasks 16-31); trained as uniform_p5"
        echo "training=uniform_mean, 100 epochs, seed 1, batch 128, lr 1e-3, cosine; cached loader on GBM, streaming on CAC"
        echo "evaluation=GMM K 2 GBM / 3 CAC; IG 12 px/component; matched count = production K_bin"
        echo "excluded_nodes=$exclude"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$root/provenance/manifest.txt"
fi
if [[ -z "$indices" ]]; then
    if compgen -G "$checkpoints/*_seed1/*/checkpoint*.pt" > /dev/null; then
        echo "E checkpoints already exist; use --indices for the missing tasks only." >&2
        exit 1
    fi
    indices=8
fi
job="$(sbatch --parsable --exclude="$exclude" ${dependency[@]+"${dependency[@]}"} \
    --array="${indices}%$concurrency" "$runner")"
echo "${job%%;*} indices=$indices ${dependency[*]:-}" | tee -a "$root/provenance/slurm_job_ids.txt"

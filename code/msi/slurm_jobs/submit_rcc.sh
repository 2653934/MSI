#!/bin/bash
# Login-node submitter for the RCC run (protocol 18 Section 6.1, item D step 2):
# file checks, mkdir and sbatch only. Each stage needs Zayd's OK.
#   bash slurm_jobs/submit_rcc.sh prep                      8 CPU tasks: budget + partition audit
#   bash slurm_jobs/submit_rcc.sh pilot  [--after JOBID]    4 GPU tasks: UH0710_33, UH9610_15, both arms
#   bash slurm_jobs/submit_rcc.sh rest   [--after JOBID]    the other 12 GPU tasks
#   bash slurm_jobs/submit_rcc.sh fair p1|bin-only [--after JOBID]   8 CPU tasks
# Options: --concurrency N (default 4), --indices LIST (resubmit given tasks only).
# CPU stages take the partition from SBATCH_PARTITION (e.g. bigbatch while batch is down).
set -euo pipefail
cd "$HOME/msi"
stage="${1:?Usage: $0 prep|pilot|rest|fair MODE [options]}"; shift
mode=""
if [ "$stage" = fair ]; then mode="${1:?fair needs p1|bin-only}"; shift; fi
concurrency=4
indices=""
sbatch_options=()
while [ "$#" -gt 0 ]; do
    case "$1" in
        --concurrency) concurrency="${2:?}"; shift 2 ;;
        --indices) indices="${2:?}"; shift 2 ;;
        --after) sbatch_options+=(--dependency="afterok:${2:?}"); shift 2 ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
source slurm_jobs/rcc_sections.sh
root="results/experiments/rcc_spatial_msipl"
checkpoints="/datasets/zsuliman/msi_checkpoints/spatial_msipl/rcc"
mkdir -p "$root/provenance" logs
for section in "${RCC_SECTIONS[@]}"; do
    [ -f "$(rcc_input_for "$section")" ] || { echo "Missing input for $section" >&2; exit 1; }
    mkdir -p "$root/${section}_seed1"
done
grep -q '"decision": "go"' results/validation/rcc_feasibility/go_no_go.json \
    || { echo "RCC feasibility is not go" >&2; exit 1; }
if [[ ! -f "$root/provenance/manifest.txt" ]]; then
    {
        echo "purpose=RCC run (protocol 18 Section 6.1 item D step 2; supervisor chat 2026-10-16 17:36)"
        echo "sections=${RCC_SECTIONS[*]}"
        echo "arms=central_only (tasks 0-7), uniform_mean (tasks 8-15); trained as the CAC production arms"
        echo "evaluation=GMM K 3; IG 12 px/component; matched count K_bin = |R@0.4| over all three classes; no legacy"
        echo "created_utc=$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
    } > "$root/provenance/manifest.txt"
fi

case "$stage" in
    prep)
        runner=slurm_jobs/run_rcc_preparation.sh
        mkdir -p results/diagnostics/peak_partition_audit_rcc
        indices="${indices:-0-7}" ;;
    pilot|rest)
        runner=slurm_jobs/run_rcc_campaign.sh
        for section in "${RCC_SECTIONS[@]}"; do
            grep -q '"status": "complete"' "$root/${section}_seed1/reference_budget.json" 2>/dev/null \
                || { echo "Reference budget missing for $section; run prep first" >&2; exit 1; }
            for arm in "${RCC_ARMS[@]}"; do mkdir -p "$root/${section}_seed1/$arm" "$checkpoints/${section}_seed1/$arm"; done
        done
        if [ "$stage" = pilot ]; then
            if compgen -G "$checkpoints/*_seed1/*/checkpoint*.pt" > /dev/null && [ -z "$indices" ]; then
                echo "RCC checkpoints already exist; use --indices for missing tasks only." >&2; exit 1
            fi
            indices="${indices:-$RCC_PILOT_TRAINING_INDICES}"
        else
            indices="${indices:-0,1,4,5,6,7,8,9,12,13,14,15}"
        fi
        exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
        [[ -n "$exclude" ]] || { echo "CUDA quarantine list is empty; inspect first." >&2; exit 1; }
        sbatch_options+=(--exclude="$exclude") ;;
    fair)
        runner=slurm_jobs/run_rcc_fair_scoring.sh
        if [ "$mode" = p1 ]; then
            grep -q '"status": "approved"' results/diagnostics/peak_partition_audit_rcc/partition_approval.json \
                || { echo "No approved RCC partition file" >&2; exit 1; }
        fi
        for scope in bin_level_only with_approved_partitions; do
            for analysis in rcc rcc_cancer_normal_sensitivity; do
                mkdir -p "results/diagnostics/fair_scoring_baselines/$analysis/$scope"
            done
        done
        indices="${indices:-0-7}" ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
bash -n "$runner"
job="$(sbatch --parsable ${sbatch_options[@]+"${sbatch_options[@]}"} \
    --array="${indices}%$concurrency" "$runner" ${mode:+"$mode"})"
echo "${job%%;*} stage=$stage ${mode:+mode=$mode }indices=$indices ${sbatch_options[*]:-}" \
    | tee -a "$root/provenance/slurm_job_ids.txt"

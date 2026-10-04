#!/bin/bash
set -euo pipefail

if [ "$#" -ne 0 ]; then
    echo "Usage: bash $0" >&2
    exit 2
fi
PROJECT_ROOT="$HOME/msi"
cd "$PROJECT_ROOT"
mkdir -p logs
if squeue -h -u "$USER" -n attention-swap-all | grep -q .; then
    echo "An attention-swap-all array is already queued or running; refusing a duplicate" >&2
    exit 1
fi

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
missing=()
canary_needed=false
for index in "${!DATASETS[@]}"; do
    dataset="${DATASETS[index]}"
    case "$dataset" in
        *TopL) input="/datasets/zsuliman/msi_data/cac_msipl/${dataset}.h5" ;;
        *) input="/datasets/zsuliman/msi_data/gbm_massnet/${dataset}.h5" ;;
    esac
    if [ ! -f "$input" ]; then
        echo "Missing prepared HDF5 input: $input" >&2
        exit 1
    fi
    result="$PROJECT_ROOT/results/diagnostics/spatial_attention_input_swap/$dataset/summary.json"
    if grep -q '"status": "valid"' "$result" 2>/dev/null; then
        printf '%-18s %s\n' "$dataset" COMPLETE
        continue
    fi
    if [ "$dataset" = 160TopL ]; then
        canary_needed=true
        continue
    fi
    missing+=("$index")
    mkdir -p \
        "$PROJECT_ROOT/results/experiments/spatial_attention_context/${dataset}_seed1/real_attention" \
        "/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${dataset}_seed1/real_attention"
done
if [ "${#missing[@]}" -eq 0 ] && [ "$canary_needed" = false ]; then
    echo "All 16 fixed-model input-swap audits are valid; nothing to submit."
    exit 0
fi
dependency_args=()
if [ "$canary_needed" = true ]; then
    canary=$(sbatch slurm_jobs/audit_spatial_attention_input_swap.sh 160TopL)
    canary_job="${canary##* }"
    dependency_args=("--dependency=afterok:${canary_job}")
    echo "160TopL preflight canary: $canary"
    echo "The full campaign will start only if this canary succeeds."
fi
if [ "${#missing[@]}" -gt 0 ]; then
    indices=$(IFS=,; echo "${missing[*]}")
    submission=$(sbatch "${dependency_args[@]}" --array="${indices}%3" slurm_jobs/run_spatial_attention_swap_campaign_array.sh)
    echo "$submission"
    echo "Submitted ${#missing[@]} incomplete sections, at most 3 simultaneously."
    echo "Array indices: $indices"
fi
echo 'Monitor with: squeue -u "$USER" -o "%.18i %.24j %.2t %.10M %.24R"'
echo 'Audit with: bash slurm_jobs/check_spatial_attention_swap_campaign.sh'

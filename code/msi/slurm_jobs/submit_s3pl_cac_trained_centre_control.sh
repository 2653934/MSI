#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
if [[ -e "checkpoints/baselines/s3pl/160TopL_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9_train_tile_centre.pt" ]]; then
    echo "160TopL pilot checkpoint already exists; inspect it before submitting a new campaign." >&2
    exit 1
fi

exclude="$(sed -e 's/\r$//' -e 's/#.*$//' -e '/^[[:space:]]*$/d' slurm_jobs/gpu_cuda_quarantine.txt | sort -u | paste -sd, -)"
if [[ -z "$exclude" ]]; then
    echo "CUDA quarantine list is empty; inspect before submission." >&2
    exit 1
fi

pilot_submission="$(sbatch --parsable --exclude="$exclude" --array=1 slurm_jobs/run_s3pl_cac_trained_centre_control.sh)"
pilot_id="${pilot_submission%%;*}"
echo "160TopL pilot: $pilot_id"

# Other sections start only if the pilot completes, including its result-file checks.
rest_submission="$(sbatch --parsable --exclude="$exclude" --dependency="afterok:${pilot_id}" --array=0,2-7%6 slurm_jobs/run_s3pl_cac_trained_centre_control.sh)"
rest_id="${rest_submission%%;*}"
echo "Remaining seven sections (after pilot success): $rest_id"
echo "Monitor: squeue -j $pilot_id,$rest_id -o '%.18i %.24j %.2t %.10M %.24R'"

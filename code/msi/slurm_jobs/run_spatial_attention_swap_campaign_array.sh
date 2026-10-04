#!/bin/bash
#SBATCH --job-name=attention-swap-all
#SBATCH --partition=bigbatch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=48G
#SBATCH --time=16:00:00
#SBATCH --exclusive
#SBATCH --exclude=mscluster44,mscluster45,mscluster48,mscluster50,mscluster51,mscluster57,mscluster59,mscluster62,mscluster65,mscluster74,mscluster75,mscluster76,mscluster83
#SBATCH --output=logs/attention-swap-all-%A_%a.out
#SBATCH --error=logs/attention-swap-all-%A_%a.err

set -euo pipefail

DATASETS=(40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
          GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
TASK_ID="${SLURM_ARRAY_TASK_ID:?Submit as a Slurm array through submit_spatial_attention_swap_campaign.sh}"
if (( TASK_ID < 0 || TASK_ID >= ${#DATASETS[@]} )); then
    echo "Invalid array index: $TASK_ID" >&2
    exit 2
fi
DATASET="${DATASETS[TASK_ID]}"
PROJECT_ROOT="$HOME/msi"
CHECKPOINT="/datasets/zsuliman/msi_checkpoints/spatial_msipl/attention_context/${DATASET}_seed1/real_attention/checkpoint.pt"
TRAINING_SUMMARY="$PROJECT_ROOT/results/experiments/spatial_attention_context/${DATASET}_seed1/real_attention/summary.json"
echo "=== $DATASET: frozen attention input-swap campaign on ${SLURMD_NODENAME:-unknown} ==="

if [ ! -f "$CHECKPOINT" ] || ! grep -q '"status": "complete"' "$TRAINING_SUMMARY" 2>/dev/null; then
    echo "Training missing or incomplete; running the original 100-epoch real-attention protocol"
    bash "$PROJECT_ROOT/slurm_jobs/run_spatial_attention_context_training.sh" "$DATASET" real_attention
else
    echo "Reusing complete real-attention checkpoint"
fi

bash "$PROJECT_ROOT/slurm_jobs/audit_spatial_attention_input_swap.sh" "$DATASET"

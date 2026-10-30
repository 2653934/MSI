#!/bin/bash
# IG completeness reruns (protocol 18 Section 6.3 amendment "30 October: IG
# completeness reruns"; supervisor chat 2026-10-30 12:58 item 1 and 13:30 ruling):
# fixed task table and paths (sourced, not run). Do not reorder after submission.
# Each task is "SECTION SEED ARM STEPS KIND":
#   0-3   the four arms that failed completeness at 64 steps, at 128 steps
#   4-7   step-count controls (valid at 64), rerun at 64 steps
#   8-11  the same controls at 128 steps
#   12-15 the failed arms at 256 steps; submitted only for arms that fail at 128
# Every task reruns IG from the saved checkpoint (no retraining), GMM seed 1 and
# sampling seed 1, into a new root; the saved 64-step folders are only read.
source "$HOME/msi/slurm_jobs/test_r_sections.sh"

IG_STEPS_TASKS=(
    "RCC_UH0505_12 1 uniform_mean 128 rerun"
    "RCC_UH0505_12 2 central_only 128 rerun"
    "RCC_UH9912_01 3 uniform_mean 128 rerun"
    "GBM39_2 3 uniform_mean 128 rerun"
    "RCC_UH0505_12 1 central_only 64 control"
    "RCC_UH9912_01 1 uniform_mean 64 control"
    "GBM39_2 1 uniform_mean 64 control"
    "40TopL 1 uniform_mean 64 control"
    "RCC_UH0505_12 1 central_only 128 control"
    "RCC_UH9912_01 1 uniform_mean 128 control"
    "GBM39_2 1 uniform_mean 128 control"
    "40TopL 1 uniform_mean 128 control"
    "RCC_UH0505_12 1 uniform_mean 256 rerun"
    "RCC_UH0505_12 2 central_only 256 rerun"
    "RCC_UH9912_01 3 uniform_mean 256 rerun"
    "GBM39_2 3 uniform_mean 256 rerun"
)
IG_STEPS_RESULTS="$HOME/msi/results/experiments"
IG_STEPS_FAIR="$HOME/msi/results/diagnostics/fair_scoring_baselines/ig_steps_20261030"
IG_STEPS_CHECKPOINTS=/datasets/zsuliman/msi_checkpoints/spatial_msipl

# Sets TASK_SECTION TASK_SEED TASK_ARM TASK_STEPS TASK_KIND for one index.
ig_steps_task() {
    local index="$1"
    if ! [[ "$index" =~ ^[0-9]+$ ]] || (( index >= ${#IG_STEPS_TASKS[@]} )); then
        echo "Invalid IG-steps task index: $index" >&2; return 1
    fi
    read -r TASK_SECTION TASK_SEED TASK_ARM TASK_STEPS TASK_KIND <<<"${IG_STEPS_TASKS[index]}"
}

# New output root of one task (never inside a saved seed folder).
ig_steps_result_root() {   # section seed arm steps kind
    local folder
    case "$5" in
        rerun) folder=ig_steps_rerun_20261030 ;;
        control) folder=ig_steps_control_20261030 ;;
        *) echo "Unknown task kind: $5" >&2; return 1 ;;
    esac
    echo "$IG_STEPS_RESULTS/$folder/$1_seed$2/$3/steps$4"
}

# The saved 64-step attribution folder of the arm (read only).
ig_steps_saved_attribution() {   # section seed arm
    local collection
    collection="$(test_r_collection "$1")" || return 1
    if [ "$2" != 1 ]; then
        echo "$IG_STEPS_RESULTS/test_r_training_seeds/$1_seed$2/$3/attribution"
    elif [ "$collection" = RCC ]; then
        echo "$IG_STEPS_RESULTS/rcc_spatial_msipl/$1_seed1/$3/attribution"
    elif [ "$collection" = GBM ]; then
        echo "$IG_STEPS_RESULTS/spatial_msipl_gmm_integrated_gradients/$1_seed1/$3"
    else
        echo "$IG_STEPS_RESULTS/spatial_msipl_cac_gmm_integrated_gradients/$1_seed1/$3"
    fi
}

# The saved checkpoint the 64-step run used (read only).
ig_steps_checkpoint() {   # section seed arm
    local collection
    collection="$(test_r_collection "$1")" || return 1
    if [ "$2" != 1 ]; then
        echo "$IG_STEPS_CHECKPOINTS/test_r/$1_seed$2/$3/checkpoint.pt"
    elif [ "$collection" = RCC ]; then
        echo "$IG_STEPS_CHECKPOINTS/rcc/$1_seed1/$3/checkpoint.pt"
    elif [ "$collection" = GBM ]; then
        echo "$IG_STEPS_CHECKPOINTS/production/$1_seed1/$3/checkpoint.pt"
    else
        echo "$IG_STEPS_CHECKPOINTS/cac/production/$1_seed1/$3/checkpoint.pt"
    fi
}

# Fair-scoring output of one task and scope.
ig_steps_fair_output() {   # scope section seed arm steps
    echo "$IG_STEPS_FAIR/$1/$2_seed$3/$4/steps$5"
}

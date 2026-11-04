#!/bin/bash
# Label-free K (protocol 18 Section 6.10; decision log D56): fixed task table and
# paths (sourced, not run). Do not reorder after submission.
# Task index i (0-47): section TEST_R_SECTIONS[i / 2], arm TEST_R_ARMS[i % 2]
# (the Test R order: RCC, CAC, GBM). Seed 1 only; production checkpoints, latents and
# BIC selections are only read. BIC index j (0-27): LFK_BIC_TASKS[j], the section-arms
# without an earlier BIC selection.
source "$HOME/msi/slurm_jobs/test_r_sections.sh"

LFK_RESULTS="$HOME/msi/results"
LFK_EXPERIMENTS="$LFK_RESULTS/experiments/label_free_k_20261104"
LFK_FAIR="$LFK_RESULTS/diagnostics/fair_scoring_baselines/label_free_k_20261104/bin_level_only"
LFK_BIC_NEW="$LFK_RESULTS/diagnostics/gate_d_bic_label_free_k_20261104"
# IG step counts: 64, then D27 (128, 256), then D37 as extended by D56 (512, 1024 cap).
LFK_STEPS=(64 128 256 512 1024)

# The 28 section-arms without a BIC selection (GBM and CAC except the two
# development sections that gate (d) already ran).
LFK_BIC_TASKS=()
for _section in 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL \
                GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2; do
    for _arm in "${TEST_R_ARMS[@]}"; do LFK_BIC_TASKS+=("$_section $_arm"); done
done
unset _section _arm

# Sets TASK_SECTION TASK_ARM for one IG/fair-scoring index.
lfk_task() {
    local index="$1"
    if ! [[ "$index" =~ ^[0-9]+$ ]] || (( index >= 2 * ${#TEST_R_SECTIONS[@]} )); then
        echo "Invalid label-free-K task index: $index" >&2; return 1
    fi
    TASK_SECTION="${TEST_R_SECTIONS[index / 2]}"
    TASK_ARM="${TEST_R_ARMS[index % 2]}"
}

# Sets TASK_SECTION TASK_ARM for one BIC index.
lfk_bic_task() {
    local index="$1"
    if ! [[ "$index" =~ ^[0-9]+$ ]] || (( index >= ${#LFK_BIC_TASKS[@]} )); then
        echo "Invalid label-free-K BIC index: $index" >&2; return 1
    fi
    read -r TASK_SECTION TASK_ARM <<<"${LFK_BIC_TASKS[index]}"
}

lfk_check_steps() {
    case "$1" in
        64|128|256|512|1024) return 0 ;;
        *) echo "IG steps must be one of ${LFK_STEPS[*]}: $1" >&2; return 1 ;;
    esac
}

# The step count before STEPS in the escalation (none for 64).
lfk_previous_steps() {
    case "$1" in
        128) echo 64 ;; 256) echo 128 ;; 512) echo 256 ;; 1024) echo 512 ;;
        *) return 1 ;;
    esac
}

# The seed-1 production attribution folder (read only): its latent is the one BIC
# used and its summary records the checkpoint (read from there, never from a path
# pattern: CAC central_only checkpoints live under cac/reconstruction/).
# RCC_UH0505_12 uniform_mean is the 128-step rerun (P18 Section 6.3 amendment), the
# folder its BIC selection used.
lfk_production_attribution() {   # section arm
    local collection
    collection="$(test_r_collection "$1")" || return 1
    if [ "$1" = RCC_UH0505_12 ] && [ "$2" = uniform_mean ]; then
        echo "$LFK_RESULTS/experiments/ig_steps_rerun_20261030/RCC_UH0505_12_seed1/uniform_mean/steps128/attribution"
    elif [ "$collection" = RCC ]; then
        echo "$LFK_RESULTS/experiments/rcc_spatial_msipl/$1_seed1/$2/attribution"
    elif [ "$collection" = GBM ]; then
        echo "$LFK_RESULTS/experiments/spatial_msipl_gmm_integrated_gradients/$1_seed1/$2"
    else
        echo "$LFK_RESULTS/experiments/spatial_msipl_cac_gmm_integrated_gradients/$1_seed1/$2"
    fi
}

# The BIC selection that fixes the label-free K: the earlier selection where one
# exists (gate (d), RCC, RCC_UH0505_12 uniform_mean rerun), else the new root.
lfk_bic_selection() {   # section arm
    local collection
    collection="$(test_r_collection "$1")" || return 1
    if [ "$1" = RCC_UH0505_12 ] && [ "$2" = uniform_mean ]; then
        echo "$LFK_RESULTS/diagnostics/gate_d_bic_rcc_ig_steps_20261030/RCC_UH0505_12_seed1/uniform_mean/bic_selection.json"
    elif [ "$collection" = RCC ]; then
        echo "$LFK_RESULTS/diagnostics/gate_d_bic_rcc/$1_seed1/$2/bic_selection.json"
    elif [ "$1" = GBM108_positive ] || [ "$1" = 40TopL ]; then
        echo "$LFK_RESULTS/diagnostics/gate_d_bic/$1_seed1/$2/bic_selection.json"
    else
        echo "$LFK_BIC_NEW/$1_seed1/$2/bic_selection.json"
    fi
}

lfk_result_root() { echo "$LFK_EXPERIMENTS/$1_seed1/$2/steps$3"; }   # section arm steps
lfk_fair_output() { echo "$LFK_FAIR/$1_seed1/$2/steps$3"; }          # section arm steps

#!/bin/bash
# Test R (protocol 18 Section 6.3; supervisor chat 2026-10-17 09:45): shared,
# ordered section list and paths for the training-seed replication (sourced, not
# run). Order: RCC first, then CAC, then GBM (the 09:45 "RCC and CAC first").
# Training array index i (0-47): section TEST_R_SECTIONS[i / 2], arm TEST_R_ARMS[i % 2].
# Fair-scoring array index i (0-23): section TEST_R_SECTIONS[i], both arms.
# Seed 1 is never written here: it stays in its production roots. Do not reorder
# after submission.
TEST_R_SECTIONS=(RCC_MH0204_33 RCC_UH0505_12 RCC_UH0710_33 RCC_UH9610_15
                 RCC_UH9812_03 RCC_UH9905_18 RCC_UH9911_05 RCC_UH9912_01
                 40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
                 GBM108_negative GBM108_positive GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2)
TEST_R_ARMS=(central_only uniform_mean)
TEST_R_SEEDS=(2 3)
TEST_R_RESULTS="$HOME/msi/results/experiments/test_r_training_seeds"
# Overridable only so the submitter test never writes under /datasets.
TEST_R_CHECKPOINTS="${TEST_R_CHECKPOINTS:-/datasets/zsuliman/msi_checkpoints/spatial_msipl/test_r}"
TEST_R_FAIR="$HOME/msi/results/diagnostics/fair_scoring_baselines/test_r"

test_r_check_seed() {
    case "$1" in
        2|3) return 0 ;;
        *) echo "Test R trains seeds 2 and 3 only (seed 1 stays in its production roots): $1" >&2
           return 1 ;;
    esac
}

test_r_collection() {
    case "$1" in
        RCC_*) echo RCC ;;
        *TopL) echo CAC ;;
        GBM*) echo GBM ;;
        *) return 1 ;;
    esac
}

test_r_input_for() {
    case "$1" in
        RCC_*) echo "/datasets/zsuliman/msi_data/rcc_cardinal/$1.h5" ;;
        *TopL) echo "/datasets/zsuliman/msi_data/cac_msipl/$1.h5" ;;
        GBM*) echo "/datasets/zsuliman/msi_data/gbm_massnet/$1.h5" ;;
        *) return 1 ;;
    esac
}

# Production GMM K (number of label classes; class-informed, disclosed).
test_r_gmm_components() {
    case "$1" in
        GBM*) echo 2 ;;
        *) echo 3 ;;
    esac
}

# Legacy msiPL folder used by the GBM/CAC matched and fair-scoring evaluation.
test_r_legacy_dir() {
    case "$1" in
        GBM*) echo "$HOME/msi/results/baselines/msipl/massnet_paper_aligned/$1" ;;
        *TopL) echo "$HOME/msi/results/baselines/msipl/cac/$1" ;;
        *) return 1 ;;
    esac
}

# The seed-1 RCC released-target budget (K_bin does not depend on the seed).
test_r_rcc_budget() {
    echo "$HOME/msi/results/experiments/rcc_spatial_msipl/$1_seed1/released_target_budget.json"
}

# Production K_bin for GBM/CAC (protocol 18 Section 1; as run_centremask_campaign.sh).
test_r_k_bin() {
    case "$1" in
        GBM108_positive) echo 584 ;; GBM108_negative) echo 940 ;; GBM12_1) echo 691 ;;
        GBM12_2) echo 986 ;; GBM22_1) echo 834 ;; GBM22_2) echo 1028 ;;
        GBM39_1) echo 695 ;; GBM39_2) echo 911 ;;
        40TopL) echo 315 ;; 160TopL) echo 210 ;; 200TopL) echo 221 ;; 240TopL) echo 255 ;;
        280TopL) echo 245 ;; 360TopL) echo 247 ;; 400TopL) echo 133 ;; 520TopL) echo 232 ;;
        *) return 1 ;;
    esac
}

test_r_result_root() { echo "$TEST_R_RESULTS/$1_seed$2/$3"; }      # section seed arm
test_r_checkpoint_dir() { echo "$TEST_R_CHECKPOINTS/$1_seed$2/$3"; }

# Training phases (09:45 "RCC and CAC first, then GBM"; Codex review 10:11): a single
# array does not order its tasks, so the phases are separate submissions.
TEST_R_PHASE_FIRST="0-31"   # RCC (0-15) and CAC (16-31)
TEST_R_PHASE_GBM="32-47"    # GBM, submitted only after the first phase

# Expand "a-b,c" into one index per line.
test_r_expand_indices() {
    local part
    for part in ${1//,/ }; do
        if [[ "$part" =~ ^([0-9]+)-([0-9]+)$ ]]; then
            seq "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
        elif [[ "$part" =~ ^[0-9]+$ ]]; then
            echo "$part"
        else
            echo "Bad index list: $1" >&2; return 1
        fi
    done
}

# Every index of LIST must lie inside the phase's range.
test_r_indices_in_phase() {   # phase list
    local range low high index
    case "$1" in
        first) range="$TEST_R_PHASE_FIRST" ;;
        gbm) range="$TEST_R_PHASE_GBM" ;;
        *) echo "Unknown phase: $1" >&2; return 1 ;;
    esac
    low="${range%-*}"; high="${range#*-}"
    local expanded
    expanded="$(test_r_expand_indices "$2")" || return 1
    [ -n "$expanded" ] || { echo "Empty index list" >&2; return 1; }
    for index in $expanded; do
        if (( index < low || index > high )); then
            echo "Index $index is outside the $1 phase ($range)" >&2; return 1
        fi
    done
}

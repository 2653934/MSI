#!/bin/bash
# msiPL Beta re-tune (protocol 18 Section 6.8; supervisor chat 2026-10-30 12:58 item 2
# and 17:33 ruling): ordered section list and paths (sourced, not run). Array index i
# refers to MSIPL_RETUNE_SECTIONS[i] for both the sweep and the scoring. Do not reorder
# after submission. Saved msiPL folders, seed-1 results and /datasets are read only.
source "$HOME/msi/slurm_jobs/test_r_sections.sh"

MSIPL_RETUNE_SECTIONS=(GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2
                       GBM39_1 GBM39_2
                       40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL
                       RCC_MH0204_33 RCC_UH0505_12 RCC_UH0710_33 RCC_UH9610_15
                       RCC_UH9812_03 RCC_UH9905_18 RCC_UH9911_05 RCC_UH9912_01)
MSIPL_RETUNE_PILOT_INDEX=5   # GBM22_2, the largest section (4,524 px x 85,062 bins)
MSIPL_RETUNE_ARMS=(central_only uniform_mean)
MSIPL_RETUNE_RESULTS="$HOME/msi/results"
MSIPL_RETUNE_ROOT="$MSIPL_RETUNE_RESULTS/baselines/msipl/retune_20261030"
MSIPL_RETUNE_FAIR="$MSIPL_RETUNE_RESULTS/diagnostics/fair_scoring_baselines/msipl_retune_20261030"
MSIPL_CHECKPOINTS=/datasets/zsuliman/msi_checkpoints/baselines/msipl

msipl_retune_section() {
    local index="$1"
    if ! [[ "$index" =~ ^[0-9]+$ ]] || (( index >= ${#MSIPL_RETUNE_SECTIONS[@]} )); then
        echo "Invalid msiPL re-tune index: $index" >&2; return 1
    fi
    echo "${MSIPL_RETUNE_SECTIONS[index]}"
}

msipl_retune_weights() {   # section
    case "$(test_r_collection "$1")" in
        GBM) echo "$MSIPL_CHECKPOINTS/massnet/$1/msipl_weights.h5" ;;
        CAC) echo "$MSIPL_CHECKPOINTS/cac/$1/msipl_weights.h5" ;;
        RCC) echo "$MSIPL_CHECKPOINTS/rcc/$1/msipl_weights.h5" ;;
    esac
}

# The saved legacy folder (GBM/CAC only): beta_selection.json, learned_peaks.csv,
# peak_metrics.json. RCC has no saved within-tolerance list for 6/8 runs.
msipl_retune_saved_dir() {   # section
    case "$(test_r_collection "$1")" in
        GBM|CAC) test_r_legacy_dir "$1" ;;
        *) return 1 ;;
    esac
}

msipl_retune_output() { echo "$MSIPL_RETUNE_ROOT/$(test_r_collection "$1")/$1"; }

# Seed-1 IG folders per arm: attribution, matched evaluation, bin-level fair scoring.
# RCC_UH0505_12 uniform_mean seed 1 is the 128-step rerun (Section 6.3 amendment).
msipl_retune_attribution() {   # section arm
    local r="$MSIPL_RETUNE_RESULTS/experiments"
    case "$(test_r_collection "$1")" in
        GBM) echo "$r/spatial_msipl_gmm_integrated_gradients/$1_seed1/$2" ;;
        CAC) echo "$r/spatial_msipl_cac_gmm_integrated_gradients/$1_seed1/$2" ;;
        RCC) if [ "$1/$2" = RCC_UH0505_12/uniform_mean ]; then
                 echo "$r/ig_steps_rerun_20261030/RCC_UH0505_12_seed1/uniform_mean/steps128/attribution"
             else
                 echo "$r/rcc_spatial_msipl/$1_seed1/$2/attribution"
             fi ;;
    esac
}

msipl_retune_evaluation() {   # section arm
    local r="$MSIPL_RETUNE_RESULTS/experiments"
    case "$(test_r_collection "$1")" in
        GBM) echo "$r/spatial_msipl_gbm_tuned_count_evaluation/$1_seed1/$2" ;;
        CAC) echo "$r/spatial_msipl_cac_attributed_peak_evaluation/$1_seed1/$2" ;;
        RCC) if [ "$1/$2" = RCC_UH0505_12/uniform_mean ]; then
                 echo "$r/ig_steps_rerun_20261030/RCC_UH0505_12_seed1/uniform_mean/steps128/peak_evaluation_released_target"
             else
                 echo "$r/rcc_spatial_msipl/$1_seed1/$2/peak_evaluation_released_target"
             fi ;;
    esac
}

msipl_retune_saved_fair() {   # section arm
    local f="$MSIPL_RETUNE_RESULTS/diagnostics/fair_scoring_baselines"
    case "$(test_r_collection "$1")" in
        GBM|CAC) echo "$f/bin_level_only/$1_seed1/$2" ;;
        RCC) if [ "$1/$2" = RCC_UH0505_12/uniform_mean ]; then
                 echo "$f/ig_steps_20261030/bin_level_only/RCC_UH0505_12_seed1/uniform_mean/steps128"
             else
                 echo "$f/rcc/bin_level_only/$1_seed1/$2"
             fi ;;
    esac
}

msipl_retune_score_output() { echo "$MSIPL_RETUNE_FAIR/$1_seed1/$2"; }   # section arm

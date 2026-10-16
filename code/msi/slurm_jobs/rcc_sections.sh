#!/bin/bash
# Shared, ordered RCC run list (protocol 18 Section 6.1, item D step 2; sourced, not run).
# Array index i refers to RCC_SECTIONS[i] (preparation, fair scoring) or to
# RCC_SECTIONS[i % 8] with arm RCC_ARMS[i / 8] (training). Do not reorder after submission.
RCC_SECTIONS=(RCC_MH0204_33 RCC_UH0505_12 RCC_UH0710_33 RCC_UH9610_15
              RCC_UH9812_03 RCC_UH9905_18 RCC_UH9911_05 RCC_UH9912_01)
RCC_ARMS=(central_only uniform_mean)
# 2-run pilot: UH9610_15 (largest, 3,564 px) and UH0710_33 (smallest, 972 px), both arms.
RCC_PILOT_TRAINING_INDICES="2,3,10,11"
RCC_DATA_DIR=/datasets/zsuliman/msi_data/rcc_cardinal
RCC_GMM_COMPONENTS=3
RCC_SENSITIVITY_CLASSES="0 1"   # cancer, normal (encoding in go_no_go.json)

rcc_input_for() {
    case "$1" in
        RCC_*) echo "$RCC_DATA_DIR/$1.h5" ;;
        *) return 1 ;;
    esac
}

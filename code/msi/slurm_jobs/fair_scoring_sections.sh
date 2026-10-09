#!/bin/bash
# Shared, ordered section list for the fair-scoring campaign (sourced, not run).
# Array index i refers to FAIR_SECTIONS[i]. Do not reorder after submission.
FAIR_SECTIONS=(GBM108_positive GBM108_negative GBM12_1 GBM12_2 GBM22_1 GBM22_2 GBM39_1 GBM39_2
               40TopL 160TopL 200TopL 240TopL 280TopL 360TopL 400TopL 520TopL)
FAIR_ARMS=(central_only uniform_mean)
# Largest section by measured pixels x bins (4,524 x 85,062); use it for resource pilots.
FAIR_PILOT_INDEX=5

fair_input_for() {
    case "$1" in
        GBM*) echo "/datasets/zsuliman/msi_data/gbm_massnet/$1.h5" ;;
        *TopL) echo "/datasets/zsuliman/msi_data/cac_msipl/$1.h5" ;;
        *) return 1 ;;
    esac
}

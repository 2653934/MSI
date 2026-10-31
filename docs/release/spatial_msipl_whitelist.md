# Spatial-msiPL release: whitelist manifest (draft, 30 October 2026)

Draft for review (supervisor chat 2026-10-30 14:56 and 14:59). Nothing has been copied yet. Copying happens only after the reruns and the final tables, by copy (never move), followed by a check that the copied scripts regenerate the tables from the copied summaries.

**Scope:** every file under `code/msi/{src,scripts,slurm_jobs}`, plus the provisional result folders that the report's tables and figures currently read. The result list is **provisional**: the report's tables are typed from the verified dump, so the exact summary files can only be fixed after the reruns. `__pycache__`, `.pyc`, `results/` outside the listed folders, `reproducibility/`, `logs/`, data and checkpoints are excluded by construction.

**Flags** (from a read-only text scan):
- `ABS`: absolute paths (`/home-mscluster`, `/datasets/`, `/mnt/c`, `C:/Users`, `$HOME/msi`).
- `USER`: usernames (`zsuliman`, `zayds`).
- `HOST`: cluster host names or the login IP (`mscluster<N>`, `146.141.21.100`, `ms.wits.ac.za`).
- `AI`: AI tool names.
- `CHAT`: references to the supervision chat or meeting notes.
- `S3PL`: imports S3PL code at run time (AGPL-3.0).
- `MSIPL`: imports msiPL code at run time (3D Slicer licence).
- `binary`: not scanned (images).

**Totals:** 449 files, 5.24 MB.
- code: 416 files (`src` 68, `scripts` 118, `slurm_jobs` 230);
- results (provisional): 33 files.

**Flag counts:**
- ABS 233, USER 143, HOST 37, CHAT 75;
- AI 3: `src/spatial_msipl/tests/test_job_scripts.py` (a comment cites the project's assistant-instructions file), and `slurm_jobs/submit_test_r.sh` and `slurm_jobs/test_r_sections.sh` (comments cite a code review by name);
- S3PL 9, MSIPL 4, binary 8.

**Untracked at the time of the scan:** `scripts/check_ig_steps_gate.py` and `slurm_jobs/run_ig_steps_gate_v2.sh` (awaiting Codex).

| Group | File | Bytes | Flags | Tracked |
|---|---|---|---|---|
| code | `src/spatial_msipl/__init__.py` | 330 |  | yes |
| code | `src/spatial_msipl/attribution.py` | 6476 |  | yes |
| code | `src/spatial_msipl/evaluation.py` | 3004 |  | yes |
| code | `src/spatial_msipl/gate_d_helpers.py` | 10383 |  | yes |
| code | `src/spatial_msipl/model.py` | 7085 |  | yes |
| code | `src/spatial_msipl/neighbourhood.py` | 7713 |  | yes |
| code | `src/spatial_msipl/paired_statistics.py` | 4416 |  | yes |
| code | `src/spatial_msipl/peak_groups.py` | 12464 |  | yes |
| code | `src/spatial_msipl/peak_selection.py` | 2983 |  | yes |
| code | `src/spatial_msipl/preprocessing.py` | 12662 |  | yes |
| code | `src/spatial_msipl/provenance.py` | 3275 |  | yes |
| code | `src/spatial_msipl/segmentation_control.py` | 4069 |  | yes |
| code | `src/spatial_msipl/simple_baselines.py` | 10239 |  | yes |
| code | `src/spatial_msipl/spatial_segmentation.py` | 6507 | CHAT | yes |
| code | `src/spatial_msipl/tests/fixtures/pre_rcc/evaluate_fair_scoring_baselines.py` | 23260 |  | yes |
| code | `src/spatial_msipl/tests/fixtures/pre_rcc/evaluate_spatial_msipl_attributed_peaks.py` | 20051 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_boundary.py` | 1123 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_boundary_alignment.py` | 979 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_changed_peaks.py` | 1134 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_context_control.py` | 3289 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_context_shift.py` | 1251 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_frozen_ranking_swap.py` | 4100 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_input_swap.py` | 3304 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_scaling.py` | 2907 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_shuffle_topology.py` | 916 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_vs_uniform.py` | 825 |  | yes |
| code | `src/spatial_msipl/tests/test_attention_weights_audit.py` | 948 |  | yes |
| code | `src/spatial_msipl/tests/test_attribution.py` | 5948 |  | yes |
| code | `src/spatial_msipl/tests/test_attribution_analytic_reference.py` | 5041 |  | yes |
| code | `src/spatial_msipl/tests/test_centre_masking.py` | 11577 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_data_contract_audit.py` | 6590 |  | yes |
| code | `src/spatial_msipl/tests/test_evaluation.py` | 1582 |  | yes |
| code | `src/spatial_msipl/tests/test_fair_scoring_arms.py` | 10670 |  | yes |
| code | `src/spatial_msipl/tests/test_fair_scoring_pipeline.py` | 34088 |  | yes |
| code | `src/spatial_msipl/tests/test_fair_scoring_summary.py` | 5999 |  | yes |
| code | `src/spatial_msipl/tests/test_gate_d_helpers.py` | 17016 |  | yes |
| code | `src/spatial_msipl/tests/test_ig_steps.py` | 26615 | ABS,CHAT | yes |
| code | `src/spatial_msipl/tests/test_job_scripts.py` | 2621 | AI,CHAT | yes |
| code | `src/spatial_msipl/tests/test_model.py` | 12622 |  | yes |
| code | `src/spatial_msipl/tests/test_model_foundation_audit.py` | 6386 |  | yes |
| code | `src/spatial_msipl/tests/test_neighbourhood.py` | 11635 |  | yes |
| code | `src/spatial_msipl/tests/test_pca_reconstruction_v.py` | 17359 |  | yes |
| code | `src/spatial_msipl/tests/test_peak_groups.py` | 7325 |  | yes |
| code | `src/spatial_msipl/tests/test_peak_selection.py` | 1448 |  | yes |
| code | `src/spatial_msipl/tests/test_preprocessing.py` | 5600 |  | yes |
| code | `src/spatial_msipl/tests/test_provenance.py` | 2251 |  | yes |
| code | `src/spatial_msipl/tests/test_ranking_stage_runtime.py` | 19955 | ABS,USER,HOST,CHAT | yes |
| code | `src/spatial_msipl/tests/test_rcc_pipeline.py` | 29832 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_runtime_v2.py` | 12493 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_s3pl_investigation_21_bd.py` | 12968 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_s3pl_investigation_21_c.py` | 7552 |  | yes |
| code | `src/spatial_msipl/tests/test_s3pl_rcc_adapter.py` | 4490 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_s3pl_seed_investigation_21.py` | 7152 |  | yes |
| code | `src/spatial_msipl/tests/test_s3pl_seed_provenance.py` | 8854 | ABS,CHAT | yes |
| code | `src/spatial_msipl/tests/test_s3pl_shuffle_control.py` | 5002 |  | yes |
| code | `src/spatial_msipl/tests/test_segmentation_control_v.py` | 21257 |  | yes |
| code | `src/spatial_msipl/tests/test_simple_baselines.py` | 8160 |  | yes |
| code | `src/spatial_msipl/tests/test_spatial_context_information.py` | 2498 |  | yes |
| code | `src/spatial_msipl/tests/test_spatial_context_model_sensitivity.py` | 3907 |  | yes |
| code | `src/spatial_msipl/tests/test_spatial_latent_separability.py` | 1736 |  | yes |
| code | `src/spatial_msipl/tests/test_spatial_segmentation.py` | 22304 | CHAT | yes |
| code | `src/spatial_msipl/tests/test_spatial_unsupervised_clusterers.py` | 1648 |  | yes |
| code | `src/spatial_msipl/tests/test_statistics_6_6.py` | 7726 |  | yes |
| code | `src/spatial_msipl/tests/test_test_r.py` | 21447 | ABS,USER,CHAT | yes |
| code | `src/spatial_msipl/tests/test_window_peak_scoring_audit.py` | 1900 |  | yes |
| code | `src/spatial_msipl/tests/test_window_topology_audit.py` | 1717 |  | yes |
| code | `src/spatial_msipl/tests/test_windows.py` | 12368 |  | yes |
| code | `src/spatial_msipl/training.py` | 28806 |  | yes |
| code | `scripts/analyse_s3pl_cac_gap.py` | 11915 |  | yes |
| code | `scripts/audit_attention_boundary.py` | 10265 |  | yes |
| code | `scripts/audit_attention_boundary_alignment.py` | 9371 |  | yes |
| code | `scripts/audit_attention_context_shift.py` | 7468 |  | yes |
| code | `scripts/audit_attention_shuffle_topology.py` | 5228 |  | yes |
| code | `scripts/audit_attention_vs_uniform.py` | 9978 |  | yes |
| code | `scripts/audit_attention_weights.py` | 9111 | ABS,USER | yes |
| code | `scripts/audit_centremask_attention_weights.py` | 3474 | CHAT | yes |
| code | `scripts/audit_peak_partitions.py` | 6632 |  | yes |
| code | `scripts/audit_rcc_dataset.R` | 5542 |  | yes |
| code | `scripts/audit_s3pl_cac_reference_sets.py` | 5864 |  | yes |
| code | `scripts/audit_s3pl_massnet_systematics.py` | 5854 | S3PL | yes |
| code | `scripts/audit_spatial_attention_changed_peaks.py` | 10601 |  | yes |
| code | `scripts/audit_spatial_attention_input_swap.py` | 15631 |  | yes |
| code | `scripts/audit_spatial_cac_validation_training.py` | 5599 |  | yes |
| code | `scripts/audit_spatial_context_information.py` | 9428 |  | yes |
| code | `scripts/audit_spatial_context_model_sensitivity.py` | 11469 |  | yes |
| code | `scripts/audit_spatial_gbm_validation_training.py` | 6073 |  | yes |
| code | `scripts/audit_spatial_ig_component_contributions.py` | 8253 |  | yes |
| code | `scripts/audit_spatial_ig_ranking_provenance.py` | 12558 |  | yes |
| code | `scripts/audit_spatial_latent_separability.py` | 6151 |  | yes |
| code | `scripts/audit_spatial_msipl_data_contract.py` | 17848 |  | yes |
| code | `scripts/audit_spatial_publication_aggregate.py` | 7308 |  | yes |
| code | `scripts/audit_spatial_unsupervised_clusterers.py` | 7113 |  | yes |
| code | `scripts/audit_spatial_window_topology.py` | 7548 |  | yes |
| code | `scripts/audit_window_peak_scoring.py` | 7378 |  | yes |
| code | `scripts/benchmark_spatial_msipl_cache.py` | 5497 |  | yes |
| code | `scripts/benchmark_spatial_msipl_gpu_feasibility.py` | 5783 |  | yes |
| code | `scripts/bic_segmentation_sensitivity.py` | 10483 |  | yes |
| code | `scripts/build_current_evidence_tables.py` | 19790 | CHAT | yes |
| code | `scripts/build_runtime_and_training_curves.py` | 22132 | CHAT | yes |
| code | `scripts/calibrate_poisson_augmentation.py` | 4966 |  | yes |
| code | `scripts/check_gate_d_n12_reproduction.py` | 7598 |  | yes |
| code | `scripts/check_gate_d_uniform_consistency.py` | 3394 |  | yes |
| code | `scripts/check_ig_steps_gate.py` | 8440 | CHAT | NO |
| code | `scripts/check_s3pl_rcc_labels.py` | 6597 | CHAT,S3PL | yes |
| code | `scripts/check_saved_list_reproduction.py` | 4334 |  | yes |
| code | `scripts/check_spatial_attention_scaling.py` | 9992 |  | yes |
| code | `scripts/compare_gbm_imzml_h5.py` | 7749 |  | yes |
| code | `scripts/compare_spatial_msipl_cache_checkpoints.py` | 3291 |  | yes |
| code | `scripts/compare_spatial_msipl_cache_training.py` | 8447 |  | yes |
| code | `scripts/compute_reference_budget.py` | 8161 | CHAT | yes |
| code | `scripts/compute_statistics_6_6.py` | 23712 | CHAT | yes |
| code | `scripts/create_massnet_gbm_masks.py` | 7143 |  | yes |
| code | `scripts/diagnose_msipl_gbm.py` | 4851 |  | yes |
| code | `scripts/evaluate_fair_scoring_baselines.py` | 27840 |  | yes |
| code | `scripts/evaluate_gate_d_pixel_counts.py` | 15869 |  | yes |
| code | `scripts/evaluate_msipl_massnet_peaks.py` | 7697 |  | yes |
| code | `scripts/evaluate_pca_reconstruction_v.py` | 7155 | CHAT | yes |
| code | `scripts/evaluate_poisson_augmentation_pilot.py` | 17233 |  | yes |
| code | `scripts/evaluate_s3pl_cac_frozen_context.py` | 9836 | S3PL | yes |
| code | `scripts/evaluate_s3pl_cac_frozen_topology.py` | 7119 | S3PL | yes |
| code | `scripts/evaluate_s3pl_epoch_checkpoints.py` | 3170 | S3PL | yes |
| code | `scripts/evaluate_s3pl_matched_peak_count.py` | 1600 | S3PL | yes |
| code | `scripts/evaluate_segmentation_control_v.py` | 16290 | CHAT | yes |
| code | `scripts/evaluate_spatial_attention_frozen_ranking_swap.py` | 18999 |  | yes |
| code | `scripts/evaluate_spatial_loss_pilots.py` | 9878 |  | yes |
| code | `scripts/evaluate_spatial_msipl_attributed_peaks.py` | 21052 |  | yes |
| code | `scripts/evaluate_spatial_msipl_neighbourhoods.py` | 26778 |  | yes |
| code | `scripts/evaluate_spatial_reconstruction.py` | 9382 |  | yes |
| code | `scripts/evaluate_spatial_segmentation_s.py` | 16638 | CHAT | yes |
| code | `scripts/evaluate_spatial_window_reconstruction.py` | 2754 |  | yes |
| code | `scripts/export_rcc_ion_images.py` | 4486 | CHAT | yes |
| code | `scripts/inspect_cac_masks.py` | 978 | ABS,USER | yes |
| code | `scripts/inspect_gbm.py` | 887 | ABS,USER | yes |
| code | `scripts/inspect_massnet_gbm.py` | 4059 |  | yes |
| code | `scripts/pilot_spatial_msipl_neighbourhood_training.py` | 4737 |  | yes |
| code | `scripts/plot_s3pl_seed_distributions.py` | 4650 |  | yes |
| code | `scripts/plot_spatial_reconstruction_comparison.py` | 2743 |  | yes |
| code | `scripts/plot_training_loss.py` | 1439 |  | yes |
| code | `scripts/prepare_msipl_cac_h5.py` | 5429 | S3PL | yes |
| code | `scripts/prepare_s3pl_gbm_imzml_pilot.py` | 4071 |  | yes |
| code | `scripts/profile_s3pl_training.py` | 6712 | S3PL | yes |
| code | `scripts/profile_spatial_msipl_training.py` | 8214 |  | yes |
| code | `scripts/rcc_feasibility_export.R` | 7985 | CHAT | yes |
| code | `scripts/run_msipl_gbm.py` | 17216 | MSIPL | yes |
| code | `scripts/run_msipl_legacy_gbm.py` | 16446 | MSIPL | yes |
| code | `scripts/run_spatial_msipl_gmm_integrated_gradients.py` | 34394 |  | yes |
| code | `scripts/select_gmm_k_bic.py` | 3965 |  | yes |
| code | `scripts/smoke_test_spatial_msipl_vae.py` | 2642 |  | yes |
| code | `scripts/summarise_fair_scoring_arms.py` | 14866 | CHAT | yes |
| code | `scripts/summarise_fair_scoring_baselines.py` | 8581 |  | yes |
| code | `scripts/summarise_gate_d_pixel_counts.py` | 2795 |  | yes |
| code | `scripts/summarise_ig_steps.py` | 12933 | CHAT | yes |
| code | `scripts/summarise_msipl_weigand_comparison.py` | 8592 |  | yes |
| code | `scripts/summarise_pca_reconstruction_v.py` | 12242 | CHAT | yes |
| code | `scripts/summarise_publication_results.py` | 19877 |  | yes |
| code | `scripts/summarise_ranking_stage_runtime.py` | 5565 | CHAT | yes |
| code | `scripts/summarise_rcc_fair_scoring.py` | 11069 | CHAT | yes |
| code | `scripts/summarise_s3pl_cac_shuffle_control.py` | 10612 | CHAT | yes |
| code | `scripts/summarise_s3pl_gbm_stability_runtime.py` | 16635 |  | yes |
| code | `scripts/summarise_s3pl_investigation_21_bd.py` | 11595 | CHAT | yes |
| code | `scripts/summarise_s3pl_investigation_21_c.py` | 9512 | CHAT | yes |
| code | `scripts/summarise_s3pl_massnet.py` | 18913 |  | yes |
| code | `scripts/summarise_s3pl_seed_investigation_21.py` | 23923 | CHAT | yes |
| code | `scripts/summarise_s3pl_seed_runs.py` | 15463 | CHAT | yes |
| code | `scripts/summarise_segmentation_control_v.py` | 10903 | CHAT | yes |
| code | `scripts/summarise_spatial_gbm_attributed_peaks.py` | 8255 |  | yes |
| code | `scripts/summarise_spatial_gbm_context_attribution.py` | 8323 |  | yes |
| code | `scripts/summarise_spatial_gbm_reconstruction.py` | 9561 |  | yes |
| code | `scripts/summarise_spatial_ig_stability.py` | 6153 |  | yes |
| code | `scripts/summarise_spatial_msipl_cac_validation.py` | 16301 |  | yes |
| code | `scripts/summarise_spatial_msipl_gbm_tuned_counts.py` | 11268 |  | yes |
| code | `scripts/summarise_spatial_msipl_training_seed_stability.py` | 11230 |  | yes |
| code | `scripts/summarise_spatial_segmentation_s.py` | 9233 | CHAT | yes |
| code | `scripts/summarise_test_r.py` | 16552 | ABS,USER,CHAT | yes |
| code | `scripts/time_ranking_stages.py` | 14047 | CHAT | yes |
| code | `scripts/train_spatial_msipl_production.py` | 13198 |  | yes |
| code | `scripts/train_spatial_msipl_stability.py` | 6129 |  | yes |
| code | `scripts/tune_msipl_massnet_beta.py` | 5640 |  | yes |
| code | `scripts/validate_s3pl_massnet_adapter.py` | 4367 | S3PL | yes |
| code | `scripts/validate_spatial_msipl_neighbourhoods.py` | 4720 |  | yes |
| code | `scripts/validate_spatial_msipl_preprocessing.py` | 2528 |  | yes |
| code | `scripts/validate_spatial_window_cache.py` | 2325 |  | yes |
| code | `scripts/visualise_cac.py` | 27004 | ABS,USER | yes |
| code | `scripts/visualise_gbm_imzml_comparison.py` | 11844 |  | yes |
| code | `scripts/visualise_massnet_gbm.py` | 19092 |  | yes |
| code | `scripts/visualise_msipl_legacy_gbm.py` | 16716 | MSIPL | yes |
| code | `slurm_jobs/audit_attention_boundary.sh` | 1451 | ABS,USER | yes |
| code | `slurm_jobs/audit_attention_boundary_alignment.sh` | 1436 | ABS,USER | yes |
| code | `slurm_jobs/audit_attention_context_shift.sh` | 1445 | ABS,USER | yes |
| code | `slurm_jobs/audit_attention_shuffle_topology.sh` | 1369 | ABS,USER | yes |
| code | `slurm_jobs/audit_attention_vs_uniform.sh` | 1456 | ABS,USER | yes |
| code | `slurm_jobs/audit_attention_weights.sh` | 1454 | ABS,USER | yes |
| code | `slurm_jobs/audit_rcc_dataset.sh` | 1717 | ABS,USER | yes |
| code | `slurm_jobs/audit_s3pl_cac_frozen_context.sh` | 1552 | ABS | yes |
| code | `slurm_jobs/audit_s3pl_cac_frozen_topology.sh` | 1634 | ABS | yes |
| code | `slurm_jobs/audit_s3pl_cac_reference_sets.sh` | 924 | ABS,USER | yes |
| code | `slurm_jobs/audit_s3pl_massnet_systematics.sh` | 930 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_attention_changed_peaks.sh` | 1748 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_attention_input_swap.sh` | 2836 | ABS,USER,HOST | yes |
| code | `slurm_jobs/audit_spatial_context_information.sh` | 1401 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_context_model_sensitivity.sh` | 2650 | ABS,USER,HOST | yes |
| code | `slurm_jobs/audit_spatial_ig_component_contributions.sh` | 1345 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_latent_separability.sh` | 1726 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_msipl_data_contract.sh` | 2458 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_msipl_gbm_tuned_scoring.sh` | 1440 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_msipl_model_foundation.sh` | 875 | ABS | yes |
| code | `slurm_jobs/audit_spatial_msipl_score_foundation.sh` | 2150 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_unsupervised_clusterers.sh` | 1737 | ABS,USER | yes |
| code | `slurm_jobs/audit_spatial_window_topology.sh` | 1254 | ABS,USER | yes |
| code | `slurm_jobs/audit_window_peak_scoring.sh` | 1183 | ABS,USER | yes |
| code | `slurm_jobs/benchmark_spatial_msipl_cache.sh` | 882 | ABS,USER | yes |
| code | `slurm_jobs/benchmark_spatial_msipl_gpu_feasibility.sh` | 1162 | ABS,USER | yes |
| code | `slurm_jobs/calibrate_spatial_msipl_poisson.sh` | 882 | ABS,USER | yes |
| code | `slurm_jobs/check_centremask_campaign.sh` | 1680 | ABS | yes |
| code | `slurm_jobs/check_fair_scoring_campaign.sh` | 1085 | ABS | yes |
| code | `slurm_jobs/check_s3pl_cac_centre_control_seed2.sh` | 2725 | ABS | yes |
| code | `slurm_jobs/check_s3pl_cac_frozen_topology.sh` | 1881 | ABS | yes |
| code | `slurm_jobs/check_s3pl_cac_trained_centre_control.sh` | 2604 | ABS | yes |
| code | `slurm_jobs/check_s3pl_gbm_p3_seed_probe.sh` | 2902 | ABS | yes |
| code | `slurm_jobs/check_s3pl_gbm_positive_epoch_rescue.sh` | 4518 | ABS | yes |
| code | `slurm_jobs/check_s3pl_gbm_positive_initialization_sweep.sh` | 4297 | ABS | yes |
| code | `slurm_jobs/check_s3pl_gbm_positive_seed_factors.sh` | 3901 | ABS | yes |
| code | `slurm_jobs/check_s3pl_gbm_seed_screen.sh` | 4649 | ABS | yes |
| code | `slurm_jobs/check_s3pl_vae_cac_runtime_workflow.sh` | 3323 | ABS | yes |
| code | `slurm_jobs/check_spatial_attention_changed_peaks_campaign.sh` | 1065 | ABS | yes |
| code | `slurm_jobs/check_spatial_attention_context.sh` | 1265 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_attention_frozen_ranking_campaign.sh` | 1296 | ABS | yes |
| code | `slurm_jobs/check_spatial_attention_scaling.sh` | 1145 | ABS,USER,HOST | yes |
| code | `slurm_jobs/check_spatial_attention_seed_repeat.sh` | 1555 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_attention_swap_campaign.sh` | 1465 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_msipl_cac_evaluation.sh` | 1592 | ABS | yes |
| code | `slurm_jobs/check_spatial_msipl_cac_validation.sh` | 1518 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_msipl_gbm_tuned_count_evaluation.sh` | 3205 | ABS | yes |
| code | `slurm_jobs/check_spatial_msipl_gbm_validation.sh` | 2563 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_msipl_neighbourhood_attribution.sh` | 1684 | ABS | yes |
| code | `slurm_jobs/check_spatial_msipl_seed_stability_training.sh` | 2384 | ABS | yes |
| code | `slurm_jobs/check_spatial_msipl_training_seed_stability_evaluation.sh` | 2052 | ABS | yes |
| code | `slurm_jobs/check_spatial_window_campaign.sh` | 1785 | ABS,USER | yes |
| code | `slurm_jobs/check_spatial_window_implementation.sh` | 786 | ABS | yes |
| code | `slurm_jobs/compare_gbm_imzml_h5.sh` | 1128 | ABS,USER | yes |
| code | `slurm_jobs/compare_s3pl_cached_vae_phases.sh` | 1702 | ABS,USER,HOST | yes |
| code | `slurm_jobs/compare_spatial_msipl_cache_checkpoints.sh` | 1349 | ABS,USER | yes |
| code | `slurm_jobs/compare_spatial_msipl_cache_training.sh` | 1160 | ABS,USER,HOST | yes |
| code | `slurm_jobs/create_massnet_gbm_masks.sh` | 946 | ABS,USER | yes |
| code | `slurm_jobs/diagnose_msipl_gbm.sh` | 1387 | ABS,USER | yes |
| code | `slurm_jobs/evaluate_spatial_attention_frozen_ranking_swap.sh` | 2733 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_attention_uniform_weight_ablation.sh` | 2434 | ABS,USER | yes |
| code | `slurm_jobs/evaluate_spatial_gbm_reconstruction.sh` | 1539 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_loss_pilots.sh` | 1364 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_msipl_attributed_peaks.sh` | 1351 | ABS,USER | yes |
| code | `slurm_jobs/evaluate_spatial_msipl_cac_reconstruction.sh` | 1754 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_msipl_neighbourhoods.sh` | 1483 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_msipl_poisson_pilot.sh` | 1951 | ABS,USER,HOST | yes |
| code | `slurm_jobs/evaluate_spatial_reconstruction.sh` | 1166 | ABS,USER,HOST | yes |
| code | `slurm_jobs/extract_massnet_gbm.sh` | 2989 | ABS,USER | yes |
| code | `slurm_jobs/extract_s3pl_gbm_imzml.sh` | 2682 | ABS,USER | yes |
| code | `slurm_jobs/fair_scoring_sections.sh` | 701 | ABS,USER | yes |
| code | `slurm_jobs/gpu_cuda_quarantine.txt` | 488 | HOST | yes |
| code | `slurm_jobs/ig_steps_sections.sh` | 3828 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/inspect_cac_masks.sh` | 835 | ABS,USER | yes |
| code | `slurm_jobs/inspect_gbm.sh` | 845 | ABS,USER | yes |
| code | `slurm_jobs/inspect_massnet_gbm.sh` | 931 | ABS,USER | yes |
| code | `slurm_jobs/pilot_spatial_msipl_neighbourhood_training.sh` | 1140 | ABS,USER | yes |
| code | `slurm_jobs/prepare_msipl_cac_pilot.sh` | 1244 | ABS,USER | yes |
| code | `slurm_jobs/profile_spatial_msipl_training.sh` | 1322 | ABS,USER,HOST | yes |
| code | `slurm_jobs/rcc_sections.sh` | 845 | ABS,USER | yes |
| code | `slurm_jobs/resume_s3pl_vae_cac_runtime_peak_evaluation.sh` | 2922 | ABS,USER | yes |
| code | `slurm_jobs/run_centremask_campaign.sh` | 9025 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_fair_scoring_array.sh` | 3471 | ABS | yes |
| code | `slurm_jobs/run_fair_scoring_extra_arm.sh` | 5865 | ABS | yes |
| code | `slurm_jobs/run_fair_scoring_summary.sh` | 1170 | ABS | yes |
| code | `slurm_jobs/run_fair_scoring_tests.sh` | 3183 | ABS | yes |
| code | `slurm_jobs/run_gate_d_bic.sh` | 2995 | ABS,USER | yes |
| code | `slurm_jobs/run_gate_d_evaluation.sh` | 2914 | ABS,USER | yes |
| code | `slurm_jobs/run_gate_d_pixel_count_ig.sh` | 7031 | ABS,USER | yes |
| code | `slurm_jobs/run_gate_d_summary.sh` | 797 | ABS | yes |
| code | `slurm_jobs/run_ig_steps_fair_scoring.sh` | 3980 | ABS | yes |
| code | `slurm_jobs/run_ig_steps_gate_v2.sh` | 4931 | ABS,CHAT | NO |
| code | `slurm_jobs/run_ig_steps_rerun.sh` | 11152 | ABS,CHAT | yes |
| code | `slurm_jobs/run_msipl_cac_pilot.sh` | 1652 | ABS,USER | yes |
| code | `slurm_jobs/run_msipl_cac_section.sh` | 3698 | ABS,USER | yes |
| code | `slurm_jobs/run_msipl_gbm.sh` | 1434 | ABS,USER | yes |
| code | `slurm_jobs/run_msipl_legacy_s1.sh` | 1323 | ABS,USER | yes |
| code | `slurm_jobs/run_msipl_massnet_gbm.sh` | 1666 | ABS,USER | yes |
| code | `slurm_jobs/run_msipl_rcc.sh` | 4216 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_pca_reconstruction_v.sh` | 2237 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_peak_partition_audit_array.sh` | 2244 | ABS | yes |
| code | `slurm_jobs/run_ranking_stage_timing.sh` | 3997 | ABS,CHAT | yes |
| code | `slurm_jobs/run_rcc_bic.sh` | 2567 | ABS,CHAT | yes |
| code | `slurm_jobs/run_rcc_campaign.sh` | 6787 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_rcc_fair_scoring.sh` | 4047 | ABS | yes |
| code | `slurm_jobs/run_rcc_feasibility.sh` | 5554 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_rcc_ion_image_export.sh` | 1483 | ABS,CHAT | yes |
| code | `slurm_jobs/run_rcc_preparation.sh` | 2694 | ABS | yes |
| code | `slurm_jobs/run_s3pl_cac.sh` | 780 | ABS,USER | yes |
| code | `slurm_jobs/run_s3pl_cac_centre_control_seed2.sh` | 4386 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_cac_matched_evaluation.sh` | 1503 | ABS | yes |
| code | `slurm_jobs/run_s3pl_cac_seeds.sh` | 2921 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_cac_shuffle_control.sh` | 4664 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_cac_trained_centre_control.sh` | 3070 | ABS,USER | yes |
| code | `slurm_jobs/run_s3pl_e100.sh` | 4081 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_gbm_imzml_pilot.sh` | 2804 | ABS,USER | yes |
| code | `slurm_jobs/run_s3pl_gbm_seed_screen_array.sh` | 2015 | ABS | yes |
| code | `slurm_jobs/run_s3pl_massnet_gbm.sh` | 3083 | ABS,USER | yes |
| code | `slurm_jobs/run_s3pl_rcc.sh` | 3315 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_rcc_gate.sh` | 1594 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_s3pl_vae_cac_runtime_workflow.sh` | 6820 | ABS,USER | yes |
| code | `slurm_jobs/run_segmentation_control_v.sh` | 3868 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_spatial_attention_changed_peaks_campaign_array.sh` | 2572 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_attention_context_evaluation.sh` | 5435 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_attention_context_training.sh` | 3854 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_attention_frozen_ranking_campaign_array.sh` | 3834 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_attention_seed_repeat_array.sh` | 7267 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_attention_sqrt_pilot.sh` | 1419 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_attention_sqrt_production.sh` | 2088 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_attention_swap_campaign_array.sh` | 1733 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_ig_stability_repeat.sh` | 2403 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_cac_attribution.sh` | 5393 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_cac_validation_training.sh` | 2856 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_cached_full.sh` | 2612 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_central_only.sh` | 1995 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_gbm_attribution.sh` | 7045 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_msipl_gbm_tuned_count_evaluation.sh` | 3744 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_msipl_gbm_validation_training.sh` | 2811 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_gmm_ig_pilot.sh` | 1562 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_lambda_pilot.sh` | 1750 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_poisson_pilot.sh` | 1743 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_production.sh` | 2238 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_msipl_seed_stability_training.sh` | 3158 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_msipl_stability.sh` | 1583 | ABS,USER | yes |
| code | `slurm_jobs/run_spatial_segmentation_s.sh` | 3699 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/run_spatial_window_campaign_array.sh` | 1262 | ABS,HOST | yes |
| code | `slurm_jobs/run_spatial_window_campaign_evaluation_array.sh` | 1117 | ABS,HOST | yes |
| code | `slurm_jobs/run_spatial_window_pilot_evaluation.sh` | 4520 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_spatial_window_pilot_training.sh` | 3920 | ABS,USER,HOST | yes |
| code | `slurm_jobs/run_test_r_campaign.sh` | 8763 | ABS,CHAT | yes |
| code | `slurm_jobs/run_test_r_fair_scoring.sh` | 3788 | ABS | yes |
| code | `slurm_jobs/run_window_e79_campaign.sh` | 7473 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/smoke_test_spatial_msipl_vae.sh` | 1032 | ABS,USER | yes |
| code | `slurm_jobs/submit_centremask_campaign.sh` | 3052 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/submit_fair_scoring.sh` | 2432 | ABS | yes |
| code | `slurm_jobs/submit_fair_scoring_extra_arm.sh` | 2374 | ABS | yes |
| code | `slurm_jobs/submit_gate_d_bic.sh` | 1653 | ABS | yes |
| code | `slurm_jobs/submit_gate_d_pixel_counts.sh` | 4463 | ABS | yes |
| code | `slurm_jobs/submit_ig_steps.sh` | 3961 | ABS | yes |
| code | `slurm_jobs/submit_msipl_cac_remaining.sh` | 916 | ABS | yes |
| code | `slurm_jobs/submit_msipl_massnet_beta_remaining.sh` | 1912 | ABS,USER | yes |
| code | `slurm_jobs/submit_msipl_massnet_remaining.sh` | 1821 | ABS,USER | yes |
| code | `slurm_jobs/submit_msipl_rcc.sh` | 1116 | ABS,USER | yes |
| code | `slurm_jobs/submit_pca_reconstruction_v.sh` | 512 | ABS | yes |
| code | `slurm_jobs/submit_peak_partition_audit.sh` | 2037 | ABS | yes |
| code | `slurm_jobs/submit_rcc.sh` | 4550 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/submit_rcc_ranking_stage_timing.sh` | 2157 | ABS,USER,HOST,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_cac_centre_control_seed2.sh` | 2942 | ABS,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_cac_frozen_topology.sh` | 921 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_cac_matched_evaluation.sh` | 718 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_cac_seeds.sh` | 1905 | ABS,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_cac_shuffle_control.sh` | 2491 | ABS,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_cac_trained_centre_control.sh` | 1156 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_e100.sh` | 2400 | ABS,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_gbm108_positive_p3_paper_tic.sh` | 1360 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_gbm108_positive_p3_repeat1.sh` | 4083 |  | yes |
| code | `slurm_jobs/submit_s3pl_gbm_imzml_pilot.sh` | 1347 | ABS,USER | yes |
| code | `slurm_jobs/submit_s3pl_gbm_p3_seed_probe.sh` | 2096 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_gbm_positive_epoch_rescue.sh` | 2579 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_gbm_positive_initialization_sweep.sh` | 2499 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_gbm_positive_seed_factors.sh` | 2753 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_gbm_seed_screen.sh` | 1731 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_massnet_paper_tic_remaining.sh` | 1879 | ABS | yes |
| code | `slurm_jobs/submit_s3pl_massnet_patch3.sh` | 1277 |  | yes |
| code | `slurm_jobs/submit_s3pl_massnet_remaining.sh` | 1233 |  | yes |
| code | `slurm_jobs/submit_s3pl_rcc.sh` | 2766 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/submit_s3pl_vae_cac_runtime_workflow.sh` | 825 | ABS | yes |
| code | `slurm_jobs/submit_segmentation_control_v.sh` | 1631 | ABS | yes |
| code | `slurm_jobs/submit_spatial_attention_changed_peaks_campaign.sh` | 2139 | ABS | yes |
| code | `slurm_jobs/submit_spatial_attention_context_training.sh` | 1170 | ABS,USER | yes |
| code | `slurm_jobs/submit_spatial_attention_frozen_ranking_campaign.sh` | 2812 | ABS,USER | yes |
| code | `slurm_jobs/submit_spatial_attention_swap_campaign.sh` | 2468 | ABS,USER | yes |
| code | `slurm_jobs/submit_spatial_gbm_reconstruction_evaluation.sh` | 916 | ABS | yes |
| code | `slurm_jobs/submit_spatial_ig_stability.sh` | 798 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_cac_pilot_evaluation.sh` | 739 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_cac_remaining_evaluation.sh` | 1293 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_cac_validation_training.sh` | 1545 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_gbm_attribution.sh` | 2935 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_gbm_central_attribution.sh` | 3043 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_gbm_validation_training.sh` | 1452 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_lambda_pilots.sh` | 495 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_neighbourhood_attribution.sh` | 1464 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_production.sh` | 1185 | ABS,USER | yes |
| code | `slurm_jobs/submit_spatial_msipl_seed_stability_training.sh` | 2019 | ABS | yes |
| code | `slurm_jobs/submit_spatial_msipl_stability.sh` | 1000 |  | yes |
| code | `slurm_jobs/submit_spatial_msipl_training_seed_stability_evaluation.sh` | 3207 | ABS | yes |
| code | `slurm_jobs/submit_spatial_segmentation_s.sh` | 1444 | ABS | yes |
| code | `slurm_jobs/submit_spatial_window_campaign.sh` | 2505 | ABS,USER | yes |
| code | `slurm_jobs/submit_spatial_window_campaign_evaluation.sh` | 2174 | ABS,USER | yes |
| code | `slurm_jobs/submit_test_r.sh` | 5473 | ABS,AI,CHAT | yes |
| code | `slurm_jobs/submit_window_e79_campaign.sh` | 2687 | ABS,USER,CHAT | yes |
| code | `slurm_jobs/summarise_publication_results.sh` | 517 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_gbm_reconstruction.sh` | 620 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_ig_stability.sh` | 906 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_msipl_cac_validation.sh` | 629 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_msipl_gbm_attribution.sh` | 615 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_msipl_gbm_context_attribution.sh` | 644 | ABS | yes |
| code | `slurm_jobs/summarise_spatial_msipl_training_seed_stability.sh` | 609 | ABS | yes |
| code | `slurm_jobs/test_msipl_legacy.sh` | 2045 | MSIPL | yes |
| code | `slurm_jobs/test_r_sections.sh` | 4566 | ABS,USER,AI,CHAT | yes |
| code | `slurm_jobs/tune_msipl_cac_pilot.sh` | 1703 | ABS,USER | yes |
| code | `slurm_jobs/tune_msipl_massnet_beta.sh` | 2084 | ABS,USER | yes |
| code | `slurm_jobs/validate_s3pl_massnet_adapter.sh` | 936 | ABS,USER | yes |
| code | `slurm_jobs/validate_spatial_msipl_neighbourhoods.sh` | 887 | ABS,USER | yes |
| code | `slurm_jobs/validate_spatial_msipl_preprocessing.sh` | 791 | ABS,USER | yes |
| code | `slurm_jobs/visualise_cac.sh` | 717 | ABS,USER | yes |
| code | `slurm_jobs/visualise_gbm_imzml_comparison.sh` | 1164 | ABS,USER | yes |
| code | `slurm_jobs/visualise_massnet_gbm.sh` | 1236 | ABS,USER | yes |
| code | `slurm_jobs/visualise_msipl_legacy_gbm.sh` | 1158 | ABS,USER | yes |
| code | `slurm_jobs/visualise_s3pl_cac_gap_ions.sh` | 895 | ABS,USER | yes |
| results (provisional) | `results/publication/current_evidence/aggregate_method_results.csv` | 817 |  | yes |
| results (provisional) | `results/publication/current_evidence/fair_scoring_bin_level_sections.csv` | 10295 |  | yes |
| results (provisional) | `results/publication/current_evidence/fair_scoring_collection_summary.csv` | 7932 |  | yes |
| results (provisional) | `results/publication/current_evidence/fair_scoring_partition_sections.csv` | 23633 |  | yes |
| results (provisional) | `results/publication/current_evidence/figure_1_primary_peak_quality.png` | 122856 | binary | yes |
| results (provisional) | `results/publication/current_evidence/figure_2_context_effect_by_section.png` | 161821 | binary | yes |
| results (provisional) | `results/publication/current_evidence/figure_3_explanation_ablation.png` | 67853 | binary | yes |
| results (provisional) | `results/publication/current_evidence/figure_4_seed_stability.png` | 186035 | binary | yes |
| results (provisional) | `results/publication/current_evidence/figure_5_context_peak_overlap.png` | 196110 | binary | yes |
| results (provisional) | `results/publication/current_evidence/figure_s1_s3pl_contextual_cac.png` | 178780 | binary | yes |
| results (provisional) | `results/publication/current_evidence/gate_d_bic.csv` | 2123 |  | yes |
| results (provisional) | `results/publication/current_evidence/gate_d_pixel_counts.csv` | 1919 |  | yes |
| results (provisional) | `results/publication/current_evidence/README.md` | 7406 |  | yes |
| results (provisional) | `results/publication/current_evidence/runtime_all_sections.csv` | 23112 |  | yes |
| results (provisional) | `results/publication/current_evidence/runtime_all_sections_v2.csv` | 91799 | HOST,CHAT | yes |
| results (provisional) | `results/publication/current_evidence/s3pl_cac_controls.csv` | 3286 |  | yes |
| results (provisional) | `results/publication/current_evidence/s3pl_cac_seed_rule.json` | 1015 | CHAT | yes |
| results (provisional) | `results/publication/current_evidence/section_level_results.csv` | 2768 |  | yes |
| results (provisional) | `results/publication/current_evidence/training_curves.png` | 257984 | binary | yes |
| results (provisional) | `results/publication/current_evidence/training_curves_s3pl.csv` | 107194 |  | yes |
| results (provisional) | `results/publication/current_evidence/training_curves_vae.csv` | 828371 |  | yes |
| results (provisional) | `results/diagnostics/statistics_6_6/mann_whitney.csv` | 330 |  | yes |
| results (provisional) | `results/diagnostics/statistics_6_6/mixed_models.csv` | 3744 |  | yes |
| results (provisional) | `results/diagnostics/statistics_6_6/summary.json` | 8691 | CHAT | yes |
| results (provisional) | `results/diagnostics/statistics_6_6/tests.csv` | 42825 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/jaccard_pairs.csv` | 31608 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/runs.csv` | 59336 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/sections.csv` | 5532 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/seed_scores_per_section.png` | 74810 | binary | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/summary.json` | 205188 | CHAT | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_a_released/variance.csv` | 965 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_b/sections.csv` | 3394 |  | yes |
| results (provisional) | `results/diagnostics/s3pl_seed_investigation_21/part_b/summary.json` | 205392 | CHAT | yes |

# Figures and tables inventory

### C107 Cache before/after figure
- Statement: `cache_before_after.png` shows the audited streaming-to-cached GBM108_positive speed-up with identical outputs.
- Numbers: 40,609→1,355 s uniform; about 30×.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/cache_before_after.png`; investigation 10.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: Current; one section/arms audit, not collection runtime.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C108 Window controls figure
- Statement: `01_window_controls.png` compares real 3×3, real 5×5, zero and shuffled context.
- Numbers: 7 confirmation sections/collection; seed 1.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/01_window_controls.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Current as descriptive evidence; older GBM budgets, not directly comparable with fair-scoring chart.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C109 Attention seed figure
- Statement: `02_attention_real_vs_shuffled_seeds.png` shows real-versus-shuffled attention over three seeds on 160TopL and GBM22_2.
- Numbers: 2 sections ×3 seeds.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/02_attention_real_vs_shuffled_seeds.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Development sections only; seed reporting should be rebuilt as mean ± SD.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C110 S3PL CAC controls figure and CSV
- Statement: `03_s3pl_cac_controls.png` and `.csv` show real, centre-tiled and frozen-context controls.
- Numbers: 8 CAC sections; two centre-tiled seeds.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/03_s3pl_cac_controls.png`; `.csv`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Headline predates Test N; needs rebuilding or caption correction to the final “mixed” topology result.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C111 Fair-scoring methods figure
- Statement: `04_fair_scoring_methods.png` is the headline comparison of IG, posterior correlation, simple rankings and oracle across datasets.
- Numbers: GBM, CAC and RCC means at K_bin.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/04_fair_scoring_methods.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Current concept; rebuild to include seed mean ± SD and explicit RCC n/caveat.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C112 IG-minus-correlation figure
- Statement: `05_ig_minus_correlation_by_section.png` shows paired section differences.
- Numbers: Seed-1 GBM/CAC and valid RCC section-arms.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/05_ig_minus_correlation_by_section.png`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Rebuild with three-seed means and dependent-unit annotation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C113 Attribution-count figure
- Statement: `06_gate_d_pixel_counts.png` shows n=12, 48 and 192 IG attribution samples on two development sections.
- Numbers: 2 sections ×2 arms ×3 counts.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/06_gate_d_pixel_counts.png`.
- Verified by supervisor: yes: 2026-10-10 09:45
- Caveats: Current; development-only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C114 Data-contract spot-check figure
- Statement: `07_data_contract_spotcheck_GBM22_2.png` visualises one coordinate/neighbour/mask audit.
- Numbers: One illustrated section; automated audit broader.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/07_data_contract_spotcheck_GBM22_2.png`.
- Verified by supervisor: yes: audit accepted before 2026-10-19 update
- Caveats: Illustration, not the full audit evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C115 GBM patient-grouped context figure
- Statement: `08_gbm_context_by_patient.png` groups paired context effects by PDX line.
- Numbers: 4 PDX lines ×2 sections.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/08_gbm_context_by_patient.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Current concept; ensure seed mean ± SD if used for Test R.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C116 Frozen swap figure
- Statement: `09_attention_frozen_shuffle_swap.png` shows frozen real-trained attention evaluated with replaced neighbours.
- Numbers: 16 sections.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/09_attention_frozen_shuffle_swap.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Mechanism/OOD diagnostic, not deployment evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C117 Changed-peaks ion images
- Statement: `10_changed_peaks_ion_images_GBM22_2.png` illustrates entering/leaving bins under the frozen neighbour swap.
- Numbers: One GBM development section.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/10_changed_peaks_ion_images_GBM22_2.png`.
- Verified by supervisor: no
- Caveats: Interpretive example; no molecular identity claim.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C118 Shuffle OOD figure
- Statement: `11_shuffle_is_out_of_distribution_GBM22_2.png` shows centre–context distribution shift under nonlocal shuffle.
- Numbers: 512 sampled centres in each of two development sections in the underlying audit.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/11_shuffle_is_out_of_distribution_GBM22_2.png`.
- Verified by supervisor: no
- Caveats: One illustrated section and two summary statistics.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C119 CAC S3PL-vs-IG threshold figure
- Statement: `12_cac_s3pl_vs_ig_by_threshold.png` locates the score gap by PCC threshold.
- Numbers: Thresholds 0.3–0.6; 8 sections.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/12_cac_s3pl_vs_ig_by_threshold.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Current diagnostic, not causal explanation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C120 CAC peak-overlap figure
- Statement: `13_cac_s3pl_vs_ig_peak_overlap.png` shows overlap between matched-count S3PL and IG lists.
- Numbers: About 79% selected m/z overlap.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/13_cac_s3pl_vs_ig_peak_overlap.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Peak identity overlap does not assign causality.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C121 S3PL GBM seed-stability figure
- Statement: `14_s3pl_gbm_seed_stability.png` shows the earlier three controlled initialisation seeds by section.
- Numbers: 8 sections ×3 controlled initialisation seeds.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/14_s3pl_gbm_seed_stability.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: SUPERSEDED for primary seed distribution by Investigation 21 released seeds 1–10; keep as controlled-initialisation evidence or rebuild.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C122 Runtime comparison figure
- Statement: `15_s3pl_vs_vae_runtime.png` shows three native-workflow repeats on 160TopL.
- Numbers: 3 repeats/method.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/15_s3pl_vs_vae_runtime.png`.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: Current only with one-section/hardware and unequal-work caption.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C123 BIC figure
- Statement: `16_bic_gmm_components.png` shows monotone BIC to K=6 and segmentation sensitivity.
- Numbers: K=1–6; four development section-arms.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/16_bic_gmm_components.png`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Caption must say “largest candidate,” not “six clusters”; RCC BIC not shown.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C124 All-neighbourhood-variants figure
- Statement: `17_all_neighbourhood_variants.png` compares attention, masked variants and 3×3–9×9 windows.
- Numbers: Final 16-section fair-scoring variants plus labelled exploratory arms.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/17_all_neighbourhood_variants.png`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Current seed-1 summary; labels/caveats must remain visible.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C125 S3PL training-length figure
- Statement: `18_s3pl_training_length.png` shows mSCF1 at epochs 10, 25, 50 and 100.
- Numbers: 16 sections; epoch 10 best in 15/16.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/18_s3pl_training_length.png`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Never select a different best checkpoint per section.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C126 Test S figure
- Statement: `19_test_s_spatial_segmentation.png` shows smoothed-versus-plain posterior-correlation effects.
- Numbers: 6 collection-arms; one incomplete.
- Label: four "equivalent", one "mixed", one "incomplete; no verdict"
- Source: `docs/meetings/2026-10-19_update/figures/19_test_s_spatial_segmentation.png`.
- Verified by supervisor: yes: 2026-10-17 08:37
- Caveats: Current seed-1 figure; segmentation accuracy and peak score should not be conflated.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C127 Baseline-reproduction figure
- Statement: `20_baseline_reproductions.png` compares legacy msiPL and S3PL reproductions with published values.
- Numbers: 3 datasets.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/20_baseline_reproductions.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Rebuild S3PL with ten-seed mean ± SD; current version predates Investigation 21.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C128 RCC ion-image figures
- Statement: `21_rcc_ion_images_MH0204_33.png` and `21_rcc_ion_images_UH0710_33.png` show example RCC ion images.
- Numbers: 2 of 8 runs.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/21_rcc_ion_images_MH0204_33.png`; `docs/meetings/2026-10-19_update/figures/21_rcc_ion_images_UH0710_33.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Examples only; no biological-identity claim.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C129 Segmentation-accuracy figure
- Statement: `22_segmentation_accuracy_vs_score.png` plots GMM balanced accuracy against posterior score/oracle gap.
- Numbers: 47 section-arms in descriptive analysis.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/figures/22_segmentation_accuracy_vs_score.png`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Association only; CAC saturation weakens its trend.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C130 VAE-vs-PCA figure
- Statement: `vae_vs_pca.png` shows paired PCA-5 versus VAE correlation-ranking differences.
- Numbers: 24 sections/runs.
- Label: GBM/CAC "mixed"; RCC "equivalent"
- Source: `docs/meetings/2026-10-19_update/figures/vae_vs_pca.png`.
- Verified by supervisor: yes: Test V result rulings
- Caveats: Rebuild with seed-mean descriptive result beside seed-1 verdict if space permits.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C131 S3PL real-vs-shuffled figure
- Statement: `s3pl_real_vs_shuffled.png` visualises Test N alongside centre-tiled context.
- Numbers: 8 CAC sections; 2 seeds.
- Label: "mixed"
- Source: `docs/meetings/2026-10-19_update/figures/s3pl_real_vs_shuffled.png`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Rebuild/report as seed mean ± SD; keep centre-tiled intervention distinct.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C132 Current-evidence legacy figures
- Statement: `figure_1_primary_peak_quality.png`, `figure_2_context_effect_by_section.png`, `figure_3_explanation_ablation.png`, `figure_4_seed_stability.png`, `figure_5_context_peak_overlap.png` and `figure_s1_s3pl_contextual_cac.png` are the earlier publication gallery.
- Numbers: 6 figures.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/`.
- Verified by supervisor: no
- Caveats: Mostly SUPERSEDED by fair-scoring/Test R/Investigation 21 figures; retain as history or appendix only after checking each caption.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C133 Fair-scoring evidence tables
- Statement: Current generated tables hold bin-level rows, approved-partition rows and collection summaries.
- Numbers: `fair_scoring_bin_level_sections.csv` 32 rows; files: `fair_scoring_collection_summary.csv`, `fair_scoring_partition_sections.csv`.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/README.md`; the three named CSVs.
- Verified by supervisor: yes: fair-scoring audits and 2026-10-20 statistics verification
- Caveats: Use seeds/arms explicitly; legacy P1 is collapse-only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C134 Runtime and training-curve tables
- Statement: Runtime v2 and training-curve CSVs are the table sources for computational and epoch results.
- Numbers: `runtime_all_sections_v2.csv`; `runtime_all_sections.csv` SUPERSEDED by v2; `training_curves_vae.csv`; `training_curves_s3pl.csv`.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/`.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: v2 is current; training curves are last-batch MSE for S3PL.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C135 Gate and S3PL-control tables
- Statement: Generated gate/control tables support attribution count, BIC and S3PL CAC results.
- Numbers: `gate_d_pixel_counts.csv`, `gate_d_bic.csv`, `s3pl_cac_controls.csv`, `s3pl_cac_seed_rule.json`.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/`.
- Verified by supervisor: yes: relevant 10–16 October rulings
- Caveats: S3PL controls table predates Test N; combine carefully with the newer decision table.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C136 Aggregate and section-result tables
- Statement: `aggregate_method_results.csv` and `section_level_results.csv` support the earlier seed-1 legacy/IG summary.
- Numbers: 6 aggregate method rows across GBM/CAC; section rows for both collections.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/`.
- Verified by supervisor: yes: primary-results audit
- Caveats: SUPERSEDED IN PART as headline by fair scoring and Test R; still valid for exact seed-1 package values.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C137 Section 6.6 statistics tables
- Statement: `tests.csv`, `mixed_models.csv`, `mann_whitney.csv` and `summary.json` are the current formal-statistics tables and provenance record.
- Numbers: 38 paired comparison rows; 9 mixed models; Mann–Whitney “not done.”
- Label: descriptive
- Source: `code/msi/results/diagnostics/statistics_6_6/`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Main report should use one table per family; PDX rows and full outputs belong in appendix.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C138 Proposed primary report tables
- Statement: Existing text tables suitable for rebuilding are the fair-scoring main table, reproduction table, Test S table, Test R IG−posterior table, runtime training/ranking tables and proposal-to-outcome table.
- Numbers: 6 logical table groups.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md`; `docs/meetings/2026-10-19_update/proposal_to_outcome.md`.
- Verified by supervisor: yes: report structure accepted 2026-10-20 10:25
- Caveats: Rebuild rather than copy when seed mean ± SD or final labels changed.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C139 Training-curves figure
- Statement: `training_curves.png` visualises saved VAE and S3PL training curves.
- Numbers: VAE 100 epochs; S3PL checkpoints through 100 epochs.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/training_curves.png`; accompanying CSVs.
- Verified by supervisor: yes: 2026-10-16 C1/C2 rulings
- Caveats: S3PL history is last-batch MSE; do not interpret it as epoch-mean loss or peak quality.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C140 Current draft patient-grouped figure and table
- Statement: `gbm_patient_grouped_effects.png` and `gbm_patient_summary.tex` are the current draft's patient-grouped GBM assets.
- Numbers: 4 PDX lines, 2 sections each.
- Label: descriptive
- Source: `report/draft/images/gbm_patient_grouped_effects.png`; `report/draft/tables/gbm_patient_summary.tex`.
- Verified by supervisor: no
- Caveats: Check against Test R seed-mean reporting and final statistics before reuse; rebuild if they show seed-1 only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

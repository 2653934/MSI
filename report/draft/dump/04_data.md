# Data

### C001 GBM collection and statistical unit
- Statement: GBM contains eight sections from four PDX lines (108, 12, 22 and 39), two sections per line; the inferential unit is the PDX line.
- Numbers: 8 sections; 4 PDX lines; 2 sections per line.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Do not describe eight sections as eight independent patients.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C002 CAC collection and statistical unit
- Statement: CAC contains eight sections from one biopsy; all section comparisons are within-specimen.
- Numbers: 8 sections; 1 biopsy.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: No patient-level p-value is supported.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C003 RCC collection and statistical unit
- Statement: RCC contains eight runs from eight subjects. The primary setup retains cancer, normal and unannotated pixels as three classes.
- Numbers: 8 runs; 8 subjects; 972–3,564 measured pixels/run; 10,200 bins over m/z 150–1000; unannotated 45–78% of pixels.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.1 item D; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.5.
- Verified by supervisor: yes: 2026-10-16 18:34 and 19:27
- Caveats: The source workflow treats unannotated pixels as background (`rcc_nobg`), but this was not independently verified; UH0505_12 and UH9905_18 contain heterogeneous tumour with large normal-looking areas per dataset documentation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C004 Development and confirmation split
- Statement: GBM108_positive, GBM22_2, 160TopL and 40TopL are development sections; confirmation summaries exclude them only where the original rule did.
- Numbers: 4 development sections: 2 GBM, 2 CAC.
- Label: descriptive
- Source: `CLAUDE.md`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 6–7; `code/msi/results/publication/current_evidence/README.md`.
- Verified by supervisor: yes: 2026-10-20 10:46
- Caveats: Several later predeclared rules deliberately use all eight sections.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C005 Spectral representation and preprocessing boundary
- Statement: Primary evaluation ranks raw spectral bins; consolidated molecular-peak views are interpretive. S3PL's released helper is not TIC normalisation.
- Numbers: VAE latent dimension 5; S3PL released settings 10 epochs and z=256, GBM p3 and CAC p9.
- Label: descriptive
- Source: `report/draft/planning/claim_map.md`; `docs/research/investigations/11 S3PL Architecture and Runtime Audit.md`; `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`.
- Verified by supervisor: yes: 2026-10-21 14:30, subject to the recorded settings correction
- Caveats: Investigation 21 Part D separately compares released `reference_spatial_max` with `paper_tic`.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C006 Matched bin budgets
- Statement: Fair scoring compares methods at a fixed section-specific K_bin. RCC uses the released S3PL `num_GT_peaks` target, approximately the project's |R@0.5| count.
- Numbers: Sensitivity budgets 0.5, 0.75, 1, 1.5 and 2 × K_bin.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 1–2 and 6.1; `docs/meetings/2026-10-19_update/descriptive_analyses/budget_sensitivity_means.csv`.
- Verified by supervisor: yes: 2026-10-16 19:47
- Caveats: The earlier |R@0.4| RCC budget is SUPERSEDED by this item.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C007 Superseded RCC budget
- Statement: SUPERSEDED: the first RCC pilot used |R@0.4|. Current results use the released target / |R@0.5| budget in C006.
- Numbers: Superseded |R@0.4|; replacement |R@0.5|/released target.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.1 and Section 10; supervisor chat 2026-10-16 19:47.
- Verified by supervisor: yes: 2026-10-16 19:47
- Caveats: The first pilot remains provenance only; replacement ID C006.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C008 P1 peak partition
- Statement: P1 collapses neighbouring bins within a mean-spectrum basin. GBM has substantive groups; CAC P1 is singleton groups and RCC P1 is a budget sensitivity rather than a verdict scale.
- Numbers: CAC 1,481 groups for 1,481 bins; RCC bin spacing ≈0.083 Da exceeds the merge threshold.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 3, 6.1, 7.1 and 10; supervisor chat 2026-10-17 08:37.
- Verified by supervisor: yes: 2026-10-17 08:37
- Caveats: Legacy msiPL is not K_peak-matched; its collapsed result is diagnostic only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C009 Class-informed GMM count
- Statement: Training and ranking are label-free, but production GMM K equals the number of annotated classes.
- Numbers: K=2 GBM; K=3 CAC; K=3 RCC.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 4 and 6.1; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.5.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: The system is not fully autonomous; BIC did not validate these values (C067).
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

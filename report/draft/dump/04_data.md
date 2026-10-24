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

### C221 GBM and CAC budget provenance
- Statement: The shared bin budget is each section's tuned legacy msiPL `unique_nearest_bins` count. GBM released S3PL targets equal the project's mixed PCC 0.4 reference-set size in every section, whereas CAC released targets match none of the project's four reference-set sizes; the targets' upstream derivation remains unverified.
- Numbers: GBM 8/8 matches at PCC 0.4; CAC 0/8 matches at PCC 0.3, 0.4, 0.5 or 0.6; legacy tuning tolerance 50 bins.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 0; `code/msi/baselines/s3pl/data_configs.py`.
- Verified by supervisor: yes: protocol 18 v3, 2026-10-09
- Caveats: GBM equality suggests but does not prove mask-derived upstream targets. Never describe CAC released targets as mask-derived. RCC has the separate released-target convention in C006.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C222 Measured-coordinate and mask validation
- Statement: The GBM HDF5 and official imzML packages have matching measured-coordinate sets in all sections after translating their different mask encodings. Unmeasured grid locations must remain outside the biological classes; CAC 280TopL also requires coordinate-based alignment because its mask grid has unmeasured locations.
- Numbers: GBM 8/8 sections matched semantically; CAC 280TopL has 4,160 measured spectra and 89.98% grid coverage.
- Label: descriptive
- Source: `docs/research/03 Datasets and Preprocessing.md`; `code/msi/results/validation/gbm_imzml_h5/comparison.json`.
- Verified by supervisor: no
- Caveats: The GBM source masks are not byte-identical because official imzML uses 0=background, 1=normal, 2=tumour while the HDF5 reconstruction uses coverage plus 0=normal, 1=tumour. This is an encoding difference, not a numerical conflict.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C234 CAC acquisition citation remains unverified
- Statement: The references tracker identifies S3PL as the released source for the CAC collection but leaves the original acquisition paper unconfirmed. A final dataset-provenance sentence should distinguish the release used here from an original acquisition citation once verified.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md` Sections 5–6; `docs/research/investigations/19 Upstream Repository and Paper Audit.md`.
- Verified by supervisor: no
- Caveats: Open bibliographic check, not evidence that the CAC dataset lacks an original citation. Do not invent a source citation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

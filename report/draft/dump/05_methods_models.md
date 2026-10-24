# Methods and models

### C010 VAE–GMM–ranking pipeline
- Statement: A section-specific dense VAE produces latent means, a GMM segments them, and a ranking selects K_bin bins for mSCF1 evaluation.
- Numbers: 100 VAE epochs; 5 latent dimensions; GMM K from C009.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 1–2; `docs/research/investigations/11 S3PL Architecture and Runtime Audit.md`.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Per-section transductive evaluation; labels enter scoring and configuration, not fitting/ranking.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C011 Core VAE arms
- Statement: Centre-only encodes one spectrum; uniform-mean concatenates it with the mean of up to eight measured 3×3 neighbours. Both reconstruct the centre.
- Numbers: D=85,062 example: centre 87,199,312 parameters; uniform 130,751,056; hidden 512; latent 5.
- Label: descriptive
- Source: `docs/research/investigations/11 S3PL Architecture and Runtime Audit.md`.
- Verified by supervisor: no
- Caveats: The contextual arm tests fixed local input, not every spatial architecture.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C012 Attention and masked controls
- Statement: Attention learns neighbour weights; G1 hides the centre for half of training samples, G2 is masked uniform mean, and G3 compares real with shuffled neighbours on two exploratory sections.
- Numbers: 50% centre masking; attention adds about 0.5% parameters (+680,504 GBM; +11,856 CAC); G3 n=2.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.1 item G; `docs/research/investigations/13 Spatial Context Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-15 15:35 and 2026-10-16 17:36
- Caveats: The corrected input scaling was in place before final runs; G3 is exploratory.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C013 Integrated Gradients ranking
- Statement: IG ranks bins by gradients of a fitted GMM component posterior with respect to the spectrum and balances selections across components.
- Numbers: Production 12 sampled pixels/component, 64 IG steps and one baseline; gate (d) tests 48 and 192 pixels.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 4, 6 and 7.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Conclusions are about this tested IG configuration.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C014 Posterior-correlation ranking
- Statement: The no-IG control ranks each bin by absolute Pearson correlation between its ion image and each GMM posterior map, then interleaves components like IG.
- Numbers: Same GMM and K_bin as the paired IG result.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 4; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.1.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Segment-then-correlate is established practice and metric-aligned; this is an ablation, not a novel recommended detector.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C015 Simple rankings and oracle
- Statement: Mean intensity, variance and Moran's I are model-free rankings; random is a chance reference; expert-mask correlation is a supervised oracle ceiling.
- Numbers: All evaluated at the same K_bin.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 4; `code/msi/results/publication/current_evidence/fair_scoring_bin_level_sections.csv`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: The oracle is not deployable.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C016 Spatial segmentation Test S
- Statement: Test S smooths saved latent representations with Cardinal-compatible structure-adaptive weights before GMM fitting and posterior-correlation ranking.
- Numbers: 24 sections/runs; 2 VAE arms; seed 1.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.2; `docs/research/investigations/20 Has Spatial Context Been Ruled Out.md`.
- Verified by supervisor: yes: 2026-10-17 08:37
- Caveats: One segmentation smoother; graph and ion-image methods remain untested.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C017 PCA segmentation Test V
- Statement: Test V replaces the VAE representation with PCA while retaining GMM and posterior correlation, isolating the nonlinear encoder.
- Numbers: PCA-5 primary; PCA-20 descriptive; all 24 sections/runs.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.4; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.8.
- Verified by supervisor: yes: Test V result rulings on 17–18 October
- Caveats: PCA and VAE optimise different objectives.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C018 S3PL baseline
- Statement: S3PL applies a learned 3D convolution over a patch, multiplicative attention on the centre and a transposed convolution to reconstruct the whole normalised patch; its selector aggregates per-pixel top attention bins.
- Numbers: p3: 470 trainable parameters at D=85,062; Adam 1e-2; batch 16; 10 epochs.
- Label: descriptive
- Source: `docs/research/investigations/11 S3PL Architecture and Runtime Audit.md`; `docs/research/investigations/19 Upstream Repository and Paper Audit.md`.
- Verified by supervisor: yes: baseline reproduction reviewed in 2026-10-19 update
- Caveats: It differs from the VAE in architecture, objective, normalisation, epochs and selector.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C019 Legacy msiPL baseline
- Statement: Legacy msiPL is reproduced and budget-tuned as in the source work, then retained as a fixed list in fair scoring.
- Numbers: Dense model about 87 million parameters; 100 epochs.
- Label: descriptive
- Source: `docs/research/investigations/11 S3PL Architecture and Runtime Audit.md`; `docs/research/investigations/19 Upstream Repository and Paper Audit.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Not K_peak-matched; peak-level use is a collapse diagnostic.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C020 mSCF1 outcome
- Statement: mSCF1 measures spatial agreement between selected-bin ion images and expert class masks over PCC thresholds; it is not chemical-identification accuracy.
- Numbers: PCC thresholds 0.3, 0.4, 0.5 and 0.6.
- Label: descriptive
- Source: `docs/research/investigations/12 CAC S3PL Gap Diagnostics.md`; `report/draft/planning/claim_map.md`; `proposal/`.
- Verified by supervisor: yes: bounded wording accepted 2026-10-20 10:25
- Caveats: Do not call selected bins biomarkers or biological identities.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT
### C225 IG path, baseline and aggregation
- Statement: Production IG integrates the assigned GMM-component posterior along a trapezoidal path from the section-wide mean TIC-normalised spectrum to each sampled centre and valid neighbour, then ranks bins by mean absolute attribution across central and context paths. The current draft's trapezoidal equation is the implemented rule.
- Numbers: 64 trapezoidal intervals including both endpoints; 12 sampled pixels per component in production.
- Label: descriptive
- Source: `code/msi/src/spatial_msipl/attribution.py`; `code/msi/scripts/run_spatial_msipl_gmm_integrated_gradients.py`; `code/msi/src/spatial_msipl/tests/test_attribution_analytic_reference.py`; `report/draft/sections/methodology.tex`.
- Verified by supervisor: yes: `docs/research/17 Supervisor Review Response and Report Completion Plan.md` (2026-10-08), formula correction
- Caveats: Missing neighbour slots stay masked and zero. The older right-endpoint equation in `report/draft/previous_version/sections/methodology.tex` is SUPERSEDED by the current methodology and this item; the analytic test validates a synthetic reference, not every real attribution.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C226 Threshold-derived mSCF1 reference rule
- Statement: The S3PL-compatible reference set uses the nearest position in each class's ranked PCC list as a threshold-derived rank cutoff and unions the selected class lists; it is not always a literal binwise PCC-above-threshold filter.
- Numbers: Four PCC thresholds: 0.3, 0.4, 0.5 and 0.6.
- Label: descriptive
- Source: `code/msi/baselines/s3pl/utils/PeakEvaluation.py`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 2 and 3.3; `report/draft/sections/methodology.tex`.
- Verified by supervisor: yes: `docs/research/17 Supervisor Review Response and Report Completion Plan.md` (2026-10-08), scoring-description correction
- Caveats: A description of the reference as literal r ≥ threshold in older report material is SUPERSEDED by this item. This is a scoring definition, not an independent biological ground truth.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C227 Audited peak-group scoring contract
- Statement: Peak-level scoring requires a label-free structural audit and reviewer-approved partition hashes before scores can be produced. A reference group is positive only when its apex is reference-positive, whereas a predicted group is selected when any of its bins is selected.
- Numbers: P1 hard gap 50 ppm, shallow-basin merge below 5% with at most 100 ppm merged width; S1 rejects a partition if any group width reaches 0.5 Da in any section.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 3.1–3.3; `code/msi/src/spatial_msipl/tests/test_peak_groups.py`; `code/msi/src/spatial_msipl/tests/test_fair_scoring_pipeline.py`.
- Verified by supervisor: yes: protocol 18 v3.1, 2026-10-09
- Caveats: S2 large-group size is descriptive and S3 singleton fraction informational; only S1 is a rejection rule. The audit prevents unreviewed grouping, but does not detect over-splitting (C008).
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

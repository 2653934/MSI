# Results: segmentation and encoder

### C064 Test V primary outcome
- Statement: PCA-5→GMM→correlation is mixed on GBM and CAC and equivalent on RCC versus the VAE pipeline; the nonlinear encoder is therefore not shown necessary.
- Numbers: Seed-1 PCA−VAE: GBM +0.023, 5/8; CAC −0.013, 4/8; RCC approximately equivalent. Three-seed descriptive VAE−PCA: GBM +0.042 5/8; CAC −0.012/−0.023 2/8; RCC −0.011 3/7.
- Label: GBM "mixed"; CAC "mixed"; RCC "equivalent"
- Source: protocol 18 Section 6.4; `code/msi/results/diagnostics/segmentation_control_V/decisions_20261017_local/`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 6.8–6.9.
- Verified by supervisor: yes: 17–18 October result rulings
- Caveats: Seed-1 verdict is primary; seed-mean result is descriptive.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C065 Segmentation accuracy
- Statement: VAE segmentations can agree better with expert masks without reliably producing better correlation-ranked peaks than PCA-5.
- Numbers: Test R GMM balanced accuracy examples, VAE centre: GBM seeds 1/2/3 0.868/0.957/0.931; RCC 0.771/0.621/0.768.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.6, 6.8 and 6.9.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Mask agreement is post-training evaluation, not a training target.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C066 PCA reconstruction addendum
- Statement: Reconstruction error does not separate PCA-5 from the VAE in a way that explains ranking quality.
- Numbers: PCA-5 lower MSE in 8/8 GBM sections; slightly higher MSE in 7/8 CAC sections.
- Label: "Reconstruction error does not separate PCA-5 from the VAE."
- Source: protocol 18 Section 6.4 addendum; `code/msi/results/diagnostics/pca_reconstruction_V/summary_local/`; supervisor chat 2026-10-20 10:35.
- Verified by supervisor: yes: 2026-10-20 10:35
- Caveats: Different reconstruction objectives; descriptive addendum.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C067 BIC component-count result
- Statement: BIC does not support production K; it selects the largest candidate in every tested development section-arm, with no interior minimum.
- Numbers: K=6 selected in 4/4 GBM/CAC section-arms and all RCC runs; candidates K=1–6.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/gate_d_bic.csv`; protocol 18 Sections 6 and 10; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.5.
- Verified by supervisor: yes: 2026-10-15 and 2026-10-16 17:36
- Caveats: Required wording: “largest candidate,” never “six clusters.” BIC offers no label-free replacement K within the tested range.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C068 BIC-K sensitivity
- Statement: A finer K=6 segmentation substantially reduces posterior-correlation score on GBM108_positive but barely changes 40TopL.
- Numbers: GBM drop about 0.30 in both arms (0.69–0.70 to 0.39–0.41); CAC +0.001 and −0.021.
- Label: "BIC-K segmentation sensitivity, descriptive"
- Source: `code/msi/results/publication/current_evidence/gate_d_bic.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.5.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Development sections; no IG rerun; does not alter the paired IG-versus-posterior comparison at fixed K.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT
### C223 Saved latent information versus GMM agreement
- Statement: On two exploratory sections, expert-class information can be accessible in frozen real- and shuffled-context latents even when the saved unsupervised GMM partitions them differently. This separates representation content from the particular clusterer's post-hoc mask agreement.
- Numbers: GBM22_2 real/shuffled GMM class ARI 0.165/0.888, while both label-trained linear probes were about 0.985 balanced accuracy and ten-neighbour purity about 0.978; 160TopL GMM ARI 0.474/0.383, probe 0.752/0.747 and purity 0.760/0.762 (n=2 sections).
- Label: descriptive
- Source: `docs/research/01 Results Record.md` subsection “Saved latent information versus the fitted GMM”; `code/msi/results/diagnostics/spatial_latent_separability/GBM22_2.json`; `code/msi/results/diagnostics/spatial_latent_separability/160TopL.json`.
- Verified by supervisor: no
- Caveats: The probe uses labels and random pixel folds within each training section, so it is neither unsupervised nor patient-independent validation; the sections were outcome-known.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C224 Clusterer-selection caution
- Statement: A tied-covariance GMM on frozen GBM22_2 real-context latents yields much higher post-hoc class ARI than the saved full-covariance GMM, despite worse label-free BIC. Selecting it because of mask agreement would be label-guided method selection.
- Numbers: GBM22_2 class ARI 0.899 tied covariance versus 0.165 saved full covariance (n=1 exploratory section).
- Label: descriptive
- Source: `docs/research/01 Results Record.md` subsection “Saved latent information versus the fitted GMM”; `code/msi/results/diagnostics/spatial_unsupervised_clusterers/GBM22_2.json`.
- Verified by supervisor: no
- Caveats: Frozen-latent diagnostic only; no alternative clusterer was promoted into fair scoring, and this does not overturn the production GMM comparison.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

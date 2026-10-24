# Conclusion and future work

### C203 Conclusion: ranking
- Statement: In the tested partly class-informed pipeline, direct correlation with GMM posterior maps outperformed tested GMM-targeted IG, with formal support across all collection-arm comparisons.
- Numbers: 47/47 seed-1; 136/140 across seeds; F1 Holm p≤0.047.
- Label: "statistically supported"
- Source: items C044–C046; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Ablation finding under mSCF1, not a novel universal detector.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C204 Conclusion: spatial context
- Statement: The tested local-context and segmentation-smoothing interventions did not provide a consistent spatially specific gain across datasets.
- Numbers: Attention equivalent; larger windows never help; Test S never helps; Test N mixed.
- Label: descriptive
- Source: items C055–C063 and C072; investigation 20.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Does not rule out spatial information or untested spatial architectures.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C205 Conclusion: encoder
- Statement: Segment-then-correlate is useful under this evaluation, but PCA-5 controls do not establish that the VAE is necessary.
- Numbers: Test V mixed GBM/CAC, equivalent RCC.
- Label: descriptive
- Source: C064–C068.
- Verified by supervisor: yes: Test V rulings
- Caveats: Class-informed K remains a major limitation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C206 Conclusion: reproducibility boundary
- Statement: Learned-baseline reproductions constrain general claims: msiPL is close on all datasets, S3PL is close on CAC/RCC but its GBM paper result remains outside the ten-seed distribution.
- Numbers: GBM S3PL 0.3193 ± 0.0419 vs 0.496.
- Label: "outside our seed distribution"
- Source: C039–C043 and C074–C077.
- Verified by supervisor: yes: 2026-10-20 20:57
- Caveats: Unresolved rather than attributed to one cause.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C207 Future work: label-free configuration and validation
- Statement: Future work should select K and budgets without annotation-derived settings, validate on additional subjects/datasets and assess chemical identity separately from spatial-mask agreement.
- Numbers: Current K=2/3/3; current datasets 4 PDX lines, 1 biopsy, 8 RCC subjects.
- Label: descriptive
- Source: protocol 18; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Discussion.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Proposed future work, not completed evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C208 Future work: spatial and attribution models
- Statement: Predeclared future tests could examine graph-based encoders, ion-image-level learning, HMRF/edge-preserving segmentation, local Moran statistics, ranking fusion and alternative IG baselines/aggregation.
- Numbers: No new runs in current study.
- Label: descriptive
- Source: `docs/research/investigations/20 Has Spatial Context Been Ruled Out.md`; `docs/meetings/references.md` Section 2b.
- Verified by supervisor: yes: investigation 20 accepted
- Caveats: Rank fusion and other post-hoc ideas need fresh predeclaration.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

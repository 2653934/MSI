# Results: simple baselines and metric alignment

### C051 Dataset-specific strongest label-free ranking
- Statement: Among the predeclared rankings (balanced posterior correlation, Moran's I, mean intensity and variance; oracle as ceiling), the strongest label-free ranking varies by dataset: posterior correlation on GBM, mean intensity on CAC (balanced correlation, Moran's I and variance within 0.02), and Moran's I on RCC.
- Numbers: GBM posterior 0.743–0.744, Moran 0.684, oracle 0.809; CAC mean 0.612, posterior 0.606–0.607, Moran 0.605, variance 0.593, oracle 0.654; RCC Moran 0.63–0.64, posterior 0.57–0.60, oracle 0.76.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/fair_scoring_collection_summary.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.1 and 6.5.
- Verified by supervisor: yes: 2026-10-19 update and 2026-10-20 11:31
- Caveats: Values are collection means at K_bin; RCC uniform has seven valid IG runs but non-IG rankings cover the specified roots. A non-predeclared max-aggregation variant (posterior_abs_pcc_max) scores 0.626–0.629; it was not part of the predeclared comparison and is reported descriptively only (appendix, not headline).
- Corrected: 2026-10-24 per supervisor ruling 2026-10-24 19:12 (restricted to predeclared rankings)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C052 CAC saturation and budget sensitivity
- Statement: CAC methods are close at K_bin and converge near 0.41 at 2× budget, including the oracle; its oracle is higher at half-budget than at K_bin.
- Numbers: At 0.5×: Moran 0.62, mean 0.60, posterior 0.56, oracle 0.74; at K_bin oracle 0.65; at 2× all about 0.41.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/descriptive_analyses/budget_sensitivity_means.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.6.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: CAC differences at the chosen budget carry limited discriminative information.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C053 Segmentation–metric alignment
- Statement: Better GMM balanced accuracy tracks a posterior-correlation score closer to the oracle on GBM and RCC; relationships are weak on saturated CAC.
- Numbers: Balanced accuracy vs posterior Spearman: GBM 0.77, RCC 0.80, CAC 0.24; vs gap to oracle: −0.90, −0.84, −0.27.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/descriptive_analyses/segmentation_vs_score.json`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.6.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Association does not show that the VAE is necessary; mSCF1 structurally rewards mask-aligned segmentations.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C054 Duplicate bins and peak collapse
- Statement: P1 removes duplicate credit without changing the main method ordering on GBM.
- Numbers: No number: duplicate bins of one peak inflate bin-level true positives, which motivates P1. The earlier "20–25%" did not reproduce from the saved partition summaries.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.4; protocol 18 Sections 3 and 7.
- Verified by supervisor: yes: fair-scoring rulings on 9–10 October
- Caveats: CAC P1 is singleton grouping and RCC P1 is budget sensitivity, not independent peak confirmation.
- Corrected: 2026-10-24 per supervisor ruling 2026-10-24 19:12 (20–25% not reproduced; number dropped)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

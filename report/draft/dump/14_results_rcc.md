# Results: RCC

### C078 Three-class RCC main table
- Statement: In three-class RCC, posterior correlation beats IG in every valid seed-1 run, while Moran's I is the strongest label-free ranking.
- Numbers: Centre/uniform means: IG 0.41/0.41; posterior 0.57/0.60; Moran 0.63/0.64; oracle 0.76/0.76; random 0.17/0.17.
- Label: centre rule fall-through; uniform "incomplete; no verdict"
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.5; `code/msi/results/diagnostics/fair_scoring_baselines/rcc/decisions_20261017_local/`.
- Verified by supervisor: yes: 2026-10-17 verdict amendment
- Caveats: Centre 8/8; uniform 7/7 valid because UH0505_12 failed IG completeness. RCC verdict is bin-level only. Centre label in Section 7.1 wording: "Neither predeclared verdict applies, because IG scored below posterior-|PCC| in every section." Unannotated class, 45–78% of pixels; the dataset's own Cardinal workflow treats these pixels as background (`rcc_nobg`), but this was not independently verified. GMM K=3 equals the number of label classes: label-free in training and ranking, class-informed in its component count.
- Corrected: 2026-10-24 per VERIFICATION.md (RCC NA caveat, K=3 note and Section 7.1 wording)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C079 RCC IG versus posterior
- Statement: IG is below posterior correlation by a large margin in the three-class primary analysis.
- Numbers: Centre −0.156, 0/8 positive; uniform −0.185, 0/7; three-seed descriptive mixed-model centre −0.1437 [−0.1722, −0.1152].
- Label: centre "mixed / not resolved by the predeclared rule"; uniform "incomplete; no verdict"
- Source: `docs/meetings/2026-10-19_update/descriptive_analyses/paired_differences.csv`; `code/msi/results/diagnostics/statistics_6_6/mixed_models.csv`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Three-class result is sensitive to the unannotated region (C082).
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C080 RCC baselines and reproductions
- Statement: RCC S3PL and legacy msiPL reproduce their published means approximately, but legacy is a weak, unmatched-count reference.
- Numbers: S3PL ours 0.41–0.44 vs 0.47; legacy 0.157 vs 0.16, 8/8 runs; legacy missed count target in 6/8.
- Label: descriptive
- Source: protocol 18 Section 10; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 6.5–6.6.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Native protocols/evaluators; legacy not at the fair-scoring budget.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C081 RCC context and seeds
- Statement: Three-seed uniform-versus-centre inference is incomplete; Moran's I remains above correlation at every seed in both arms.
- Numbers: Uniform−centre over six complete sections +0.026, 5/6, descriptive; Moran−correlation +0.039 to +0.108 across seeds/arms.
- Label: "incomplete"
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.9; Test R decision tables.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Missing IG seed-arms prevent the predeclared context verdict. Unannotated class, 45–78% of pixels; the dataset's own Cardinal workflow treats these pixels as background (`rcc_nobg`), but this was not independently verified. GMM K=3 is class-informed in its component count.
- Corrected: 2026-10-24 per VERIFICATION.md (RCC NA caveat and K=3 note)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C082 Cancer/normal sensitivity
- Statement: Removing the dominant unannotated class shrinks the posterior-correlation advantage. In central_only, correlation beats IG in five of eight runs and falls below mean intensity, variance and Moran's I; in uniform_mean (7 runs) correlation beats IG in six of seven and stays above mean intensity, below variance and Moran's I.
- Numbers: central_only IG−posterior about −0.045, IG ahead 3/8, posterior ahead 5/8 (posterior 0.380 vs mean intensity 0.397, variance 0.444, Moran 0.443); uniform_mean −0.077, IG ahead 1/7 (posterior 0.427 vs mean intensity 0.414, variance 0.444, Moran 0.439); unannotated 45–78% of pixels.
- Label: descriptive
- Source: `code/msi/results/diagnostics/fair_scoring_baselines/rcc_cancer_normal_sensitivity/decisions_20261017_local/`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.5.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Necessary qualifier to every RCC headline; cancer/normal subset follows the dataset subset definition.
- Corrected: 2026-10-24 per VERIFICATION.md (statement held for central_only only; uniform_mean added)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C083 RCC BIC and P1 status
- Statement: RCC BIC selects K=6 everywhere, and RCC P1 is a budget sensitivity rather than an independent partition verdict.
- Numbers: 15/15 RCC run-arms (8/8 central_only, 7/7 uniform_mean; UH0505_12 uniform_mean not done) select the largest candidate K=6, with no minimum within the predeclared range; bin spacing ≈0.083 Da.
- Label: descriptive
- Source: protocol 18 Sections 6.1 and 10; `code/msi/results/diagnostics/gate_d_bic_rcc/`.
- Verified by supervisor: yes: 2026-10-17 verdict amendment
- Caveats: Current RCC decision tables are `decisions_20261017_local`; `decisions_20261016_local` is SUPERSEDED, with unchanged values but obsolete P1 interpretation.
- Corrected: 2026-10-24 per VERIFICATION.md (15/15 run-arms; BIC wording rule)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

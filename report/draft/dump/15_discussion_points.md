# Discussion points, limitations and likely objections

### C084 Bounded contribution
- Statement: The defensible contribution is a controlled empirical evaluation of spatial context, segmentation, peak ranking and evaluation choices, not a fully autonomous detector or general superiority over S3PL.
- Numbers: 3 datasets; 24 sections/runs; multiple predeclared controls.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/meeting_summary.md`; supervisor chat 2026-10-20 10:25.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Original research questions remain visible through the proposal-to-outcome account.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C085 Why correlation wins here
- Statement: Posterior correlation directly measures the section-wide co-localisation that mSCF1 rewards, whereas tested IG integrates local gradients along one baseline path for sampled pixels.
- Numbers: 47/47 seed-1 and 136/140 three-seed valid comparisons favour correlation.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.3 and 7; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Plausible metric-alignment explanation, not proof IG is generally ineffective.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C086 What remains of the spatial hypothesis
- Statement: Tested dense-VAE neighbourhood inputs and segmentation smoothing did not yield a consistent spatially specific gain, while Moran's I and S3PL's neighbour dependence show that spatial structure can still be informative.
- Numbers: Test S never “helps”; Test N real−shuffled about +0.04 and “mixed”; Moran's I is strongest on RCC.
- Label: descriptive
- Source: `docs/research/investigations/20 Has Spatial Context Been Ruled Out.md`; `docs/meetings/2026-10-19_update/meeting_summary.md`.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Do not claim spatial information has no value in MSI; graph and ion-image models remain future work.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C087 Reconstruction is not ranking quality
- Statement: Better reconstruction does not reliably imply better peak ranking, and the PCA addendum does not separate PCA-5 from the VAE in the needed direction.
- Numbers: PCA-5 reconstructs better in 8/8 GBM and slightly worse in 7/8 CAC; Test V is mixed/equivalent.
- Label: "Reconstruction error does not separate PCA-5 from the VAE."
- Source: protocol 18 Section 6.4 addendum; supervisor chat 2026-10-20 10:35.
- Verified by supervisor: yes: 2026-10-20 10:35
- Caveats: Different objectives and model capacities.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C088 Metric-alignment limitation
- Statement: mSCF1 measures mask agreement, so a segmentation-correlated ranking is advantaged when its GMM resembles the expert masks; this supports an ablation interpretation, not biological discovery.
- Numbers: Segmentation accuracy vs oracle gap Spearman −0.90 GBM and −0.84 RCC.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.3 and 4.6.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Scores are not molecular identification or biomarker validation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C089 Class-informed and post-hoc choices
- Statement: GMM K and budgets are class-informed, and posterior correlation was introduced as a control after the original proposal; the report must disclose both.
- Numbers: K=2 GBM and K=3 CAC/RCC; BIC selects boundary K=6.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.3 and 4.5; `report/draft/planning/claim_map.md`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Do not market posterior correlation as a newly validated autonomous method.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C090 Small and clustered samples
- Statement: GBM contains four PDX lines, CAC one biopsy and RCC eight subjects; sections and seeds are dependent repeats, not new patients.
- Numbers: n=4 GBM PDX lines; 1 CAC biopsy; 8 RCC subjects.
- Label: descriptive
- Source: protocol 18 Section 6.6; `report/draft/planning/claim_map.md`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: P-values describe these observed units; generalisation is limited.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C091 RCC unannotated-class objection
- Statement: The three-class RCC headline is qualified by a cancer/normal-only sensitivity in which the ranking advantage shrinks and simple baselines lead.
- Numbers: Unannotated 45–78%; correlation beats IG 5/8 after removal, gap about −0.045.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.5; protocol 18 Section 6.1.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: The background interpretation comes from dataset documentation and was not independently verified.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C092 Why not compare VAE at ten epochs
- Statement: A 10-epoch VAE ranking endpoint was not scored, and matching epoch counts would not match compute or learning objectives.
- Numbers: VAE 100 epochs; S3PL 10; future comparison should use measured time/compute budgets.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/meeting_walkthrough.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.4.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Do not imply 100 epochs versus 10 is an equal-work architecture comparison.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C093 Did more IG sampling rescue IG
- Statement: No tested pixel-count increase rescued IG under the promotion rule, but untested IG formulations remain outside scope.
- Numbers: Best n=192 changes +0.017 GBM and +0.024 CAC; rule required +0.02 on both.
- Label: predeclared rule not met
- Source: protocol 18 Section 6; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.2.
- Verified by supervisor: yes: 2026-10-10 09:45
- Caveats: Two development sections, one attribution formulation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C094 S3PL instability objection
- Statement: The unreproduced GBM score cannot be dismissed as one unlucky seed: ten released seeds and exact best-of-k analysis do not reach the paper mean; controlled runs identify initialisation as the main source on selected sections.
- Numbers: GBM 0.3193 ± 0.0419, maximum seed mean 0.3735, best-of-10 0.4343 vs 0.496; init dominant 2/3 sections.
- Label: "outside our seed distribution"; "not explained by seed selection alone"; "initialisation dominant"
- Source: `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`.
- Verified by supervisor: yes: 2026-10-20 20:57 and 2026-10-21 14:21
- Caveats: Does not identify every source of the paper gap; supplements unavailable and tuned-on-test hyperparameters remain a discussion point.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

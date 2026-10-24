# Problem, research questions and proposal-to-outcome

### C191 Original RQ1
- Statement: How can local spatial covariance be integrated into a 1D VAE without the computational and memory overhead of 3D convolution?
- Numbers: Proposed centre plus 8-pixel Moore neighbourhood.
- Label: descriptive
- Source: `proposal/proposal.tex` Research Questions; proposal-to-outcome row 1.
- Verified by supervisor: yes: proposal-to-outcome accepted 2026-10-20 10:25
- Caveats: Answer is an implemented lightweight contextual vector, not a proven efficiency advantage.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C192 Original RQ2
- Statement: To what extent do an explicit spatial-coherence penalty and physical noise augmentation isolate spatial signals relative to spatially blind baselines?
- Numbers: Penalty λ tested at 0, 0.01, 0.1 and 1; noisy-input gain about 0.022%, below 1% gate.
- Label: descriptive
- Source: `proposal/proposal.tex`; `docs/meetings/2026-10-19_update/proposal_to_outcome.md` rows 2–4.
- Verified by supervisor: yes: proposal-to-outcome accepted 2026-10-20 10:25
- Caveats: Each component failed its gate; their combination was not tested, so the combined question remains unanswered.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C193 Original RQ3
- Statement: To what extent does the spatially regularised framework improve spatially structured peak selection over spatially blind msiPL?
- Numbers: Pipeline beats legacy 8/8 in both arms/collections, but neighbourhood contribution is mixed and simple baselines weaken the headline.
- Label: descriptive
- Source: `proposal/proposal.tex`; proposal-to-outcome rows 1, 7 and 10.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Rewrite “biologically relevant” as measured mask agreement.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C194 Revised report questions
- Statement: The report separates three questions: whether the label-free pipeline beats legacy msiPL, which component carries the improvement, and whether neighbourhood context helps.
- Numbers: 3 report questions.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 1.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Present as refinement of the original questions, not the plan all along.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C195 Spatial penalty outcome
- Statement: The penalty reduced neighbour latent distance but worsened reconstruction and did not consistently improve the development probe; it was not retained.
- Numbers: λ=0, 0.01, 0.1, 1.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 2.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Only the tested range is ruled out; no global optimisation claim.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C196 Poisson augmentation outcome
- Statement: Poisson augmentation passed clean reconstruction but failed the predeclared noisy-input improvement gate.
- Numbers: Observed gain about 0.022% vs required ≥1%.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 3.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Interaction with the spatial penalty remains untested.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C197 Bayesian optimisation outcome
- Statement: Bayesian optimisation was omitted because no penalty formulation passed the development gate.
- Numbers: 0 optimisation runs.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 5.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Cannot claim the penalty was globally optimised.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C198 Peak-extraction change
- Statement: First-layer L2 weight analysis was retained as a comparator, while GMM-targeted IG replaced it as the nonlinear ranking on 12 September.
- Numbers: Early GBM comparator about 0.21 L2 vs 0.46 pipeline mSCF1.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` rows 6–7.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Posterior correlation later outperformed IG; do not present IG as an original immutable plan.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C199 Baseline delivery
- Statement: msiPL and S3PL were reproduced and audited; MALDIquant was omitted; model-free baselines, random and oracle were added.
- Numbers: 3 datasets for learned baselines; 0 MALDIquant runs.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 8.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: No superiority claim over classical peak picking generally.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C200 Data-plan change
- Statement: Practical audited HDF5 paths replaced an all-raw-imzML plan where needed, and RCC was added as a third dataset.
- Numbers: GBM two-section imzML pilot matched HDF5; CAC imzML→HDF5 adapters audited; RCC added 16 Oct.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 9.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Keep format and dataset-lineage disclosures.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C201 Evaluation strengthened
- Statement: The proposed mSCF1 evaluation was delivered and extended with matched budgets, P1, simple baselines, oracle, predeclared rules and provenance checks.
- Numbers: 4 PCC thresholds; 5 budget multipliers; 38 formal paired comparisons.
- Label: descriptive
- Source: proposal-to-outcome row 10; protocol 18 Sections 1–10.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Budgets/class count are partly class-informed.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C202 Added tests after review
- Statement: Tests V, R and N were added after reviews exposed missing encoder, seed and topology controls.
- Numbers: Test V 24 sections/runs; Test R 96 planned retrainings; Test N 16 runs.
- Label: descriptive
- Source: proposal-to-outcome rows 12–14; protocol 18 Sections 6.3–6.5.
- Verified by supervisor: yes: 17–20 October rulings
- Caveats: Identify them as later predeclared additions.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

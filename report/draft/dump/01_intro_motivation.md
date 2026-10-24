# Introduction and motivation

### C141 MSI as spatial molecular measurement
- Statement: MSI records a mass spectrum at each measured tissue coordinate, producing a high-dimensional spatial data cube without requiring a target list in advance.
- Numbers: Each section contains about a thousand to several thousand locations and 1,481–85,062 spectral bins, depending on the dataset (CAC 1,481; RCC 10,200; GBM 85,062).
- Label: descriptive
- Source: `proposal/proposal.tex` Introduction and Background; `report/draft/sections/introduction.tex`.
- Verified by supervisor: no
- Caveats: Avoid the proposal's unqualified clinical claims; the project evaluates computational peak rankings, not diagnostic deployment.
- Corrected: 2026-10-24 per VERIFICATION.md (bin and pixel ranges per dataset)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C142 Peak-selection problem
- Statement: MSI dimensionality, sparsity and noise motivate selecting a smaller set of informative m/z bins before downstream analysis; classical pipelines use smoothing, normalisation and threshold-based peak picking.
- Numbers: No project-specific value; conceptual motivation.
- Label: descriptive
- Source: `proposal/proposal.tex` Background; `proposal/lit-review.tex`; `report/draft/sections/introduction.tex`.
- Verified by supervisor: no
- Caveats: Do not state that classical peak picking is necessarily manual, linear or clinically blocking without evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C143 Learned peak ranking
- Statement: msiPL and S3PL motivate learning spectral features from MSI data instead of relying only on fixed signal-to-noise heuristics.
- Numbers: msiPL and S3PL are reproduced on 3 datasets in this project.
- Label: descriptive
- Source: `proposal/proposal.tex`; `docs/meetings/references.md`; `docs/research/investigations/19 Upstream Repository and Paper Audit.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: “Learned” does not mean label-independent configuration or molecular identification.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C144 Spatial hypothesis
- Statement: The original hypothesis was that local neighbourhood covariance could improve a lightweight VAE's representation and spatially structured peak ranking without a heavy 3D convolution.
- Numbers: Proposed Moore neighbourhood: 8 neighbours in a 3×3 window.
- Label: descriptive
- Source: `proposal/proposal.tex` Research Questions and Expected Contributions; `docs/meetings/2026-10-19_update/proposal_to_outcome.md` row 1.
- Verified by supervisor: yes: proposal-to-outcome accepted 2026-10-20 10:25
- Caveats: The evaluated evidence does not support a consistent spatially specific gain.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C145 Ranking question that emerged
- Statement: Fair scoring separates whether the learned segmentation is useful from whether nonlinear IG adds value over direct correlation with that segmentation.
- Numbers: 47/47 seed-1 valid comparisons and 136/140 across seeds favour correlation.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 1 and 4; supervisor chat 2026-10-20 10:25.
- Verified by supervisor: yes: 2026-10-20 10:25 and 11:31
- Caveats: This was an added control, not the original proposal claim.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C146 Report preview
- Statement: The evidence supports a narrower contribution: audited fair scoring, a ranking ablation, bounded spatial-context results, encoder and segmentation controls, and explicit reproduction/stability limits.
- Numbers: 3 datasets; 24 sections/runs; 38 formal paired comparisons.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/meeting_summary.md`; supervisor chat 2026-10-20 10:25.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Phrase as an empirical evaluation, not a generally superior detector.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

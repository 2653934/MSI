# Dropped, superseded and negative material

### C095 Drop universal spatial-benefit claim
- Statement: Drop “spatial context universally improves peak selection.” Fixed windows, attention, masking, shuffle controls and Test S do not support it.
- Numbers: CAC seed-1 uniform +0.031 but shuffled ties real; GBM −0.007; Test S never “helps.”
- Label: descriptive
- Source: `report/draft/planning/claim_map.md`; `docs/research/investigations/20 Has Spatial Context Been Ruled Out.md`.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: Replacement is the bounded wording in C086.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C096 Drop IG-caused-the-gain claim
- Statement: Drop “IG caused the pipeline's improvement over legacy.” Posterior correlation and simple baselines show ranking and metric alignment carry much of the result.
- Numbers: IG below posterior in 47/47 seed-1 valid pairs; mean intensity beats legacy on GBM and CAC.
- Label: descriptive
- Source: `report/draft/planning/claim_map.md`; protocol 18 Section 7.1.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: The full VAE/GMM/IG package still beats legacy at K_bin.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C097 Drop intrinsic runtime superiority
- Statement: Drop claims that either S3PL or the VAE is intrinsically faster from the saved clocks.
- Numbers: Three 160TopL native repeats favour VAE wall time, but collection training medians favour 10-epoch S3PL.
- Label: descriptive
- Source: `docs/research/investigations/10 GBM Training Runtime Investigation.md`; `11 S3PL Architecture and Runtime Audit.md`; `14 Primary Results Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: Keep only measured workflow/hardware statements.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C098 Drop S3PL architecture-contrast claim
- Statement: Drop the claim that S3PL demonstrates a consistent benefit from spatially correct neighbours while the VAE does not.
- Numbers: Test N real−shuffled +0.039/+0.040 but only 4/8 and 3/8 sections clear +0.02; label “mixed.”
- Label: "mixed"
- Source: protocol 18 Section 6.5; `docs/meetings/2026-10-19_update/meeting_summary.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: S3PL still strongly depends on having neighbour input under its patch objective.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C099 Drop VAE-is-essential claim
- Statement: Drop any claim that the nonlinear VAE is necessary for segment-then-correlate.
- Numbers: PCA-5 comparison is mixed on GBM/CAC and equivalent on RCC.
- Label: descriptive
- Source: protocol 18 Section 6.4; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.8.
- Verified by supervisor: yes: Test V result rulings
- Caveats: The VAE may still offer other benefits not established here.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C100 Drop fully-unsupervised/autonomous wording
- Statement: Drop “fully unsupervised” or “fully autonomous detector” for the evaluated configuration.
- Numbers: GMM K equals 2/3/3 annotated classes; budgets are released/reference-set derived.
- Label: descriptive
- Source: protocol 18 Sections 0–1 and 6.1; `report/draft/planning/claim_map.md`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Training and ranking remain label-free once configuration is fixed.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C101 Superseded RCC decisions
- Statement: SUPERSEDED: RCC `decisions_20261016_local` used P1 as if it entered the verdict; current `decisions_20261017_local` treats P1 as budget sensitivity.
- Numbers: Verdict labels and CSV values unchanged; interpretation/date replaced.
- Label: descriptive
- Source: protocol 18 Sections 6.1 and 10; supervisor chat 2026-10-17 morning.
- Verified by supervisor: yes: 2026-10-17
- Caveats: Replacement C078/C083 and `decisions_20261017_local`.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C102 Superseded RCC |R@0.4| pilot
- Statement: SUPERSEDED: first RCC reference budget and pilot used |R@0.4|; released-target |R@0.5| results replace it.
- Numbers: Replacement budget equals released `num_GT_peaks`.
- Label: descriptive
- Source: protocol 18 Section 6.1 item D; supervisor chat 2026-10-16 19:47.
- Verified by supervisor: yes: 2026-10-16 19:47
- Caveats: Replacement C006; retain pilot only as provenance.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C103 Superseded pre-fair-scoring headline
- Statement: SUPERSEDED IN PART: “Nonlinear IG improves over legacy” remains numerically true as a package comparison but is no longer the headline after fair scoring.
- Numbers: IG beats legacy 8/8 in all four GBM/CAC arms; IG is below posterior in all 32 seed-1 GBM/CAC section-arms.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/README.md` note dated 15 October; protocol 18 Section 7.1.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Replacement is the ranking ablation in C044–C048.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C104 Negative BIC result
- Statement: No label-free K was obtained from BIC: it selected the largest candidate, K=6, in every tested arm, with no minimum within the predeclared range.
- Numbers: 4/4 GBM/CAC development arms plus 15/15 RCC run-arms (UH0505_12 uniform_mean not done) select largest candidate K=6.
- Label: descriptive
- Source: protocol 18 Sections 6 and 10; current BIC evidence.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Say “largest candidate,” not “six clusters.”
- Corrected: 2026-10-24 per VERIFICATION.md (15/15 RCC run-arms; largest-candidate wording)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C105 Negative IG pixel-count result
- Statement: Increasing attribution samples to 48 or 192 did not meet the setting-change rule.
- Numbers: Best n=192 pair +0.017/+0.024; threshold +0.02 on both.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6; `code/msi/results/publication/current_evidence/gate_d_pixel_counts.csv`.
- Verified by supervisor: yes: 2026-10-10 09:45
- Caveats: Production n=12 stands.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C106 Not-done and incomplete analyses
- Statement: Record rather than conceal predeclared non-completions: Mann–Whitney not done; Test C3 not run; four Test R seed-arms not done; RCC uniform seed-1 verdict incomplete.
- Numbers: Mann–Whitney 0 rows; C3 0 runs; 4 Test R not-done arms; RCC uniform 7/8 valid seed-1 runs.
- Label: "not done"; "incomplete; no verdict"
- Source: protocol 18 Sections 6.1, 6.3, 6.6 and 10.
- Verified by supervisor: yes: relevant 15–20 October rulings
- Caveats: Do not impute or silently omit missing sections.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT
### C229 Unimplemented S3PL GBM matched-budget rerank
- Statement: The protocol reserved an S3PL GBM matched-K rerank if S3PL were placed in the main comparative table, but it was not implemented. The released S3PL GBM reproduction and the fair-scored VAE rankings therefore remain distinct protocols.
- Numbers: 0 matched-K S3PL GBM rerank outputs.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 5; `code/msi/results/publication/current_evidence/README.md`.
- Verified by supervisor: no
- Caveats: This is a documented uncompleted conditional analysis, not a failed S3PL run; retain the native evaluator, budget and seed qualifiers in C042/C074.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C230 Superseded GBM values in previous report
- Statement: SUPERSEDED: the previous report draft's GBM 0.3643 legacy and 0.4562 uniform-context IG values came from an older count/version comparison. The corrected tuned-count seed-1 evidence is 0.4142 legacy and 0.5111 uniform-context IG at the shared section-specific budget.
- Numbers: Older 0.3643/0.4562; replacement 0.4142/0.5111, each mean over n=8 GBM sections.
- Label: descriptive
- Source: `report/draft/previous_version/sections/results.tex`; `docs/research/17 Supervisor Review Response and Report Completion Plan.md`; `code/msi/results/publication/current_evidence/aggregate_method_results.csv`.
- Verified by supervisor: yes: `docs/research/17 Supervisor Review Response and Report Completion Plan.md` (2026-10-08)
- Caveats: CONFLICT within the historical draft: its baseline-reproduction paragraph says tuned legacy GBM 0.414, while its later “primary matched-count” paragraph says legacy 0.3643 without a version qualifier. The saved aggregate and supervisor correction establish C047 as replacement; fair scoring C044–C046 supersedes the old headline.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

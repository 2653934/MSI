# Experimental design and statistics

### C021 Unsupervised transductive design
- Statement: Models are fitted separately on each section from spectra and coordinates without annotation labels, then scored against masks on that same section.
- Numbers: 8 GBM + 8 CAC + 8 RCC sections/runs.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 2; `report/draft/sections/methodology.tex`.
- Verified by supervisor: yes: framing accepted 2026-10-20 10:25
- Caveats: K and budgets are class-informed; this is not inductive generalisation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C022 Held-out RCC confirmation
- Statement: RCC was held out from GBM/CAC development choices; both core arms and all eight runs were specified before scoring.
- Numbers: 8 subjects; central_only and uniform_mean; seed 1; 100 epochs.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.1 item D.
- Verified by supervisor: yes: 2026-10-16 17:36 and 18:34
- Caveats: The unannotated class requires the sensitivity qualification in C082.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C023 Practical rules
- Statement: Practical labels were fixed before relevant outputs. A 0.02 mean mSCF1 threshold, sign counts and partition requirements govern verdicts; no post-result “worse” category was added.
- Numbers: IG “adds value” requires mean ≥+0.02 and >0 in at least 6/8 sections at bin and every approved partition; “equivalent” is within ±0.02.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 6–7.1; `CLAUDE.md`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Outcomes outside defined categories use the exact fall-through wording.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C024 IG-versus-posterior fall-through
- Statement: Required wording: “Neither predeclared verdict applies, because IG scored below posterior-|PCC| in every section.”
- Numbers: Seed-1 bin: GBM/CAC 0/8 IG-positive in four arms; RCC 0/8 centre and 0/7 uniform.
- Label: "mixed / not resolved by the predeclared rule"
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 7.1; `CLAUDE.md`.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: “Mixed” is a rule fall-through, not mixed directional evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C025 Training-seed design and reporting
- Statement: Test R adds seeds 2 and 3 to both core arms on all three datasets. Report collection means as mean ± sample SD across seed-level means, and section SD as median (min–max).
- Numbers: 96 planned retrainings; not-done arms: RCC UH0505_12 twice (including seed 1), RCC UH9912_01 and GBM39_2.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 6.3 and 10; supervisor chat 2026-10-20 10:51.
- Verified by supervisor: yes: 2026-10-20 10:51
- Caveats: Per-seed values move to the appendix, but per-seed predeclared labels remain.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C026 Section 6.6 paired statistics
- Statement: Rule-labelled comparisons use exact two-sided Wilcoxon, Hodges–Lehmann paired difference with exact Walsh-average CI, matched-pairs rank-biserial r, sign count and Holm correction.
- Numbers: 38 comparisons; F1=6, F2=4, F3=17, F4=9, F5=2.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6; supervisor chat 2026-10-20 10:28 and 10:46.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Statistics accompany but never replace practical labels.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C027 Holm attainability
- Statement: Holm is applied within research-question families and separately by scale. At n=8 only families with at most six tests can attain adjusted significance.
- Numbers: Minimum exact two-sided p: 0.0078125 at n=8; 0.125 at GBM PDX n=4.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6 addendum; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: F3 (k=17) and F4 (k=9) cannot attain Holm significance at n=8.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C028 Statistical units
- Statement: Three-seed comparisons average seeds within section before testing. GBM also receives PDX-line summaries outside Holm; CAC is within one biopsy; RCC uses subjects.
- Numbers: GBM PDX n=4; CAC one biopsy; RCC n=8 subjects.
- Label: descriptive
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: P-values describe these sections, not a population.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C029 Descriptive mixed models
- Statement: Mixed models estimate score ~ method + (1|section) [+ (1|seed)]; failed fits are reported only as “not converged.”
- Numbers: CAC both IG arms and RCC uniform did not converge; GBM IG−posterior centre −0.2445 [−0.2731, −0.2159], RCC centre −0.1437 [−0.1722, −0.1152].
- Label: descriptive
- Source: `code/msi/results/diagnostics/statistics_6_6/mixed_models.csv`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Uses all available seed rows, unlike the complete-triple Wilcoxon unit; singular/boundary fits are flagged.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C030 Mann–Whitney item
- Statement: The planned selected-bin Mann–Whitney comparison was not done because posterior-selected bins lacked saved per-bin mask correlations; no substitute was introduced.
- Numbers: 0 result rows.
- Label: "not done"
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 6.6; `code/msi/results/diagnostics/statistics_6_6/mann_whitney.csv`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: A later calculation would require a new specification.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

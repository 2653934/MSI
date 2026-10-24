# Results: main ranking comparison

### C044 Seed-1 IG versus posterior correlation
- Statement: Holding each fitted GMM fixed, IG scored below posterior correlation in every valid seed-1 comparison across all three datasets.
- Numbers: 47/47 valid section–arm comparisons; GBM differences −0.225/−0.233, CAC −0.078/−0.047, RCC −0.156/−0.185 (centre/uniform; RCC uniform n=7).
- Label: "mixed / not resolved by the predeclared rule"
- Source: `code/msi/results/publication/current_evidence/fair_scoring_collection_summary.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 4.1 and 6.5; protocol 18 Section 7.1.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Paired dependent comparisons, not 47 independent biological samples; use C024 wording.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C045 Three-seed IG versus posterior correlation
- Statement: Across Test R, posterior correlation beat IG in 136/140 valid pairs; the strict per-seed rule failed only at CAC seed 2.
- Numbers: 136/140; CAC seed-2 centre P1 6/8 and uniform bin/P1 6/8; four not-done seed-arms listed in C025.
- Label: "does not hold overall"
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.9; `code/msi/results/diagnostics/fair_scoring_baselines/test_r/decisions_20261017_local/`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: This label is the predeclared per-seed rule outcome; aggregate statistical support in C046 appears beside it.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C046 F1 statistical support
- Statement: IG being below posterior correlation is statistically supported in all six collection×arm comparisons at bin level.
- Numbers: Holm p≤0.04688; all section differences negative; rank-biserial r=−1. Example seed-mean rows: GBM centre −0.2445, CAC centre −0.07735, RCC centre about −0.14.
- Label: "statistically supported"
- Source: `code/msi/results/diagnostics/statistics_6_6/tests.csv`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Holm values sit at the smallest attainable p for n=6–8. CAC uniform P1 is not supported (p=0.078; 7/8).
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C047 IG versus legacy msiPL
- Statement: Both VAE/IG arms beat reproduced legacy msiPL at K_bin in every GBM and CAC section.
- Numbers: GBM legacy 0.414 vs IG 0.518 centre/0.511 uniform; CAC 0.402 vs 0.528/0.560; 8/8 wins in all four arms.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/aggregate_method_results.csv`; protocol 18 Section 7.1; `docs/research/investigations/14 Primary Results Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Package comparison, not proof IG or spatial context caused the gain; legacy is not K_peak-matched.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C048 F2 statistical support versus legacy
- Statement: The four bin-level IG-versus-legacy comparisons are statistically supported within F2.
- Numbers: 4/4 rows Holm-adjusted p<0.05.
- Label: "statistically supported"
- Source: `code/msi/results/diagnostics/statistics_6_6/tests.csv`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Does not repair the unassessable budget-stability clause or make legacy a strong benchmark.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C049 Attribution-pixel count gate
- Statement: Increasing IG sampling from 12 to 48 or 192 pixels per component did not meet the promotion rule; production n=12 stands.
- Numbers: Best case centre n=192: +0.017 GBM108_positive and +0.024 40TopL; required ≥+0.02 on both.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/gate_d_pixel_counts.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.2; protocol 18 Section 6.
- Verified by supervisor: yes: 2026-10-10 09:45
- Caveats: Two development sections only; other IG settings remain untested.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C050 GBM PDX-level direction
- Statement: IG minus posterior correlation is negative within every GBM PDX line; PDX-level p-values cannot be below 0.125 by construction.
- Numbers: 4 PDX lines; n=4; minimum two-sided p=0.125.
- Label: descriptive
- Source: `code/msi/results/diagnostics/statistics_6_6/tests.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 4.1.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Report direction and Hodges–Lehmann estimates, not population significance.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

# Results: spatial context

### C055 Core uniform-context comparison
- Statement: Uniform 3×3 context helps CAC IG at seed 1 but gives no consistent GBM benefit.
- Numbers: CAC +0.031, 8/8; GBM −0.0067, 5/8. Under three-seed averaging CAC +0.023 bin and +0.027 P1, 8/8; GBM incomplete, +0.000 bin over 7 sections.
- Label: CAC "helps"; GBM seed 1 "equivalent" and three-seed "incomplete"
- Source: `code/msi/results/publication/current_evidence/aggregate_method_results.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 5.2 and 6.9.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: CAC is one biopsy; under correlation ranking its context difference is 0.000, so this effect belongs to IG ranking.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C056 Window and zero/shuffle controls
- Statement: Fixed-window controls do not establish a spatially specific gain: CAC real and shuffled 3×3 tie; GBM zeroed context is highest in the descriptive confirmation subset.
- Numbers: CAC confirmation means real3 0.5419, real5 0.5352, zero3 0.5235, shuffled3 0.5425; GBM 0.4460, 0.4334, 0.4594, 0.4430.
- Label: descriptive
- Source: `docs/research/investigations/14 Primary Results Claim-Evidence Ledger.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 5.3.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Seed 1, IG only, older GBM counts, seven confirmation sections; shuffled inputs change distribution and retain overlap topology.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C057 Larger windows
- Statement: Uniform 7×7 and 9×9 windows do not meet the “helps” rule; both are below 3×3 on GBM and equivalent on CAC.
- Numbers: GBM both −0.035 bin, 2/8 positive; P1 −0.032/−0.034. CAC both within ±0.02; p7 P1 −0.018, 1/8 positive. p5 descriptive: GBM −0.018, CAC −0.006.
- Label: GBM "mixed"; CAC "equivalent"
- Source: `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 6.1 and 10; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 5.3.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Required wording: does not meet “helps”; report negative size and sign count.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C058 Attention versus uniform
- Statement: Learned attention is equivalent to uniform averaging on both collections in the final fair test.
- Numbers: GBM +0.011, 6/8 positive; CAC −0.006.
- Label: "equivalent"
- Source: protocol 18 Section 10; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 5.4.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Equivalence and simplicity, not runtime cost, justify retaining uniform mean.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C059 Attention mechanism
- Statement: Real-neighbour attention stayed near uniform, while shuffled-neighbour models learned much more selective weights, showing the mechanism can respond when inputs differ.
- Numbers: Real normalised entropy 0.98–0.999; masked 0.998–0.999; attention-vs-uniform half-L1 real 0.003–0.028 vs shuffled 0.16–0.32; neighbour-centre median cosine ≈0.98.
- Label: descriptive
- Source: `docs/research/investigations/13 Spatial Context Claim-Evidence Ledger.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 5.4.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Sampled pixels/two development sections; not proof attention cannot help in another design.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C060 Centre masking
- Statement: Centre masking did not make attention selective and lowered GBM peak scores versus standard attention.
- Numbers: GBM G1−attention −0.039 bin/−0.040 P1, 1/8 positive; CAC equivalent; G1 vs G2 equivalent both collections; G3 +0.021 160TopL and −0.011 GBM22_2.
- Label: GBM "mixed"; CAC "equivalent"; G1 vs G2 "equivalent"; G3 rule not met
- Source: protocol 18 Sections 6.1 and 10; supervisor wording 2026-10-16 17:36.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: G3 is two exploratory sections.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C061 Frozen neighbour swap
- Statement: The trained real-neighbour model responds to neighbour replacement, but the frozen shuffled input is out of distribution and does not establish deployment benefit.
- Numbers: Reconstruction MSE ratio shuffled/real 1.36–3.38 in 16/16; label flips mean 4.27% CAC and 8.48% GBM; shuffled−real mSCF1 +0.0049 CAC and +0.0183 GBM.
- Label: descriptive
- Source: `docs/research/investigations/13 Spatial Context Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Same-checkpoint mechanism test; retrained shuffle is the fairer intervention.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C062 Shuffle distribution/topology audit
- Statement: Nonlocal shuffle substantially shifts centre–context similarity but preserves local overlap in the fixed source permutation.
- Numbers: Shuffled cosine below real 5th percentile: 81.1% 160TopL, 66.2% GBM22_2; half-L1 above real 95th: 92.0%, 70.9%; adjacent source-set Jaccard ≈0.240 in real and shuffled.
- Label: descriptive
- Source: `docs/research/investigations/13 Spatial Context Claim-Evidence Ledger.md`.
- Verified by supervisor: no
- Caveats: Two development sections and selected distribution statistics, not a formal full-model OOD proof.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C063 Spatial segmentation Test S results
- Statement: Spatially smoothed segmentation was never labelled “helps”: four decided comparisons were equivalent, one mixed, and RCC uniform incomplete.
- Numbers: GBM centre +0.013 5/8 equivalent; GBM uniform +0.029 3/8 mixed; CAC centre −0.001 4/8 equivalent; CAC uniform +0.004 5/8 equivalent; RCC centre −0.012 5/8 equivalent; RCC uniform −0.023 4/7 incomplete.
- Label: "equivalent" (4); "mixed" (1); "incomplete; no verdict" (1)
- Source: `docs/research/investigations/20 Has Spatial Context Been Ruled Out.md`; `code/msi/results/diagnostics/spatial_segmentation_S/decisions_20261017_local/`.
- Verified by supervisor: yes: 2026-10-17 08:37
- Caveats: CAC P1 is a two-budget check, not independent partition evidence.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

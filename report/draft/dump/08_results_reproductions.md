# Results: baseline reproductions

### C039 Legacy msiPL reproduction
- Statement: Reproduced legacy msiPL means are close to the published values on all three datasets.
- Numbers: GBM 0.414 vs 0.403 published; CAC 0.402 vs 0.431; RCC 0.157 vs 0.16 (8/8 runs; count target missed in 6/8 RCC runs).
- Label: descriptive
- Source: `docs/research/investigations/19 Upstream Repository and Paper Audit.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Sections 3 and 6.6; protocol 18 Section 10.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: RCC legacy is reference-only and not at the same budget.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C040 S3PL CAC reproduction
- Statement: S3PL on CAC is close to the published collection mean at seed 1, although individual sections differ; across ten released seeds the published mean lies just outside our seed distribution.
- Numbers: Seed-1 0.5915 vs 0.601 published; ten released seeds 0.5470 ± 0.0377, seed-level range 0.4960–0.5910; per-section seed SD median 0.0456 (0.0346–0.2094).
- Label: "outside our seed distribution"; "not explained by seed selection alone"
- Source: `docs/research/investigations/19 Upstream Repository and Paper Audit.md`; `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`.
- Verified by supervisor: yes: 2026-10-20 20:57
- Caveats: One of 160 released runs returned 256/257 peaks (CAC 240TopL seed 7); S3PL's in-job evaluator is used. The margin is within the published 2-decimal rounding (per-section mean 0.60125), so CAC is consistent with a favourable seed or best-of-several selection, but not shown to be.
- Corrected: 2026-10-24 per VERIFICATION.md (Part B CAC labels and rounding qualifier)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C041 S3PL RCC reproduction
- Statement: S3PL RCC reproduction is close to the published mean over three seeds.
- Numbers: Ours 0.41–0.44 across three seeds vs 0.47 published; seed 1 ≈0.44.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/meeting_summary.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.6; protocol 18 Section 10.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: S3PL's native evaluator/protocol, not the fair-scoring evaluator.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C042 S3PL GBM reproduction gap
- Statement: The published S3PL GBM score was not reproduced; the published value exceeds the ten-seed distribution and the per-section best-of-10 average.
- Numbers: Published 0.496; released-seed mean 0.3193 ± 0.0419, range 0.2260–0.3735; best-of-10 0.4343; published above all three earlier controlled seeds in 7/8 sections.
- Label: "outside our seed distribution"; "not explained by seed selection alone"
- Source: `docs/research/investigations/19 Upstream Repository and Paper Audit.md`; `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`; supervisor chat 2026-10-20 20:57.
- Verified by supervisor: yes: 2026-10-20 20:57
- Caveats: Published scores are rounded; no supplementary tables were publicly available; do not select the best seed as baseline. S3PL in-job mSCF1, not the fair-scoring evaluator.
- Corrected: 2026-10-24 per VERIFICATION.md (evaluator disclosure)
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C043 Upstream audit
- Statement: The project used the current public S3PL repository and the recorded msiPL import; no public supplement exposes the paper's per-dataset hyperparameter or peak-count tables.
- Numbers: S3PL HEAD 660e3d9 (29 Apr 2026, v1.0.0); msiPL HEAD 1e8d5cf (11 Jul 2021); paper arXiv:2603.10487v1.
- Label: descriptive
- Source: `docs/research/investigations/19 Upstream Repository and Paper Audit.md`.
- Verified by supervisor: yes: Investigation 19 included in accepted update
- Caveats: Absence of public supplements limits exact paper-protocol verification.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

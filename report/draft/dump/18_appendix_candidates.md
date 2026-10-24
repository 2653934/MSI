# Appendix candidates

### C209 Per-seed result tables
- Statement: Put individual Test R, S3PL, Test N and attention seed values in the appendix; body uses mean ± SD.
- Numbers: VAE 3 seeds; S3PL released 10 seeds GBM/CAC; Test N 2 seeds.
- Label: descriptive
- Source: supervisor chat 2026-10-20 10:51; relevant decision tables.
- Verified by supervisor: yes: 2026-10-20 10:51
- Caveats: Preserve not-done seed-arms.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C210 Full Section 6.6 tables
- Statement: Put all 38 paired rows, P1 secondary rows, PDX-line rows and descriptive mixed models in the appendix.
- Numbers: F1–F5 family sizes 6/4/17/9/2.
- Label: descriptive
- Source: `code/msi/results/diagnostics/statistics_6_6/`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Body should use one concise table per family; Mann–Whitney remains not done.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C211 Per-section and PDX summaries
- Statement: Include section-level values, GBM PDX-line aggregates, sign counts and uncertainty so collection means are auditable.
- Numbers: 8 sections/collection; 4 GBM PDX lines.
- Label: descriptive
- Source: current evidence CSVs; `report/draft/tables/gbm_patient_summary.tex`.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Rebuild patient table for final seed-mean unit.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C212 Protocol and evidence map
- Statement: Include a compact chronology of predeclarations, decision rules, superseded records and artifact paths.
- Numbers: Protocol 18 Sections 6–10; 220 dump items when complete.
- Label: descriptive
- Source: protocol 18; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Appendix A.
- Verified by supervisor: yes: report plan 2026-10-24 14:03
- Caveats: Summarise; do not reproduce the entire execution log in the body.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C213 Proposal-to-outcome table
- Statement: Include the full original-commitment versus delivered/changed/omitted account.
- Numbers: 14 rows plus dated change timeline.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/proposal_to_outcome.md`.
- Verified by supervisor: yes: 2026-10-20 10:25
- Caveats: Do not rewrite later controls as original plans.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C214 Detailed controls and negative results
- Statement: Candidate appendix material includes pixel-count sweeps, BIC curves, window controls, attention mechanism/OOD audits, S3PL gap diagnostics, training curves and incomplete/not-done records.
- Numbers: See items C049, C056–C062, C067–C077 and C095–C106.
- Label: descriptive
- Source: investigations 10–21; update-pack figures; protocol 18 Section 10.
- Verified by supervisor: yes: report structure 2026-10-24 14:03
- Caveats: Placement remains for curation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

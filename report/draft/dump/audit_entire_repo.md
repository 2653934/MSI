# Entire-repository dump audit ledger

Date: 2026-10-24 (SAST). The existing inventory ended at C220; new claims are C221–C238. This is an audit record, not a numbered claim.

| Repository area inspected | Potentially relevant files and result families | New IDs | Inspected without a distinct new claim |
|---|---|---|---|
| Scientific protocol and result records | Protocol 18 Sections 0–10; docs/research/01 Results Record.md; investigations 10–21; code/msi/results/diagnostics summary families | C221, C223–C224, C229, C236–C238 | Investigations 10–12, 14–16 and 19–21, plus fair-scoring, Test R/S/V/N, statistics, BIC, timing and Investigation 21 summaries: distinct outcomes already in C031–C083. |
| Datasets and provenance | docs/research/03 Datasets and Preprocessing.md; GBM imzML/HDF5 comparison JSON; RCC feasibility summaries; docs/meetings/references.md | C222, C234 | RCC feasibility/class caveat already C003/C078–C083. References tracker already maps to C147–C190. |
| Methods, scripts and tests | code/msi/src/spatial_msipl, code/msi/scripts, code/msi/baselines/s3pl; preprocessing, attribution, scoring, partition, provenance, RCC, S3PL, statistics and bit-identity tests | C225–C228 | Cache identity, stale guards, GMM/PCA controls and seed flags already C016–C038 and C215–C220. Tests confirm contracts, not new real-data results. |
| Negative, failed, incomplete and superseded work | Protocol 18 execution log; docs/research/17 Supervisor Review Response and Report Completion Plan.md; prior/current report drafts; saved comparison summaries | C229–C230 | Infrastructure failures, old RCC budget/P1 interpretation, BIC boundary, IG count gate, missing Test R arms and Mann–Whitney already C095–C106. |
| Limitations and objections | Investigation 13; docs/report/Report Requirements and Evidence Map.md; meeting records and previous discussion | C223–C224, C228, C237–C238 | Clustered samples, class-informed K, mask agreement and S3PL reproduction limits already C084–C094. |
| Figures, tables and editable assets | report/draft/previous_version/figures and images; results/README.md; results/datasets and model-comparisons; code/msi/results/visualisations; current-evidence and update-pack tables | C231–C233 | Top-level gallery copies and comparison plots restate C107–C140; accompanying text/tables were used as evidence. |
| Background, proposal and older reports | proposal text, both report drafts, September meeting brief, docs/research/02–09, handbook and report planning records | C230, C234 | Original RQs, proposal-to-outcome, references and accepted framing already C141–C214. |
| Reproducibility and AI use | CLAUDE.md, docs/research/06, docs/operations/cluster_sync.md, repository audit, supervisor chat and two proposal AI declaration forms | C235 | Code availability, hashes, tests and workflow already C215–C220. No checked declaration choices were inferred. |

## Exclusions and interpretation

- Credentials, keys, environment files, dependency directories, caches and .git contents were excluded. The pre-existing untracked report/draft/planning/report_plan_2026-10-21.md was left untouched.
- Repeated per-run JSON/CSV files were searched by result family and compared through saved summaries, decision tables and provenance. Raw Slurm logs were used only where needed for failure or provenance; they were not treated as fresh claims.
- Binary checkpoints, NumPy arrays and unrelated images were not interpreted. Proposal/report PDFs and architecture PDFs have text/TeX/TikZ sources. The two AI declaration PDFs were read because their form language may be unique. Figure claims rely on text, captions or result summaries.
- C230 records the newly found historical CONFLICT. Current differences tied to seeds, budgets, evaluator versions or statistical units remain scoped in existing dump items.

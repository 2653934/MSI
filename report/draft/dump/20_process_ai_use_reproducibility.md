# Process, AI use and reproducibility

### C215 Append-only scientific record
- Statement: Specifications, approvals, results, reviews and resolutions are recorded in protocol 18 and the append-only supervisor chat; earlier entries are not rewritten.
- Numbers: Protocol 18 Sections 6–10 govern the final experiments and execution record.
- Label: descriptive
- Source: `CLAUDE.md`; `docs/supervision/supervisor_chat.md`; protocol 18.
- Verified by supervisor: yes: current-state guidance reviewed 2026-10-21 14:41
- Caveats: The report should distinguish predeclared, descriptive and post-hoc analyses.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C216 Code and artifact provenance
- Statement: Result summaries record evaluator/protocol versions, parameters, input hashes and code hashes; scripts fail closed on stale or existing outputs.
- Numbers: Section 6.6 reproduced 4/4 outputs byte-for-byte; numerous decision tables regenerated identically during review.
- Label: descriptive
- Source: protocol 18 Sections 8–10; supervisor review entries.
- Verified by supervisor: yes: 2026-10-20 11:34
- Caveats: Raw cluster results are evidence and were not edited.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C217 Independent review and tests
- Statement: Codex reviewed and committed staged work; a separate supervisor checked scientific wording and predeclarations; local and cluster tests guarded code paths and bit identity.
- Numbers: Section 6.6 14/14 local; Investigation 21 Part C CPU gate 259 main tests with 3 expected skips, 25 S3PL tests and 4 seed-flag tests.
- Label: descriptive
- Source: supervisor chat 2026-10-20 11:34 and 2026-10-21 14:24; protocol 18 Section 10.
- Verified by supervisor: yes: 2026-10-21 14:21
- Caveats: Review reduces but does not eliminate scientific/software error.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C218 AI-use disclosure
- Statement: AI systems assisted planning, code generation, review, evidence extraction and report preparation under Zayd's decisions; generated claims were checked against saved repository artifacts and supervisor rulings.
- Numbers: Not applicable.
- Label: descriptive
- Source: repository workflow in `CLAUDE.md`; `proposal/PG student AI declaration RP.pdf`; `proposal/PG student AI declaration LR.pdf`; supervisor chat.
- Verified by supervisor: no
- Caveats: Final wording must follow the university declaration form and accurately name tools/roles; do not claim AI independently made scientific decisions.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C219 Code availability statement material
- Statement: The report can state that code, tests, predeclared protocols and derived evidence are version-controlled in the project repository, while raw data/checkpoints remain on the institutional cluster subject to their source licences/access.
- Numbers: Not applicable.
- Label: descriptive
- Source: `CLAUDE.md`; protocol 18 Sections 8–11; repository paths documented in the evidence map.
- Verified by supervisor: no
- Caveats: Insert the actual public repository/archive URL only if and when released; do not promise access not yet provided.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C220 Reproducibility limitations
- Statement: Exact reproduction is hardware- and path-sensitive; older streaming runs, current cached runs, distinct CPU models and S3PL normalisation modes are disclosed rather than pooled silently.
- Numbers: Cached VAE exact in 2 audited arms; S3PL repeats exact in 3 sections on RTX 3090; RCC ranking exact 28/28 comparable checks on i9-10940X.
- Label: descriptive
- Source: investigations 10, 16 and 21; runtime v2; `CLAUDE.md` hardware lessons.
- Verified by supervisor: yes: 2026-10-21 14:41
- Caveats: Bit identity on one hardware path does not guarantee portability.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

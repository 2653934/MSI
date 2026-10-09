# Research report drafting workspace

This directory is the only active report-writing location until the report is
explicitly approved for promotion to `report/final/`.

## Directory roles

- `report.tex`: active compilable draft using the official 2026 Wits format.
- `sections/`: current report prose. Claims must agree with the audited evidence.
- `planning/`: report-only reasoning, traceability and claim-control material.
- `previous_version/`: preserved six-page report and its figures. It is a source
  of reusable prose and assets, not an authoritative source of numeric claims.
- `official_template.tex`: untouched official template supplied for the report.
- `template_references.bib`: example bibliography supplied with the template.
- `references.bib`: working research bibliography inherited from the previous
  report and to be verified during the literature pass.
- `report/final/`: deliberately empty until a submission-ready draft passes the
  evidence, formatting and consistency audits.

## Authoritative evidence order

1. `docs/research/investigations/14 Primary Results Claim-Evidence Ledger.md`
2. `docs/research/investigations/16 S3PL GBM Stability and Runtime Synthesis.md`
3. machine-readable result files linked by those ledgers;
4. `docs/report/Research Questions and Contributions.md` for bounded framing;
5. the previous report only for wording or figure candidates.

If prose and an audited artifact disagree, the audited artifact wins. A number
must not enter the report without a source row in the claim ledger or the draft
claim map.

## Promotion rule

Nothing is copied into `report/final/` until all of the following hold:

- stale values, equations and scoring descriptions are corrected;
- the proposal-to-outcome account is complete;
- GBM results are shown by patient as well as section;
- development, exploratory and confirmation evidence are distinguished;
- every efficiency statement names the measured quantity and protocol;
- the abstract, results, discussion and conclusion agree;
- the compiled report meets the required 8--12 pages excluding references;
- Astra and Hairong have been given the bounded contribution and report
  structure for review.


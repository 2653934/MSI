# Decision log

**Purpose:** one place for every standing decision, so nobody reverses one by accident.

**Rules:**
- Before proposing anything that touches a decision below, check here first.
- A decision changes only by adding a new row that says which decision it **supersedes**. Old rows are never edited or deleted; mark them `SUPERSEDED by Dxx` instead.
- New rows go at the bottom of the right section, with the next free number.

**Status values:**
- **ACTIVE**: in force.
- **SUPERSEDED**: replaced; follow the newer row.
- **PENDING**: a decision is needed.

**Sources:** "Chat" means `docs/supervision/supervisor_chat.md`, by entry time. "P18" means `docs/research/18 Fair Scoring and Simple Baselines Protocol.md`.

## A. Report: scope, format and framing

| ID | Date | Decision | Why | Who | Source | Status |
|---|---|---|---|---|---|---|
| D01 | 19 Oct | Title: "Spatial Aware Peak Ranking in Mass Spectrometry Imaging" | Hairong's change | Hairong | update outcome | ACTIVE |
| D02 | 19 Oct | Framing: a controlled evaluation of where spatial information helps learned peak ranking | Accepted at the update | Hairong | update outcome | ACTIVE |
| D03 | 21 Oct | Report due 2 Nov | Then believed | Zayd | report plan | SUPERSEDED by D04 |
| D04 | 30 Oct | Submission **11 Nov** | Hairong gave the date | Hairong | Chat 12:58 | ACTIVE |
| D05 | 30 Oct | 8 pages including appendices | Misreading of "8 pages" | Zayd | session | SUPERSEDED by D06 |
| D06 | 30 Oct | **8–12 pages, excluding references** (official template, line 144). Target 10–11 pages of body | Template rule; 8 is the minimum | template | `official_template.tex` | ACTIVE |
| D07 | 30 Oct | **No appendix**; everything goes in the body | Easier to follow | Zayd | session | ACTIVE |
| D08 | 30 Oct | **No proposal framing:** no proposal-to-outcome table, no P1–P3 or "autonomy" discussion. Write it like a normal paper | The project changed from the proposal | Zayd | session | ACTIVE |
| D09 | 30 Oct | Include a **dataset figure** (TIC + annotation mask per collection) | Every paper we read shows the data | Zayd | Chat 12:58, item 4 | ACTIVE |
| D10 | 30 Oct | **No incomplete experiments, and nothing that looks incomplete.** Run everything first, then write | Zayd's requirement | Zayd | Chat 12:58 | ACTIVE |
| D11 | 30 Oct | Abstract 150–250 words, no citations or undefined acronyms. Choose from `report/draft/planning/abstract_options.md` (supervisor recommends Draft 2 minus K) | Template | Zayd | abstract_options.md | PENDING |
| D12 | 25 Oct | Style follows `report/draft/planning/report_style_guide.md`. Quote verdict labels exactly; say "bins" vs "peaks" correctly | Consistency | Supervisor | style guide | ACTIVE |
| D13 | 30 Oct | Report figures are rebuilt in report style: no presentation titles, colour-blind-safe | Update-pack figures carry slide titles | Supervisor | Chat 12:58, item 4 | ACTIVE |
| D14 | 19 Oct | Include a short **caching/runtime** subsection | Hairong (HPC lecturer) asked for it | Hairong | update outcome | ACTIVE |
| D15 | 30 Oct | **No Oxford comma** ("A, B and C"); British spelling throughout | Zayd's writing style (British English) | Zayd | style guide | ACTIVE |
| D16 | 30 Oct | Submit by **11 Nov, midnight**; no extensions. The 2025 rubric may change (Prof Vadapalli will announce the 2026 one) | Hairong's email | Hairong | project doc hairong-final-report-requirements | ACTIVE |
| D17 | 30 Oct | Use the supplied IEEE Overleaf template. Remove all red instructions, sample text and sample references, so no red text remains | Hairong's email | Hairong | same | ACTIVE |
| D18 | 30 Oct | The completed **postgraduate AI declaration form** is the **final page**. It covers all AI use (code generation, method design, review, writing), names the models and includes the relevant prompts (extra pages allowed) | Hairong's email | Hairong | same | ACTIVE |
| D19 | 30 Oct | The **GitHub link** goes in the experimental setup. It points to a **new, clean, public repo, `Spatial-msiPL` (https://github.com/2653934/Spatial-msiPL)**: final code, environment, small summary results, a README with data access and a table/figure → script map, and the baselines linked at their exact commits (not copied). It excludes the chat, drafts, working docs and data. The paper cites a tagged release and commit | Hairong; Zayd chose public | Zayd | Chat (this entry) | ACTIVE |

## B. Experiments and analysis

| ID | Date | Decision | Why | Who | Source | Status |
|---|---|---|---|---|---|---|
| D20 | Oct | Predeclared rules and thresholds are fixed before results. Never tune a rule, partition, budget, seed or threshold after seeing outcomes; propose changes as a new, separately labelled analysis | Integrity | Supervisor | CLAUDE.md, P18 | ACTIVE |
| D21 | Oct | Labels: "helps" = mean ≥ +0.02 and positive in ≥ 6/8 sections; "equivalent" = within ±0.02; otherwise "mixed"; "incomplete" if sections are missing. Use the exact fall-through wording | Predeclared | Supervisor | P18 §7.1; Chat 16 Oct 17:36 | ACTIVE |
| D22 | 20 Oct | Statistics (P18 §6.6): exact Wilcoxon, Hodges–Lehmann CI, rank-biserial r, Holm within F1–F5. "Statistically supported" needs Holm p < 0.05 **and** agreement with the practical label | Hairong asked for statistics | Supervisor | statistics plan | ACTIVE |
| D23 | 20 Oct | Mann–Whitney is not used because the comparisons are paired. The paper simply reports paired tests and does not call Mann–Whitney "not done" | Correct test | Supervisor | Chat 12:58 | ACTIVE |
| D24 | 21 Oct | Seeds: report mean ± SD **across seeds** of the seed-level collection means; per-section seed SD as median (min–max) | Hairong; style-guide fix | Supervisor | style guide | ACTIVE |
| D25 | Oct | K_bin = tuned legacy msiPL count (GBM, CAC); released S3PL target (RCC, ≈ \|R@0.5\|) | Shared budget | Supervisor | P18 §2 | ACTIVE |
| D26 | 16 Oct | RCC: NA pixels are kept as a third class, "unannotated"; GMM K = 3 | Predeclared option (a) | Supervisor/Zayd | P18 §6.1 D | ACTIVE |
| D27 | 30 Oct | **IG completeness:** an arm that fails at 64 steps is rerun from its checkpoint at 128, then 256. All other arms stay at 64. A 64-vs-128 control is reported | D10 | Zayd/Supervisor | Chat 12:58, 13:30; P18 §6.3 amendment | ACTIVE |
| D28 | 30 Oct | **msiPL Beta re-tune** (−2 to 2.5) at m ∈ {0.5, 0.75, 1, 1.5, 2} on all collections. An unreachable count = msiPL cap, a property of msiPL. On RCC, all rankings are also scored at msiPL's count. RCC msiPL rows sit outside Holm | Fill the RCC cell; assess budget stability | Supervisor | Chat 12:58, item 2 | ACTIVE |
| D29 | 30 Oct | C3 training length (epochs 10/25/50/100, development sections) is run | Justifies 100 epochs | Zayd | Chat 13:20 | ACTIVE |
| D30 | Oct | The S3PL GBM matched-K rerank is not run; S3PL is not in the fair-scored table | Conditional analysis not triggered | Supervisor | Chat 12:58 | ACTIVE |
| D31 | Oct | Statistical unit = section. GBM PDX-line rows are reported; CAC is 8 sections of one biopsy | Independence | Supervisor | P18 | ACTIVE |
| D32 | 30 Oct | Composite root for regenerated summaries: copy, never move, with a SHA-256 manifest; unchanged summarisers | Provenance | Supervisor | Chat 13:30 | ACTIVE |
| D33 | 30 Oct | GMM gate = direct pixel-sample/target identity, not component-order identity (30 Oct, after 78483). Gate v2: model state equal, hard assignment equal, alignment within 1e-4, and per component identical attribution/faithfulness pixels and IG target, with aligned mean/covariance within 1e-6; written as `gmm_gate_v2.json`, v1 kept | The identity condition was a proxy that rejected a true match (78483 tasks 1/4/8; direct check clean 12/12 before any scoring) | Supervisor/Zayd | Chat 14:46, 14:54; P18 §6.3 gate correction | ACTIVE |

## C. Process and cluster

| ID | Date | Decision | Why | Who | Source | Status |
|---|---|---|---|---|---|---|
| D40 | Oct | Roles: Code builds and runs; **Codex reviews and commits** (no longer a builder); Zayd decides and may commit; Supervisor rules in the chat | Zayd's preference | Zayd | session | ACTIVE |
| D41 | 30 Oct | Commits stay with Codex (Zayd tried manual commands and prefers Codex) | Easier | Zayd | session | ACTIVE |
| D42 | 30 Oct | **Commit messages contain no AI names (Claude, Code, Codex, Supervisor) and no dates** | Zayd's rule | Zayd | session | ACTIVE |
| D43 | Oct | Every `sbatch`, cancel or cluster file move needs Zayd's explicit OK, after a pre-submission checklist | Safety | Zayd | CLAUDE.md | ACTIVE |
| D44 | Oct | Never `--delete`; never touch `/datasets` data; `mv -n` only; nothing is deleted (cleanups use `rmdir` only, with Zayd's OK) | Safety | Zayd | CLAUDE.md | ACTIVE |
| D45 | Oct | No subagents | Token cost | Zayd | session | ACTIVE |
| D46 | Oct | The chat is append-only, with times from Zayd's local clock (SAST); close items with "Resolves:" | Audit trail | Supervisor | workflow doc | ACTIVE |
| D47 | 17 Oct | Polling: wait for the expected duration, then at most every 2–5 min; one SSH call per check; no loops or `watch` | Login-node stability | Supervisor | CLAUDE.md | ACTIVE |
| D48 | Oct | Results are read locally only, after a pull | Login-node rule | Supervisor | CLAUDE.md | ACTIVE |
| D49 | 16 Oct | Training must use the cached loader (`--cache-spectra`), enforced by a test | 11 h → 23 min | Supervisor | CLAUDE.md | ACTIVE |
| D50 | Oct | CPU jobs go on `batch`. `bigbatch` only for long or high-memory work, or with Zayd's OK when `batch` is down | Fair use | Supervisor | CLAUDE.md | ACTIVE |
| D51 | Oct | Never `--exclusive` on busy `bigbatch` nodes | Queue waits | Supervisor | CLAUDE.md | ACTIVE |
| D52 | 30 Oct | **GPU IG jobs may run on `batch` (RTX 3060) when `bigbatch` is overloaded.** All tasks of one comparison run on the **same** partition. Set the partition at submit time and log the move in P18 §10 | `bigbatch` full; IG ran on `batch` 3060s before (Chat, gate d) | Zayd/Supervisor | Chat (this entry) | ACTIVE |
| D53 | Oct | Echo-first dry runs for any cluster file loop | Safety | Supervisor | CLAUDE.md | ACTIVE |
| D54 | Oct | Don't inspect SSH keys | Security | Zayd | session | ACTIVE |

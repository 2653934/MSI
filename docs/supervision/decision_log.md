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
| D11 | 30 Oct | Abstract 150–250 words, no citations or undefined acronyms. Choose from `report/draft/planning/abstract_options.md` (supervisor recommends Draft 2 minus K) | Template | Zayd | abstract_options.md | SUPERSEDED by D20a |
| D12 | 25 Oct | Style follows `report/draft/planning/report_style_guide.md`. Quote verdict labels exactly; say "bins" vs "peaks" correctly | Consistency | Supervisor | style guide | ACTIVE |
| D13 | 30 Oct | Report figures are rebuilt in report style: no presentation titles, colour-blind-safe | Update-pack figures carry slide titles | Supervisor | Chat 12:58, item 4 | ACTIVE |
| D14 | 19 Oct | Include a short **caching/runtime** subsection | Hairong (HPC lecturer) asked for it | Hairong | update outcome | ACTIVE |
| D15 | 30 Oct | **No Oxford comma** ("A, B and C"); British spelling throughout | Zayd's writing style (British English) | Zayd | style guide | ACTIVE |
| D15b | 30 Oct | Write **S³PL** with a superscript 3 in the report, as the authors do. Plain S3PL is fine in code, file names and the chat | Matches the source paper | Zayd | style guide | ACTIVE |
| D16 | 30 Oct | Submit by **11 Nov, midnight**; no extensions. The 2025 rubric may change (Prof Vadapalli will announce the 2026 one) | Hairong's email | Hairong | project doc hairong-final-report-requirements | ACTIVE |
| D17 | 30 Oct | Use the supplied IEEE Overleaf template. Remove all red instructions, sample text and sample references, so no red text remains | Hairong's email | Hairong | same | ACTIVE |
| D18 | 30 Oct | The completed **postgraduate AI declaration form** is the **final page**. It covers all AI use (code generation, method design, review, writing), names the models and includes the relevant prompts (extra pages allowed) | Hairong's email | Hairong | same | ACTIVE |
| D19 | 30 Oct | The **GitHub link** goes in the experimental setup. It points to a **new, clean, public repo, `Spatial-msiPL` (https://github.com/2653934/Spatial-msiPL)**: final code, environment, small summary results, a README with data access and a table/figure → script map, and the baselines linked at their exact commits (not copied). It excludes the chat, drafts, working docs and data. The paper cites a tagged release and commit | Hairong; Zayd chose public | Zayd | Chat (this entry) | ACTIVE |
| D20a | 30 Oct | **Abstract chosen:** the revised ~165-word version (pixels; "neighbourhood context", not 3×3; one headline number). The headline is now 140 of 144 | Zayd liked it | Zayd | session; `abstract_options.md` | ACTIVE |
| D20b | 30 Oct | Rewrite now, in parallel with items 2–3: the sections that the remaining runs can't change. Gaps for item 2/3 results are marked and filled before anything goes to Hairong. Target: full draft Mon 2 Nov, sent to Hairong Tue 3 Nov | Timeline | Zayd/Supervisor | session | ACTIVE |
| D20c | 30 Oct | **No seed numbers in the paper** ("seed 1/2/3", "seeds 1–3"). Seed-dependent results are given as mean ± SD over three training seeds; single-seed variant screens are described as such without naming the seed | Hairong; Zayd | Zayd | session | ACTIVE |
| D20d | 30 Oct | Mazarura et al. is cited in one sentence, not given its own subsection. The "Gap" names the scientific gap (where spatial information helps); fairness is the means, not the subject | Zayd | Zayd | session | ACTIVE |
| D20e | 30 Oct | **No AI-use paragraph in the paper body** (the declaration covers it). Open: the form's clause about methodology for integral AI use | Zayd | Zayd | session | PENDING (clause) |
| D20f | 30 Oct | The baseline-reproduction figure is dropped (numbers in the text); the S³PL seed figure is kept; the S³PL gap is shortened with no information lost; a pipeline figure and the model equations are added; no freeze date | Zayd's review | Zayd | session | ACTIVE |
| D20g | 30 Oct | Epochs are **not** tuned on mSCF1, because that would select on the evaluation labels. C3 reports mSCF1 and training loss per epoch on the development sections; the loss plateau is the label-free criterion | Supervisor; Zayd asked | Supervisor | Chat | ACTIVE |

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
| D34 | 30 Oct | **Release licence, option (b):** MIT for our code (copyright Zayd Suliman). Everything that contains or imports S3PL code goes in `baselines/s3pl/` with S3PL's AGPL-3.0 `LICENSE` and the changes marked. msiPL code is not redistributed: wrappers import a user-supplied clone at `1e8d5cf`, and any patch ships as a diff with Part B of the 3D Slicer licence. The README states this in a "Licences" section. A Wits rule, if any, overrides | S3PL is AGPL-3.0; msiPL uses the 3D Slicer licence | Supervisor/Zayd | Chat 15:05, 15:06 | ACTIVE |
| D35 | 30 Oct | **Release scope: pipeline only.** After the reruns, the release includes only the scripts, `src` modules, job scripts and tests that produce the paper's tables and figures, traced back from the final summary files. Exploratory and superseded scripts stay in the private repo, and the README says so | A clean, auditable release | Supervisor/Zayd | Chat 15:06 | ACTIVE |
| D36 | 30 Oct | **Release copies are cleaned:** cluster paths become configurable roots (environment variable or arguments, documented defaults); chat, review, AI-tool and person references are removed from comments; tests cover the path handling. The regeneration check (copied scripts rebuild the tables from the copied summaries) must pass after the clean-up. The private repo is unchanged | Public repo hygiene | Supervisor/Zayd | Chat 15:06 | ACTIVE |
| D37 | 30 Oct | **IG completeness escalation beyond 256 (extends D27):** if RCC_UH0505_12 `central_only` s2 fails at 256 steps, continue doubling to 512, then 1024 (cap), with the same IG call, gate v2 and one checklist each. Only a failure at 1024 is reported as "not done (IG completeness not reached at 1024 steps)", with the residual trajectory | D10: no "not done" left in the paper; predeclared before the 256-step result | Supervisor/Zayd | Chat 15:45; P18 §6.3 escalation note | ACTIVE |
| D38 | 30 Oct | **Reproduction check before every regeneration:** before regenerating any saved table, rerun the unchanged summariser on the inputs the saved table was built from (the same root), into a scratch folder, and confirm it reproduces the saved files (line endings normalised); only then regenerate into a new folder. A mismatch is investigated and posted first | The 16:16 RCC regeneration skipped it and lost the P1 budget-sensitivity block (found 18:45) | Supervisor | Chat 19:02 | ACTIVE |

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
| D55 | 31 Oct | **Codex is the builder, runner, reviewer and committer for the remainder of the project; this supersedes D40 only.** Zayd owns every decision and the Supervisor continues to rule on scientific and protocol questions in the chat. All other ACTIVE decisions remain binding | Project-owner handoff from Code to Codex | Zayd | Session 12:29 | ACTIVE |

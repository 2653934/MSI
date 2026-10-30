# Report plan: "Spatial Aware Peak Ranking in Mass Spectrometry Imaging"

## REVISED 24 October 2026: the deadline is 2 November
**The method changes to dump → curate → write.**
1. **Dump** (24–26 Oct): everything we could say goes into Markdown files, one per section, under `report/draft/dump/`. It is extracted from the repo's sources: protocol 18, investigations 10–21, the update pack, the supervisor-chat rulings, `references.md`, the proposal and the earlier draft. Every item carries its numbers, its source path and its predeclared label. Nothing is invented.
2. **Curate** (27 Oct): Zayd and the supervisor mark every item **BODY / APPENDIX / CUT**.
3. **Write** (27–29 Oct): the curated items become LaTeX in `report/draft/sections/`. Code builds the figures and tables in parallel.
4. **Verify and send the draft** (30 Oct): the full number check, then the draft goes to the supervisor with a request for quick feedback.
5. **Revise** (31 Oct–1 Nov). **Submit 2 November.**

The chapter structure below still applies; the dates in the earlier version are superseded.

---

**Workflow:**
- The supervisor (Claude) drafts each chapter's outline, key points, numbers and figure slots.
- Zayd writes the prose.
- The supervisor reviews and verifies.
- Code builds the figures and tables from committed results and compiles the LaTeX.
- Codex checks the numbers against the files.

**Format:** LaTeX in `report/draft/` (`report.tex` plus `sections/*.tex`). The older planning files and `previous_version/` are history.

**Dates:** superseded; see the revision at the top (submission 2 November).

## Marking weights (Honours RR scheme, experimental CS)
| Component | Weight |
|---|---|
| Results | 6 |
| Methodology | 3 |
| Presentation | 3 |
| Introduction | 2 |
| Background | 2 |
| Abstract | 1 |
| Problem | 1 |
| Conclusion | 1 |
| References | 1 |

So the Results and Methodology chapters, with clean figures and tables, carry most of the marks.

## Chapters (section files)
1. **Abstract.** Context; what was done; how; the main results; the bounded contribution.
2. **Introduction** (`introduction.tex`):
   - MSI and why peak picking matters;
   - learned peak picking (msiPL, S3PL);
   - the spatial hypothesis;
   - what we did;
   - a preview of the results;
   - the structure of the report.
3. **Background and related work** (`related_work.tex`):
   - MSI data and preprocessing (TIC, binning);
   - peak picking;
   - msiPL; S3PL and IonMorphNet;
   - VAEs and representation learning for MSI (Mazarura, Jarvis & Bau 2025);
   - Integrated Gradients;
   - segment-then-correlate;
   - Moran's I and spatially aware methods (graph, ion-image level);
   - mSCF1 and its alignment with the masks.
4. **Research problem and questions** (in the intro, or its own short chapter):
   - the original RQs and hypotheses;
   - the bounded contribution;
   - the proposal-to-outcome table (`proposal_outcomes.tex`).
5. **Methodology** (`methodology.tex`):
   - the data: GBM (4 PDX lines, 8 sections), CAC (1 biopsy, 8 sections) and RCC (8 subjects), with their statistical units;
   - the models: VAE (centre-only, uniform 3×3, variants), GMM (K = classes, a class-informed disclosure), IG, posterior correlation, the simple rankings, the oracle;
   - the baselines: legacy msiPL, S3PL;
   - the evaluation: mSCF1, K_bin budgets, P1;
   - the experimental design:
     - unsupervised and transductive per section;
     - development sections (validation) vs confirmation;
     - RCC held out;
     - predeclared rules and labels;
     - seeds;
   - the statistics: exact Wilcoxon, Hodges–Lehmann CI, rank-biserial r, Holm within question families, the attainability limit, mixed models;
   - **computational considerations** (supervisor's request): the cached loader (30×, identical weights), the cluster setup, runtimes and caveats, reproducibility (bit-identity gates).
6. **Results** (`results.tex`):
   1. Baseline reproductions (msiPL on all 3 datasets; S3PL on CAC and RCC; the GBM gap).
   2. **Main result:** posterior correlation vs IG (F1 statistics; 136/140 across seeds; Test R as mean ± SD).
   3. Simple baselines and metric alignment (mean intensity, Moran's I).
   4. Spatial context in the encoder (windows, attention, masking, shuffled controls) and at segmentation (Test S).
   5. Is the encoder needed? (Test V and the reconstruction addendum.)
   6. S3PL's neighbour dependence (centre-tiled and Test N).
   7. **The S3PL GBM reproduction gap and seed sensitivity (Investigation 21 A–D).**
   8. Runtime.
7. **Discussion** (`discussion.tex`):
   - why correlation beats IG;
   - what remains of the spatial hypothesis (ranking statistic vs encoder input);
   - reconstruction ≠ ranking;
   - metric alignment;
   - the S3PL instability;
   - threats to validity (class-informed K, the RCC unannotated class, small n, post hoc choices, a single scorer).
8. **Conclusion and future work** (`conclusion.tex`).
9. **Appendices:**
   - per-seed tables;
   - the PDX-line statistics;
   - the full Section 6.6 tables;
   - the evidence map;
   - the protocol summary;
   - the AI declaration;
   - code availability.

## Reporting rules
- Seeds as mean ± SD (collection level); per-section seed SD as median (min–max); per-seed values in the appendix.
- Predeclared labels are quoted exactly. Statistics go beside the labels. "Statistically supported" only per the Section 6.6 wording rule.
- Every number traces to a committed artifact (the claim map, task 24).

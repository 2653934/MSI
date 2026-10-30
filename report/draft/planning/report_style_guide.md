# Style guide: "Spatial Aware Peak Ranking in Mass Spectrometry Imaging"

Based on how msiPL (Abdelmoula et al. 2021), S3PL (Weigand et al. 2026), Tapiwa (Mazarura et al. 2025, Wits Honours) and the RR marking scheme are written.

**Marks.** Results ×6 (30%), Methodology ×3, Presentation ×3, Introduction ×2, Background ×2, all others ×1. There is no Discussion criterion: Discussion earns marks through the Results bullets ("understanding", "limitations", "context of other research", "code availability").

> **Supervisor note (25 Oct):** the numbers in the templates below are illustrative placeholders, not our results; for example, our main finding is that correlation **beats** IG. Take real values only from `report/draft/dump/` (verified). Tapiwa is used only for format and as a list of things to avoid; don't copy its claim style.

---

## 1. Abstract (×1)

**In the papers.** One paragraph of 150–200 words, with no citations or numbers. The order is: field and problem (1–2 sentences), the gap ("existing approaches…, therefore we…"), the method in one sentence, the evaluation (what data, how judged), the headline finding, and the implication. Tapiwa states a "trade-off" result in words. S3PL claims "consistently outperforms". msiPL gives data sizes, not scores.

**Templates.**
- "*Peak selection in MSI is usually judged by …, which leaves open whether …*"
- "*We compare … against … on N sections from three public collections at a fixed, shared budget.*"
- "*In this setting, … did not outperform …; the difference was small (median Δ = …) and …*"

**Marking scheme extras.** It must be readable on its own (define MSI and IG, no section numbers) and say *how* the work was done, not only *what* was done. Include one or two concrete numbers, which none of the three papers does.

## 2. Introduction (×2)

**In the papers.** msiPL uses about 8 paragraphs with the related work folded in: the technology and why it matters → the data are large and complex → peak picking is standard but subjective → dimensionality reduction and its limits → "we propose…" → what the method does → what it was tested on. S3PL takes 6 paragraphs plus a method-overview **Table 1**, and ends with a contributions paragraph ("In this paper, we address… we introduce… Moreover, we propose…"). Tapiwa takes 6 paragraphs: the problem → the framing → the proposed answer → objective ("the central objective is not X but Y") → method and evaluation sketch → payoff.

**Templates.**
- "*Learned peak selection methods such as msiPL and S3PL rank m/z bins by …; how much of their advantage comes from … has not been tested under a common budget.*"
- "*This report asks whether …. It does not attempt …*" (scope sentence, as in Tapiwa)
- "*The main finding is that … (Section 6.2).*"
- "*Section 2 reviews …; Section 3 states …; …; Section 8 concludes.*"

**Marking scheme extras.** The Introduction must "provide the idea of the obtained results" (only S3PL does this) and "describe the structure of the document" (none of the three does). Keep the general → specific → own work order, in about 1–1.5 pages.

## 3. Background / Related work (×2)

**In the papers.** Tapiwa: themed subsections (A–D, 1–2 paragraphs each), then a **gap paragraph** ("open questions remain about … This project addresses those gaps by (a) … (b) …"). S3PL groups methods by *what information they use* (per-spectrum, ion-image, spatio-spectral) in a table, and closes with "to the best of our knowledge, there is currently no …". msiPL contrasts each family by its limitation.

**Templates.**
- "*Existing approaches fall into three groups according to whether they use spectral, spatial, or joint information.*"
- "*X addresses …, but evaluates on …, which leaves …*" (cite, then the limit, then the link to you)
- "*Of direct relevance here, … reports that …; we test whether this holds when …*"

**Marking scheme extras.** You must "relate background material to the work done by the author" and justify the report's purpose "with reference to previous work". End **every** subsection with a sentence linking it to your study. Explain IG, GMM, and the PCC-mask F1 *conceptually* here, and leave the formulas for Methodology.

## 4. Research questions (×1)

**In the papers.** None states RQs explicitly. Tapiwa's Results answer "a key research question" that was never stated, and S3PL lists contributions instead. Here you can gain marks the models don't show.

**Write it as follows.** A problem paragraph, then RQ1–RQ*n*: each one testable sentence, with its family, metric, comparison and predeclared decision rule. Add a proposal-to-outcome paragraph (what changed since the proposal, and why).

**Templates.**
- "*RQ1. Under a shared budget K, does IG ranking on a VAE+GMM pipeline recover more mask-correlated peaks than correlation ranking?*"
- "*Each RQ is answered with a paired comparison across sections, with Holm correction within its family.*"
- "*RQ3 was added after the proposal because …; it is reported as exploratory.*"

**Marking scheme extras.** "Clearly stated, adequately justified, reasonable": give each RQ a one-line justification that points to a gap named in Section 2.

## 5. Methodology (×3)

**In the papers.** S3PL: architecture → preprocessing → training (Algorithm boxes) → selection → evaluation procedure, each motivated ("Previous procedures do not …; hence we propose …"). Its datasets subsection says **why** each dataset was chosen ("all publicly available datasets that meet …") and **why** sections were excluded (duplicates, a mask that doesn't fit). Tapiwa: datasets → ordered preprocessing steps, each with a rationale → an explicit **Assumptions** list → models with exact hyperparameters → evaluation → a summary paragraph. msiPL gives exact hyperparameters inline (layers, optimiser, learning rate, batch size, epochs).

**Templates.**
- "*All methods receive the same TIC-normalised input and select the same number of bins, K, per section.*"
- "*The unit of analysis is the section, so seed results are averaged within section before testing.*"
- "*We assume …; Section 7.3 discusses the consequences if this does not hold.*"

**Marking scheme extras.** "Data identified" and "selection of data justified": give a dataset table (collection, instrument, sections, m/z bins, mask classes, source/ID) and one sentence per exclusion. Give statistics and computational cost (hardware, runtime, caching) their own subsections. Tapiwa's "to ensure a fair comparison" is worth reusing, followed by *what* was held equal.

## 6. Results (×6)

**In the papers.** msiPL has one subsection per dataset with **finding-style subheadings** ("Tumor-specific … identified in …"): setup in 1–2 sentences → fit → main observation with figure reference → detail. S3PL: main comparison (table averaged over sections + per-section figure) → exceptions named ("except for UH9610_15, where …") → qualitative case → one ablation paragraph per hyperparameter. Tapiwa: one subsection per evaluation axis ("We first assess … summarised in Table I" → reading → interpretation).

**Templates.**
- "*Table 4 reports …, averaged over the eight GBM sections (mean ± SD over seeds).*"
- "*IG exceeded correlation ranking on 5 of 8 sections (median Δ = 0.02, HL 95% CI [−0.01, 0.05], r = 0.31); the difference was not significant after Holm correction (p = 0.41).*"
- "*This pattern is consistent with …, but does not establish …*"
- "*In summary, for RQ2 …*" (close every subsection by answering its RQ)

**How to word results.**
- Report the **effect size and interval first**, then the p-value, and name the test the first time it appears.
- Name exceptions by section, as S3PL does. Write "on 6 of 8 sections", never "consistently".
- S3PL mixes "+9.3%" with "percentage points". Choose one convention and define it.
- Separate observation ("was lower") from interpretation ("suggests"). Tapiwa's "this confirms the hypothesis" turns a single-run observation into proof.
- Check that text numbers match the tables. Tapiwa's text quotes a different CNN-AE MSE from its Table I.

**Marking scheme extras** (mostly missing from the papers). Tie each result to an RQ explicitly. Put limitations *in* Results, not only in Discussion. Compare each finding with msiPL/S3PL's reported numbers ("work placed in context"). State **code availability** (repository, commit, how to rerun): both published papers do this, Tapiwa does not.

## 7. Discussion (credited via Results)

**In the papers.** S3PL uses 4 paragraphs: recap and positioning → strengths and caveats of the evaluation → a design limitation framed honestly ("not unique to our method … remains an open problem", then the evidence that bounds it) → limitations and future work. msiPL is organised by design choice (latent size, normalisation, β, spatial independence, GMM k), each with "Of note, …" and a future fix.

**Templates.**
- "*Three explanations fit this result: … We can rule out … because …; the others remain open.*"
- "*These findings are bounded by: eight sections per collection, one mask per section, and a budget fixed by ….*"

## 8. Conclusion (×1)

**In the papers.** S3PL: one 4-sentence paragraph (proposal → result → second contribution → value). Tapiwa: bolded run-in heads per finding ("Reconstruction fidelity: …"), then an over-strong "validates" close.

**Templates.** "*This report tested whether …. Under a common budget, …*" · "*The contribution is a controlled comparison, not a new method.*" · "*Future work should first …, because … remains unresolved.*"

**Marking scheme extras.** Summary, most important results, *your* contribution made explicit, and future work: 3–4 short paragraphs with no new results.

## 9. Figures and tables (Presentation ×3)

- **Figure captions** (all three sources): an opening phrase stating the content → panels "(a) … (b) …" → **one interpretive sentence** (S3PL Fig. 5: "The best patch size highly depends on the dataset"). They should stand alone: define abbreviations and say what the error bars are.
- **Table captions**: S3PL gives the metric and the averaging unit, plus a "Reproducibility Note" for deviations. Table captions go **above**, figure captions **below**.
- Reference every figure and table in the text before it appears. Bold best values only when the difference exceeds seed SD. Keep figures readable at print size and method names and colours consistent.

---

## Dos and don'ts for this report

**Negative and null results**

- **Do** state the null result plainly in the first sentence: "*IG ranking did not outperform correlation ranking at the shared budget.*" Then give the difference and its interval.
- **Do** distinguish "no evidence of a difference" from "evidence of no difference". Use the CI: "*the interval excludes gains larger than 0.05 F1, so a large advantage is unlikely in this setting.*"
- **Do** report where the result reverses (named sections, a threshold), and whether that was predeclared.
- **Do** frame a failed reproduction as a finding with a diagnosis: "*We obtained 0.30 vs the reported 0.32; most of the gap is attributable to …; … remains unexplained.*"
- **Don't** bury nulls in an appendix, rename them "comparable performance", or rescue them with a metric that wasn't predeclared. Don't write "significantly" without a test (Tapiwa and msiPL both do).

**A bounded contribution**

- **Do** write it as *what was tested, under which conditions, with what result*: "*On 24 sections from three public collections, under a shared budget and a PCC-mask reference, …*"
- **Do** use scope phrases: "in this setting", "at this budget", "for these masks", "on the GBM collection".
- **Do** say what the work is *not*: not a new peak picker, not biological validation, not a test on centroided data. Answer each RQ by name in Results and in the Conclusion, and introduce no new numbers after Results.
- **Don't** copy the source papers' universal claims ("valuable tool for any kind of MSI data", "decisive answer", "validates"). An Honours marker rewards calibration more than confidence.

**Seeds as mean ± SD**

- **Do** state the seed sets in Methodology: Test R uses training seeds 1–3; the S3PL investigation uses released seeds 1–10.
- **Do** report collection-level values as **mean ± SD across seeds of the seed-level collection means**: for each seed, average over the sections, then take the mean and SD of those n seed values (n = 3 or 10). This is the supervisor's rule (chat 20 Oct). It is *not* the SD across sections.
- **Do** report per-section seed variability as the **median (min–max) of the per-section seed SDs**. Per-seed values go in the appendix.
- **Do** say in every caption which SD it is ("*mean ± SD across 3 training seeds of the collection mean*"), and give the mean and SD to the same number of decimals.
- **Do** keep predeclared per-seed rule outcomes (for example Test R Decision 1 at CAC seed 2) beside the mean ± SD.
- **Don't** pool seed × section runs into one SD.

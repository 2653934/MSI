# Research Report Requirements and Evidence Map

## Source documents

- Official 2026 Honours research report template:
  `report/Template/report.tex`.
- 2025 Honours research report assessment scheme:
  `report/RR-marking-scheme.pdf`.

The template is the current formatting authority. The marking scheme is from
the previous year and may change, but it is sufficiently aligned with the 2026
template to guide the report plan until a newer rubric is issued.

## Mandatory format

- IEEE journal-paper layout using `IEEEtran`.
- Two columns, 10 pt font and single spacing.
- 8–12 pages excluding references.
- Abstract of 150–250 words with no citations or undefined acronyms.
- Four to six keywords.
- Sections: Introduction, Related Work, Methodology, Experiments and Results,
  Discussion, Conclusion, optional Acknowledgements, and References.
- Every table and figure must be referenced in the prose and have a
  self-contained caption.
- Results should be presented objectively in the results section; explanation,
  comparison, limitations and future work belong in the discussion.

## Mark allocation for an experimental computer science project

The rubric rates each component from 0 to 5 and multiplies it by the listed
weight. The resulting contribution to the final mark is shown below.

| Component | Rubric weight | Maximum final-mark contribution |
|---|---:|---:|
| Abstract | 1 | 5% |
| Introduction | 2 | 10% |
| Problem background | 2 | 10% |
| Research problem, hypothesis, question or purpose | 1 | 5% |
| Research methodology | 3 | 15% |
| Results | 6 | 30% |
| Conclusion | 1 | 5% |
| Presentation | 3 | 15% |
| References | 1 | 5% |
| **Total** | **20** | **100%** |

Results, methodology and presentation therefore account for 60% of the final
mark. The report must prioritise a reproducible experimental design, enough
evidence to answer the research questions, honest limitations, and concise,
legible figures rather than an oversized literature review.

## Proposed report argument

The report should not claim that neighbourhood context is universally better.
The evidence supports a more useful and defensible argument:

1. Nonlinear GMM-targeted Integrated Gradients is the robust contribution. It
   improves matched-count peak selection over legacy msiPL across all eight GBM
   and all eight CAC sections.
2. Uniform-mean neighbourhood context is dataset-dependent. It does not
   consistently improve GBM peak selection or reconstruction, but improves
   matched mSCF1 over centre-only IG on all eight CAC sections.
3. Corrected nonlinear attention improves mSCF1 over uniform mean on all three
   training seeds of the GBM108-positive development section, with a mean gain
   of +0.0204, but does not improve deletion faithfulness and costs more GPU
   memory. It therefore fails the combined predeclared gate.
4. S3PL remains the strongest executable CAC baseline at matched peak counts
   (mean mSCF1 0.5915 versus 0.5595 for uniform-context IG). Its architecture
   and ten-epoch protocol differ, so compute comparisons must remain qualified.

This argument contains positive results, negative results and a clear boundary
on what has been established. That directly serves the rubric requirements for
understanding, limitations and placement in related research.

## Working research questions

These should be finalised with the supervisor before report drafting, but the
current evidence supports the following form:

1. Does incorporating neighbourhood context into an msiPL-style VAE improve
   reconstruction, latent tissue separation or spatially structured peak
   selection compared with a matched centre-only VAE?
2. Does nonlinear Integrated Gradients provide better spatially structured
   peak rankings than legacy msiPL and a simple first-layer L2 ranking?
3. How do simple uniform context and learned attention trade off peak quality,
   attribution faithfulness, runtime and GPU memory, and are the conclusions
   stable across model-training seeds?

## Evidence mapped to report sections

### Introduction

Include:

- the scale and spatial nature of MSI data;
- why peak picking is necessary;
- the limitation of spectrum-only msiPL and the cost or reproducibility gap of
  existing spatial methods;
- the three research questions, aim, objectives and contributions;
- a short preview of the actual result, including that context is
  dataset-dependent rather than universally beneficial.

### Related Work

Organise thematically rather than paper by paper:

1. MSI preprocessing and spatially structured peak evaluation;
2. VAE-based peak learning and legacy msiPL;
3. spatial peak picking and S3PL;
4. neural attribution, Integrated Gradients and faithfulness evaluation.

End by positioning the project as a controlled study of neighbourhood context
and nonlinear attribution inside an msiPL-style VAE.

### Methodology

The section must be sufficiently detailed for reproduction and should include:

- GBM and CAC dataset provenance, section counts, spectral dimensions, mask
  classes and incomplete-grid handling;
- TIC normalisation and measured-coordinate neighbourhood construction;
- centre-only VAE, uniform-mean contextual VAE and corrected-attention VAE;
- matched architecture and training controls, 100 epochs and seeds;
- legacy msiPL and S3PL reproduction protocols;
- label-free two-component GMM in latent space;
- GMM-targeted Integrated Gradients, completeness and deletion-faithfulness
  checks;
- Pearson mask correlation, F1 at thresholds 0.3, 0.4, 0.5 and 0.6, and
  mSCF1 as their arithmetic mean;
- matched section-specific peak budgets and paired section-level comparisons;
- distinction between development-section decisions and frozen validation.

### Experiments and Results

Recommended order:

1. Baseline reproduction and data validation;
2. reconstruction comparison with centre-only controls;
3. explanation-method ablation: first-layer L2, legacy msiPL and nonlinear IG;
4. whole-GBM matched peak-selection validation;
5. frozen CAC validation and matched-count S3PL comparison;
6. targeted three-seed comparison of centre-only, uniform mean and corrected
   attention;
7. runtime, GPU-memory and attribution-cost comparison.

Report per-section observations where they matter, means with section spread,
paired directions and exact Wilcoxon results. Do not imply that eight tissue
sections are eight independent patients.

### Discussion

Explain:

- why nonlinear attribution, rather than neighbourhood input alone, is the
  strongest consistent contribution;
- why context may help CAC but not GBM;
- why better mSCF1 does not automatically mean better attribution
  faithfulness;
- why attention is retained as an informative ablation but does not pass the
  full selection gate;
- why the S3PL reproduction remains stronger on CAC and why epoch/runtime
  comparisons are not equivalent;
- limitations: seed-1 section-wide validation, three-seed testing restricted
  to one development section, section rather than patient independence,
  reproduction discrepancies, dataset-specific hyperparameters and cluster
  hardware variability;
- future work: patient-level replication, broader multi-seed validation,
  improved but constrained aggregation, automatic peak-budget selection and
  independent biological validation.

### Conclusion

Answer each research question directly, name the nonlinear attribution
contribution, state that neighbourhood value is dataset-dependent, and mention
the corrected-attention trade-off without introducing new results.

## Recommended page budget

| Material | Approximate pages |
|---|---:|
| Title, abstract and keywords | 0.5 |
| Introduction | 1.0 |
| Related Work | 1.5 |
| Methodology | 2.0–2.5 |
| Experiments and Results | 3.0–3.5 |
| Discussion | 1.0–1.5 |
| Conclusion | 0.5 |
| **Target before references** | **9.5–11.0** |

## Recommended main figures and tables

The page limit requires selection rather than including every generated plot.

Main figures:

1. Spatial-msiPL pipeline and controlled variants;
2. matched primary peak quality across GBM and CAC;
3. per-section neighbourhood-context effect;
4. explanation-method ablation;
5. targeted three-seed stability.

Main tables:

1. dataset and mask characteristics;
2. model and training controls;
3. aggregate GBM and CAC peak-selection results;
4. reconstruction, representation, faithfulness and compute trade-offs.

Detailed per-section values, additional ion images and troubleshooting evidence
should be moved to supplementary material or the repository if permitted.

## Current gaps while drafting the final report

Completed on 2026-09-22:

- a working report title, exact research questions, aim, objectives and bounded
  contributions were recorded in `Research Questions and Contributions.md`;
- a publication-quality pipeline diagram was created in SVG and PNG forms;
- the official report template was copied into a separate working structure in
  `report/final/`, and a first evidence-grounded draft was written.

Remaining work:

1. Confirm the final research-question and contribution wording with the
   supervisors.
2. Consolidate the bibliography and verify every reference entry against its
   primary publication.
3. Produce a compact hyperparameter and reproducibility table.
4. Decide whether any remaining experiment can materially change an answer to
   a research question; avoid experiments that only add volume.
5. Add the repository or code-availability statement expected by the results
   rubric.
6. Expand the current six-page framing draft to the required 8--12 pages only
   after the revised direction is confirmed with Hairong. MiKTeX compilation
   and page-by-page visual inspection succeeded on 2026-09-22.

## Rubric-specific final checks

- Abstract independently states context, problem, method, principal numbers
  and conclusion.
- Introduction previews the obtained result and outlines the paper.
- Background synthesises literature and explicitly justifies this work.
- Research questions are measurable and answered in the conclusion.
- Methodology justifies data selection and every major design control.
- Results are sufficient, readable, tied to the questions and accompanied by
  limitations and code availability.
- Figures remain legible at IEEE column width; captions explain the takeaway.
- Tables use consistent precision and identify whether spread is across
  sections or training seeds.
- References are complete, accurate and consistently formatted.
- No red instructional text or placeholder figures remain in the final TeX.

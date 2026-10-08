# Supervisor Review Response and Report Completion Plan

Date: 8 October 2026

## Bottom line

The review is largely fair. Its central criticism is not that the project lacks experiments; it is that the final report does not yet faithfully represent, connect, and qualify the evidence already produced.

One recency caution matters: the review inspected `C:\Users\zayds\Documents\MSI`, whereas the active repository is `C:\Users\zayds\Documents\Research\MSI`. Several items described as unfinished in the review have since been completed. The active report nevertheless confirms the main writing and traceability problems.

## Criticism triage

| Review point | Verdict | Evidence or interpretation | Required response |
|---|---|---|---|
| The report is behind the experiments | Fair and urgent | The current PDF is six pages including references, while the rubric expects 8–12 pages excluding references. The abstract and results still use the older GBM values 0.3643 and 0.4562 instead of the corrected tuned-count evidence. | Rebuild the report from the claim ledger and frozen result tables before conducting optional experiments. |
| Proposal commitments and delivered work are not traced explicitly | Fair | Poisson augmentation, a spatial coherence penalty, Bayesian optimisation and MALDIquant appear in the proposal, but their eventual status is not explained together in the report. | Add a proposal-to-outcome table: delivered, modified, tested but not retained, deferred, or not completed, with a reason for each change. |
| The original combined spatial-penalty-plus-augmentation question was not fully answered | Fair | The components were investigated separately and the project evolved toward controlled spatial-context and attribution studies. | State this as a methodological deviation and limitation. Do not imply that the exact original combined intervention was exhaustively tested. |
| Bayesian optimisation and MALDIquant are missing | Fair as a disclosure issue; not automatically a reason for new runs | They were proposal commitments, but completing them now may not change the central thesis. | Document the deviation honestly. Run them only if Hairong or the rubric treats them as mandatory, or if report synthesis shows that they would change the main conclusion. |
| First-layer L2 was displaced by GMM-targeted IG without enough rationale | Fair | The repository contains the empirical rationale, but it is scattered. | Write a short decision chain: first-layer L2 was weak; GMM represents the latent separation target; IG attributes that target back to spectral bins; subsequent controls tested whether the ranking was meaningful and spatially specific. |
| Validation and runtime work are unfinished | Outdated | All 21 remaining GBM seed runs, the stability synthesis, and three native 160TopL runtime measurements are complete. | Cite the completed synthesis and update the report; do not rerun them. |
| GBM sections are not independent patients | Fair | Eight sections come from four patients. Current text mentions this, but the headline presentation is section based. | Add patient-grouped summaries and show section points nested by patient. Avoid inferential claims that treat eight sections as eight independent patients. |
| Biological language is too strong | Fair | PCC/mSCF1 against masks measures spatial agreement, not molecular identity, biomarker validity or stochastic noise. | Replace biological-discovery language with spatial-agreement and expert-mask language. State what would require identification or external biological validation. |
| “Lightweight” is undefined | Fair | The contextual VAE can be large in parameter count, while measured wall time and sampled memory are only modestly lower in the native workflow comparison. | Report parameters, wall time, CPU time, RSS and sampled GPU memory separately. Use “lighter” only with the named metric and comparator. |
| The IG formula does not match the code | Fair and concrete | The code uses trapezoidal integration, whereas the report currently presents a right-endpoint approximation. | Correct the equation and cite the implementation. |
| S3PL thresholding is described too simply | Fair and concrete | The implementation converts the PCC threshold to the nearest point in the ranked correlation list and therefore uses a rank cutoff; it is not always a literal `r >= threshold` filter. | Describe the actual nearest-threshold rank rule and retain the raw-spectrum scoring audit as validation. |
| The GBM-positive mechanism is “understood” | Too strong | The experiments identify weight initialisation and short-training transience as important causes, but not every internal cause of variability or the entire reproduction gap. | Say “an important source of instability was identified and bounded.” |
| The centre-tiled S3PL control proves beneficial spatial information | Needs qualification | Centre tiling removes real neighbours but also creates a harder training/input condition. Its large score drop supports context dependence, not a clean estimate of spatial benefit alone. | Present it beside frozen topology and seed controls, with the harder-task caveat. |
| More literature synthesis is needed | Fair | Results now need to be interpreted through spatial scale, tissue-boundary mixing, spatial autocorrelation, convolutional inductive bias, attribution limits and the distinction between spatial agreement and biological identity. | Perform a targeted literature pass during report writing; do not use it to open an unbounded new model campaign. |

## Agreed contribution to write toward

The defensible contribution is a controlled empirical study of how neighbourhood construction, learned attention, attribution choice, training instability and evaluation design affect unsupervised MSI peak selection across CAC and GBM sections. The project contributes:

1. an audited comparison of legacy msiPL, centre-only VAE attribution, fixed contextual VAE attribution and S3PL;
2. controlled spatial-context ablations, including window size, zero/shuffled context, attention input/ranking swaps and S3PL centre/topology controls;
3. evidence that simple neighbourhood context does not provide a consistent collection-wide peak-selection gain in this implementation;
4. evidence that S3PL depends on neighbourhood content on CAC but is highly initialization-sensitive under the ten-epoch GBM protocol;
5. a reproducible evaluation and resource-accounting workflow with explicit limitations.

This is a valid research outcome even though it is not the originally hoped-for universal improvement.

## Tomorrow's plan

### 1. Freeze the evidence boundary

- Treat the current audited result folders and claim ledger as authoritative.
- Do not launch RCC, MALDIquant, Bayesian optimisation, 7×7/9×9 windows or another model variant by default.
- Permit a new run only when it can change a principal conclusion, repair a verified defect, or satisfy an explicit assessment requirement.

### 2. Repair scientific accuracy first

- Replace the stale abstract and results values with the corrected tuned-count results.
- Correct the IG equation to trapezoidal integration.
- Describe S3PL's nearest-threshold rank cutoff accurately.
- Change “mechanism understood” to the bounded instability claim.
- Qualify the centre-tiled control and all biological language.

### 3. Add proposal-to-outcome traceability

Create one table covering every proposed objective and method:

- implemented as proposed;
- implemented with a justified modification;
- tested but not retained;
- deferred or incomplete;
- evidence and reason.

Poisson augmentation, the spatial coherence penalty, Bayesian optimisation, MALDIquant, first-layer L2, GMM-targeted IG and the raw-data adapters must all appear.

### 4. Rebuild the results presentation

- Create the authoritative method-by-dataset table from the audited source files.
- Add patient-grouped GBM summaries alongside section-level points.
- Add the S3PL seed-stability and native-runtime figures.
- Separate development sections, confirmation sections and diagnostic controls visually and in captions.
- Never use section variation as if it were patient-level replication.

### 5. Rewrite the report around claims, not chronology

1. Problem and research questions.
2. Methods and exact implementation.
3. Proposal deviations and why they occurred.
4. Main quality results.
5. Spatial-context and attribution ablations.
6. S3PL reproduction, stability and computational findings.
7. Limitations, including patient grouping, outcome-known development sections and biological interpretation.
8. Bounded conclusion and future work.

The next compiled draft must meet the rubric length range without padding; figures, tables and interpretation should provide the added substance.

### 6. Targeted literature pass

Search only for literature needed to interpret the observed results:

- spatial scale and neighbourhood choice in MSI;
- tissue-boundary mixing and spatial smoothing;
- convolutional versus pooled/dense spatial representations;
- spatial autocorrelation baselines;
- limits of attribution and mask agreement as evidence of biological relevance.

### 7. Final audit

- Every numeric claim maps to an authoritative artifact.
- Every equation matches the code.
- Every comparison states its peak budget, seed, epoch protocol and evaluation rule.
- Every efficiency claim names the measured resource.
- Every limitation is visible near the corresponding result.
- The abstract, results, discussion and conclusion agree.

## Stopping rule

The project now prioritises synthesis over exploration. A new experiment is justified only if at least one of these is true:

1. it repairs a demonstrated implementation or scoring defect;
2. it tests a thesis-changing ambiguity that cannot be answered from saved artifacts;
3. it is explicitly required by the rubric or Hairong;
4. it is small, predeclared and has a clear decision rule.

Otherwise, record it as future work. A well-supported negative or mixed result is preferable to an unfinished collection of extra experiments.

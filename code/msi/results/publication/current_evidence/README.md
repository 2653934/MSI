# Current publication results

This package summarizes the completed seed-1 model campaign. Section-level
variation is shown explicitly; training-seed stability remains a planned targeted
analysis. All primary method comparisons below use matched section-specific peak
budgets.

## Primary result

Nonlinear Integrated Gradients improves peak selection over legacy msiPL across
both collections. Uniform-mean context has a dataset-dependent contribution: it
does not consistently improve GBM mSCF1, but improves all eight CAC sections.

### GBM

| Method | Mean mSCF1 | Section SD | Median |
|---|---:|---:|---:|
| Legacy msiPL | 0.3643 | 0.0749 | 0.3809 |
| Centre-only IG | 0.4665 | 0.0820 | 0.4935 |
| Uniform-context IG | 0.4562 | 0.0898 | 0.4743 |

- Uniform-context IG versus centre-only IG: mean change -0.0103; wins 5/8; paired exact Wilcoxon p=0.945312.
- Uniform-context IG versus legacy msiPL: mean change +0.0919; wins 8/8; p=0.007812.

### CAC

| Method | Mean mSCF1 | Section SD | Median |
|---|---:|---:|---:|
| Legacy msiPL | 0.4024 | 0.0688 | 0.3999 |
| Centre-only IG | 0.5285 | 0.1205 | 0.5308 |
| Uniform-context IG | 0.5595 | 0.1253 | 0.5866 |

- Uniform-context IG versus centre-only IG: mean change +0.0310; wins 8/8; p=0.007812.
- Uniform-context IG versus legacy msiPL: mean change +0.1572; wins 8/8; p=0.007812.

## S3PL placement

S3PL is retained as a contextual CAC benchmark, not included in the matched primary
test. It used its own selected peak counts and a 10-epoch implementation protocol.
Its mean CAC mSCF1 was 0.5908, versus 0.5595 for uniform-context IG.

## Interpretation boundaries

- The neighbourhood conclusion currently concerns uniform-mean context, not all
  possible learned neighbourhood aggregators.
- First-layer L2 is an intentionally simple weight-magnitude comparator, not a
  reimplementation of legacy LearnPeaks.
- Full GBM and CAC validation currently uses one model-training seed. Attribution
  sampling stability was tested separately; targeted model-seed repeats are pending.
- The eight sections within a collection are paired section-level units and are not
  asserted to be eight independent patients.

## Figures

1. `figure_1_primary_peak_quality.png` — matched primary comparison.
2. `figure_2_context_effect_by_section.png` — section-level context contribution.
3. `figure_3_explanation_ablation.png` — L2, legacy msiPL, and nonlinear IG.
4. `figure_s1_s3pl_contextual_cac.png` — separate contextual S3PL comparison.

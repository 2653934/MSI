# Current publication results

This package summarizes the completed seed-1 section-wide model campaign and
the targeted three-seed stability experiment. All primary method comparisons
below use matched section-specific peak budgets.

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

S3PL is retained as a separate CAC architecture benchmark. Its existing checkpoints
were re-evaluated with the same section-specific peak counts as the primary methods;
its training protocol remains the reproduced 10-epoch S3PL protocol.
Its mean CAC mSCF1 was 0.5915, versus 0.5595 for uniform-context IG.

## Targeted training-seed stability

On GBM108-positive, centre-only, uniform-mean and corrected-attention models
were independently trained with seeds 1, 2 and 3. Evaluation randomness and
the 530-peak budget were fixed. Mean mSCF1 was 0.5120 for centre-only, 0.5250
for uniform mean and 0.5454 for corrected attention.

Corrected attention beat uniform mean in all three seeds and improved mSCF1 by
+0.0204 on average. It nevertheless failed the combined predeclared gate
because mean deletion faithfulness changed by -0.0045. The result supports a
small peak-quality benefit on this development section, not a claim of more
faithful explanations or whole-dataset multi-seed superiority.

## Interpretation boundaries

- The neighbourhood conclusion currently concerns uniform-mean context, not all
  possible learned neighbourhood aggregators.
- First-layer L2 is an intentionally simple weight-magnitude comparator, not a
  reimplementation of legacy LearnPeaks.
- Full GBM and CAC section-wide validation uses seed 1. The three-seed analysis
  is deliberately restricted to the GBM108-positive development section.
- The eight sections within a collection are paired section-level units and are not
  asserted to be eight independent patients.

## Figures

1. `figure_1_primary_peak_quality.png` — matched primary comparison.
2. `figure_2_context_effect_by_section.png` — section-level context contribution.
3. `figure_3_explanation_ablation.png` — L2, legacy msiPL, and nonlinear IG.
4. `figure_s1_s3pl_contextual_cac.png` — matched-count S3PL architecture comparison.
5. `figure_4_seed_stability.png` — targeted model-training seed stability.

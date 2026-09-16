# Spatial-msiPL research status — 16 September 2026

## Research question

Determine whether spatial-neighbourhood context and nonlinear peak attribution improve MSI peak learning over a centre-only VAE, legacy msiPL first-layer peak selection, and S3PL.

## Data in scope

- MassNet GBM: eight tumour/normal tissue sections.
- CAC: eight three-class tissue sections.
- All published baseline sections have been processed. `GBM108_positive` is the development section for the new Spatial-msiPL method; the other sections are the next validation stage.

## Completed foundations

- The MassNet GBM masks, CAC masks, coordinate alignment, coverage, HDF5 adapters and visualisations were checked.
- S3PL was run across all GBM and CAC sections.
- The paper-aligned legacy msiPL reproduction was completed across both datasets. Mean mSCF1 was 0.4142 for GBM versus 0.403 reported by Weigand, and 0.4024 for CAC versus 0.431 reported. Both reproduced means fall inside the paper's published 95% intervals; this is descriptive agreement, not an equivalence claim.
- A centre-only VAE control and contextual models completed 100 matched epochs on `GBM108_positive`.

## Development-section model findings

- Centre-only reconstruction was better than every contextual variant on `GBM108_positive`: TIC-MSE was 5.683e-9, while contextual variants were approximately 15.3–16.2% worse and used approximately 50% more parameters.
- Uniform mean, depthwise aggregation, original attention and corrected `sqrt(D)` attention were compared. Learned variants did not demonstrate a material, consistent advantage over uniform mean.
- Original attention was found to saturate because it scaled scores by the full 85,062-bin spectral dimension. The corrected `sqrt(D)` version learned non-uniform weights but still did not beat uniform mean.
- Spatial-loss pilots mechanically smoothed adjacent latent representations but did not improve the broader reconstruction or representation criteria. Lambda 0 was retained.
- Poisson augmentation passed its implementation checks but failed the predeclared improvement gate. Augmentation remains off.
- Decision: retain the simplest uniform-mean contextual model with lambda 0 and no Poisson augmentation.

## Nonlinear attribution

The retained 100-epoch model is interpreted using Integrated Gradients of the assigned GMM component posterior. This follows the complete nonlinear encoder, unlike first-layer weight magnitude.

The pilot used:

- two-component GMM with seed 1;
- 12 attribution pixels per component;
- 64 trapezoidal Integrated-Gradients steps;
- section-mean TIC-normalised baseline;
- separate central and neighbourhood-context attribution;
- combined score `|central IG| + sum(|valid-neighbour IG|)` per m/z bin;
- disjoint held-out deletion tests;
- component-balanced selection of exactly 530 bins to match legacy msiPL.

The differentiable PyTorch posterior matched scikit-learn to within 7.15e-7. Integrated-Gradients completeness passed, and deletion of attributed bins caused substantially larger posterior changes than random or first-layer-L2 selections at the main deletion budgets.

## Development-section peak quality

Matched 530-bin mSCF1 on `GBM108_positive`:

| Method | mSCF1 |
|---|---:|
| Legacy msiPL | 0.4042 |
| GMM Integrated Gradients | 0.5277 |
| First-layer L2 | 0.0682 |

Integrated Gradients improved over legacy msiPL by 0.1235 absolute, approximately 30.6% relative, and won at every PCC threshold from 0.3 to 0.6. It shared 300 of 530 bins with legacy msiPL, whereas first-layer L2 shared only 15. GMM-to-expert mapping reached 90.15% accuracy, 89.28% balanced accuracy and ARI 0.6443. Expert labels were used only after clustering for evaluation and display.

## Attribution-sampling stability

The model and GMM were fixed while only the attribution-pixel sampling seed changed:

| Sampling seed | mSCF1 |
|---|---:|
| 1, pre-specified | 0.5277 |
| 2 | 0.5169 |
| 3 | 0.5479 |
| 4 | 0.5401 |
| Mean ± sample SD | 0.5331 ± 0.0137 |

- Pairwise Jaccard similarity for the 530-bin sets was 0.782–0.860.
- Pairwise overlap was 465–490 bins.
- 436 of 530 bins appeared in every run.
- 492 of 530 appeared in at least three of four runs.
- All repeats passed completeness and the 35-test cluster suite.

Conclusion: the mSCF1 improvement and broad peak set are robust to the sampled attribution pixels. The pre-specified seed-1 result is retained to avoid choosing the best result after inspection.

## Frozen method and limitations

For validation, freeze the uniform-mean model, 100 epochs, lambda 0, augmentation off, model/GMM seed 1, sampling seed 1, 12 attribution pixels per component, 64 IG steps, centre-plus-context absolute aggregation, and component-balanced matched-count evaluation.

The positive attribution result is still based on one development section and one trained model seed. It is not yet evidence of whole-dataset generalisation. The smallest 32-bin deletion effect was weak for one GMM component in some sampling repeats; claims should focus on the broader ranked set rather than every top individual ion.

## Next stage

1. Generalise the restartable training and evaluation scripts to the remaining seven MassNet GBM sections.
2. Run the frozen uniform-mean spatial VAE and matched centre-only VAE independently per section.
3. Run GMM Integrated Gradients and matched peak evaluation per section.
4. Aggregate reconstruction, clustering, mSCF1, uncertainty, runtime and memory across all eight GBM sections.
5. Generalise the locked pipeline to the eight three-class CAC sections and produce the same dataset-level comparison.
6. Finish combined figures, statistical comparisons, limitations and the report.

The working completion target remains four weeks. Whole-dataset validation, not further tuning on `GBM108_positive`, is now the priority.

# Current Status and Next Steps

Last updated: 2026-09-24

## Completed

- CAC and GBM inspection, masks and visualisation.
- Legacy msiPL reproduction on both collections.
- S3PL CAC runs and documented MassNet GBM reproduction gap.
- Spatial-msiPL preprocessing, model and tests.
- Uniform mean frozen as the neighbourhood method.
- Whole-GBM uniform-mean and centre-only 100-epoch training.
- Whole-GBM reconstruction comparison: mixed 4-4 MSE split.
- Whole-GBM nonlinear peak attribution and matched evaluation.
- Matched centre-only IG control across all eight GBM sections.
- Matched 100-epoch uniform-mean and centre-only training on all eight CAC
  sections.
- Frozen CAC reconstruction, clustering, Integrated Gradients, L2 and
  matched-count peak evaluation.

## Whole-GBM attribution result

At the tuned, paper-aligned section-specific peak counts, uniform-context
Integrated Gradients achieved mean mSCF1 0.5111 versus 0.4142 for legacy
msiPL and won on all eight sections. Mean gain was 0.0969 mSCF1; paired
section-level Wilcoxon `p = 0.0078125`. Centre-only IG averaged 0.5178 and
also beat tuned msiPL in all eight sections. Uniform first-layer L2 averaged
0.2193 and lost to uniform IG on seven of eight sections.

This supports nonlinear attribution as a peak-ranking method. The completed
centre-only control now separates that gain from the neighbourhood mechanism.

## Completed decision: neighbourhood context versus nonlinear attribution

The frozen centre-only control held constant:

- section and preprocessing;
- seed and trained duration;
- hidden and latent dimensions;
- GMM components, initialisations and seed;
- IG baseline, integration steps and sampled pixels;
- section-specific matched peak count and PCC evaluation.

The intended difference was only the encoder input. Centre-only IG averaged
0.5178 mSCF1 versus 0.5111 for spatial IG. Spatial won five sections and
centre-only won three, but the mean paired change was -0.0067 and the exact
Wilcoxon result was `p = 1.0`. There is no consistent GBM peak-selection
advantage from neighbourhood context.

Centre-only IG beat tuned legacy msiPL on all eight sections, with mean gain
0.1036 and paired `p = 0.0078125`. The defensible conclusion is that nonlinear
IG is the robust peak-selection contribution. The centre/context peak sets
shared 73.8% of selected bins on average (mean Jaccard 0.590), so context did
change a meaningful minority of peak identities without consistently improving
their GBM mSCF1.

## Frozen CAC result

Spatial IG averaged 0.5595 mSCF1 versus 0.5285 for centre-only IG and won all
eight paired CAC sections. The mean paired gain was 0.0310 and the exact
Wilcoxon result was `p = 0.0078125`. Spatial IG also beat legacy msiPL on all
eight sections, averaging 0.1572 higher mSCF1 (`p = 0.0078125`).

The result is specific rather than universal: reconstruction MSE split 4-4,
and centre-only had slightly higher mean GMM balanced accuracy. Context helped
the nonlinear peak-ranking objective on CAC, not every representation metric.
Centre-only and uniform-context rankings shared 78.6% of selected CAC bins on
average (mean Jaccard 0.648). Thus the consistent CAC gain came from a targeted
minority of peak substitutions rather than a wholly different peak list.
Matched-count S3PL averaged 0.5915 versus 0.5595 for uniform-context IG. S3PL
remains a secondary architecture benchmark because its model and 10-epoch
training protocol differ from the 100-epoch dense VAE protocol.

## Current priority: cross-dataset synthesis and writing

The frozen validation campaign is complete. The next work is to turn the GBM
and CAC evidence into dissertation-ready methods, results and discussion,
including the interaction between dataset and context, computational tradeoffs,
limitations and the distinction between nonlinear attribution and spatial
neighbourhood input.

## Remaining sequence

```text
GBM and CAC frozen validation complete
  -> cross-dataset synthesis and final figures
  -> limitations and computational comparison
  -> dissertation-ready methods, results and discussion
```

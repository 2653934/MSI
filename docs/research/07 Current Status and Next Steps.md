# Current Status and Next Steps

Last updated: 2026-09-21

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

## Whole-GBM attribution result

Spatial-msiPL Integrated Gradients achieved mean mSCF1 0.4562 versus 0.3643
for legacy msiPL and won on all eight sections. Mean gain was 0.0919 mSCF1;
paired section-level Wilcoxon `p = 0.0078125`. First-layer L2 averaged 0.2139
and lost to IG on seven of eight sections. Mean GMM balanced accuracy was
0.9113, and all attribution completeness checks passed.

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
0.4665 mSCF1 versus 0.4562 for spatial IG. Spatial won five sections and
centre-only won three, but the mean paired change was -0.0103 and the exact
Wilcoxon result was `p = 0.9453125`. There is no consistent peak-selection
advantage from neighbourhood context.

Centre-only IG beat legacy msiPL on all eight sections, with mean gain 0.1022
and paired `p = 0.0078125`. The defensible conclusion is that nonlinear IG is
the robust peak-selection contribution. Spatial context may still improve
latent tissue organisation: mean GMM balanced accuracy was 0.9113 for spatial
models versus 0.8676 for centre-only models. That possible representation
benefit did not translate into consistently better mSCF1.

## Current priority: frozen CAC validation

The GBM architecture-versus-explanation question is now closed. The next stage
is to apply the locked analysis to CAC without retuning the method in response
to individual sections. This supplies the cross-dataset validation required
before final synthesis.

Do not add a Spatial LearnPeaks adaptation unless CAC exposes a specific
unresolved methodological question that justifies it.

## Remaining sequence

```text
GBM centre-only IG control complete
  -> frozen CAC validation
  -> cross-dataset synthesis
  -> dissertation-ready methods, results and discussion
```

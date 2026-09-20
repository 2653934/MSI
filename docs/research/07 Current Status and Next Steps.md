# Current Status and Next Steps

Last updated: 2026-09-20

## Completed

- CAC and GBM inspection, masks and visualisation.
- Legacy msiPL reproduction on both collections.
- S3PL CAC runs and documented MassNet GBM reproduction gap.
- Spatial-msiPL preprocessing, model and tests.
- Uniform mean frozen as the neighbourhood method.
- Whole-GBM uniform-mean and centre-only 100-epoch training.
- Whole-GBM reconstruction comparison: mixed 4-4 MSE split.
- Whole-GBM nonlinear peak attribution and matched evaluation.

## Whole-GBM attribution result

Spatial-msiPL Integrated Gradients achieved mean mSCF1 0.4562 versus 0.3643
for legacy msiPL and won on all eight sections. Mean gain was 0.0919 mSCF1;
paired section-level Wilcoxon `p = 0.0078125`. First-layer L2 averaged 0.2139
and lost to IG on seven of eight sections. Mean GMM balanced accuracy was
0.9113, and all attribution completeness checks passed.

This supports nonlinear attribution as a peak-ranking method. It does not yet
isolate whether neighbourhood context adds value because the legacy comparison
changes both model architecture and explanation method.

## Running now: matched centre-only IG control

Use the frozen 100-epoch centre-only checkpoints. No retraining is required.
The control holds constant:

- section and preprocessing;
- seed and trained duration;
- hidden and latent dimensions;
- GMM components, initialisations and seed;
- IG baseline, integration steps and sampled pixels;
- section-specific matched peak count and PCC evaluation.

The intended difference is only the encoder input: centre spectrum alone versus
centre plus uniform-mean neighbourhood context.

The `GBM108_negative` canary completed and passed all 37 tests and IG
completeness. Centre-only IG achieved mSCF1 0.5321 versus 0.5400 for spatial IG,
0.4571 for legacy msiPL and 0.1142 for centre-only first-layer L2. Spatial
context therefore added 0.0079 mSCF1 (1.5%) on this section, while nonlinear IG
accounted for most of the gain over legacy msiPL.

The remaining seven controls are submitted as jobs `57245`-`57257`. Summary
job `57258` waits for their gates and will report spatial IG minus centre-only
IG, centre-only IG minus legacy msiPL, win/loss counts and paired tests.

## Decision after the control

- If spatial IG consistently beats centre-only IG, neighbourhood context has
  evidence of added peak-selection value even though reconstruction was mixed.
- If the results are tied or heterogeneous, IG is still useful but context is
  not consistently beneficial for peak selection.
- If centre-only IG wins, the nonlinear explanation method rather than spatial
  context is the likely source of improvement.

Do not add a Spatial LearnPeaks adaptation unless the centre-only result leaves
a specific unresolved question that justifies it.

## Remaining sequence

```text
centre-only IG canary complete
  -> seven remaining centre-only IG sections queued
  -> aggregate context-control result
  -> frozen CAC validation
  -> cross-dataset synthesis
  -> dissertation-ready methods, results and discussion
```

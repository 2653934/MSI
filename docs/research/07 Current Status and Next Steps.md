# Current Status and Next Steps

Last updated: 2026-10-05

The [main results record](01%20Results%20Record.md) now includes the cached
GBM training result, the S3PL versus cached-VAE phase probe, and the CAC
reference-set/selected-peak diagnosis. Their figures are collected in the
[local results gallery](../../results/README.md). The current work is the
[two-week spatial investigation](09%20Two-Week%20Spatial%20Model%20Investigation%20Plan.md).
The 1x1/3x3/5x5 window implementation and context-control tests passed; the
seed-1 window campaign now has complete local training and evaluation
artifacts for all 48 new configurations. The [results record](01%20Results%20Record.md#spatial-window-and-context-controls-3-october-2026)
compares the real 5x5, zero-context 3x3 and shuffled-context 3x3 arms with
the frozen real 3x3 reference. Across the seven GBM confirmation sections,
the respective mean IG mSCF1 values are 0.4334, 0.4594, 0.4430 and 0.4460;
across the seven CAC confirmation sections they are 0.5352, 0.5235, 0.5425
and 0.5419. The larger window does not restore a consistent spatial gain,
and real versus shuffled context is close on average. These are descriptive
seed-1 results, not a final mechanism explanation.

## Direction after Hairong's 28 September meeting

Hairong asked for a stronger investigation before treating the mixed spatial
effect as a settled conclusion or presenting GMM-targeted IG as a replacement
research direction. The next two weeks prioritise an implementation and
evaluation audit, 1×1/3×3/5×5 neighbourhood tests with capacity and spatial
controls, and a measured explanation of the CAC S3PL quality/runtime gap.
The detailed sequence, acceptance checks and evidence requirements are in
[the two-week investigation plan](09%20Two-Week%20Spatial%20Model%20Investigation%20Plan.md).

The results below remain observations from the existing runs. The earlier
writing-first sequence is superseded by the investigation plan until these
checks establish which model claims survive.

## Completed

- CAC and GBM inspection, masks and visualisation.
- Legacy msiPL reproduction on both collections.
- S3PL CAC runs and documented MassNet GBM reproduction gap.
- Spatial-msiPL preprocessing, model and tests.
- Uniform mean frozen as the simple neighbourhood *baseline/control* for the
  initial comparison; the 48-arm campaign did not establish it as the final
  spatial method.
- Whole-GBM uniform-mean and centre-only 100-epoch training.
- Whole-GBM reconstruction comparison: mixed 4-4 MSE split.
- Whole-GBM nonlinear peak attribution and matched evaluation.
- Matched centre-only IG control across all eight GBM sections.
- Matched 100-epoch uniform-mean and centre-only training on all eight CAC
  sections.
- Frozen CAC reconstruction, clustering, Integrated Gradients, L2 and
  matched-count peak evaluation.
- Complete seed-1 CAC and GBM 5x5/zero/shuffled window campaign (48/48
  configurations), with local training, reconstruction, attribution and
  matched-count peak-evaluation artifacts audited.
- Valid post-hoc real-versus-shuffled input-information audits on two CAC and
  two GBM sections, plus frozen-model context-swap sensitivity checks on
  `160TopL` and `GBM22_2`; see the
  [results record](01%20Results%20Record.md#what-the-shuffled-input-changes-and-whether-frozen-models-respond).
- Saved-latent separability audit on `160TopL` and `GBM22_2`: expert-class
  information is accessible to a post-hoc label-trained probe in both real
  and shuffled models, while the label-free GMM gives different partitions;
  see the [results record](01%20Results%20Record.md#saved-latent-information-versus-the-fitted-gmm).
- Frozen-latent covariance/KMeans audit completed without expert-label
  selection; full GMM remained the BIC choice, while a different covariance
  assumption could change post-hoc class agreement.
- Real-versus-shuffled learned-attention training and matched-count evaluation
  completed on `160TopL` and `GBM22_2`. The mSCF1 differences are small and
  opposite in sign; see the
  [results record](01%20Results%20Record.md#targeted-learned-attention-context-check-4-october-2026).
- Frozen attention IG contribution-ranking ablation completed on both
  sections: combined-score reproduction passed, and real-neighbour-only
  rankings beat shuffled-neighbour-only rankings, but combined scores remain
  mixed. See the
  [results record](01%20Results%20Record.md#frozen-attention-integrated-gradients-contribution-ablation).
- Frozen same-checkpoint learned-attention input swap completed on all 16
  sections with a fixed real-input GMM: reconstruction MSE increased after
  shuffling in every section (1.36–3.38 times), and mean fixed-GMM label
  flips were 4.27% CAC and 8.48% GBM. This shows input sensitivity, not
  improved peak selection; no IG or mSCF1 was recomputed. See the
  [results record](01%20Results%20Record.md#frozen-learned-attention-neighbour-input-swap-5-october-2026).

## Immediate next step

Interpret the completed same-checkpoint swap alongside the centre/neighbour
IG ablation: neighbour input affects reconstruction and fitted components,
but the swap does not test peak-ranking benefit and may be out of
distribution. Before making a spatial-specific peak-quality claim, run a
bounded topology or ranking counterfactual with a predeclared comparison;
target-choice controls may follow if that remains unresolved. Keep the S3PL
protocol/runtime gap investigation separate. Any promising peak-quality gain
still needs targeted training-seed confirmation.

The RCC third-dataset option is intentionally parked. The cluster archive was
transferred, SHA-256 verified and found to contain `rcc.rda`, but the
[archive-audit log](../../code/msi/logs/rcc-audit-63930.out) shows Cardinal is
not available on the compute node, so the dataset-content audit did not run.
Its available labels are coarse for the current section-level peak-scoring
protocol. Do not treat RCC as a ready validation cohort or divert the present
attention diagnostic to an unvalidated third-dataset run.

## Whole-GBM attribution result

At the tuned, paper-aligned section-specific peak counts, uniform-context
Integrated Gradients achieved mean mSCF1 0.5111 versus 0.4142 for legacy
msiPL and won on all eight sections. Mean gain was 0.0969 mSCF1; paired
section-level Wilcoxon `p = 0.0078125`. Centre-only IG averaged 0.5178 and
also beat tuned msiPL in all eight sections. Uniform first-layer L2 averaged
0.2193 and lost to uniform IG on seven of eight sections.

This supports nonlinear attribution as a peak-ranking method within the tested
models. The centre-only result shows that neighbouring spectra are not required
for the observed improvement, but comparison with legacy msiPL also changes
the model and pipeline; attribution alone is not isolated as its sole cause.

## Completed decision: neighbourhood context versus nonlinear attribution

The frozen centre-only control held constant:

- section and preprocessing;
- seed and trained duration;
- hidden and latent dimensions;
- GMM components, initialisations and seed;
- IG baseline, integration steps and sampled pixels;
- section-specific matched peak count and PCC evaluation.

The intended change was access to context; the contextual model also has a
wider first encoder layer and more parameters. Centre-only IG averaged
0.5178 mSCF1 versus 0.5111 for spatial IG. Spatial won five sections and
centre-only won three, but the mean paired change was -0.0067 and the exact
Wilcoxon result was `p = 1.0`. There is no consistent GBM peak-selection
advantage from neighbourhood context.

Centre-only IG beat tuned legacy msiPL on all eight sections, with mean gain
0.1036 and paired `p = 0.0078125`. This is a strong observed pipeline result,
while the relative contribution of architecture and attribution needs the
audits in the new plan. The centre/context peak sets
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
minority of peak differences rather than a wholly different peak list; this
comparison does not identify which particular substitutions caused the gain.
Matched-count S3PL averaged 0.5915 versus 0.5595 for uniform-context IG. S3PL
remains a secondary architecture benchmark because its model and 10-epoch
training protocol differ from the 100-epoch dense VAE protocol.

## Previous priority (24 September): cross-dataset synthesis and writing

The frozen validation campaign is complete. The next work is to turn the GBM
and CAC evidence into dissertation-ready methods, results and discussion,
including the interaction between dataset and context, computational tradeoffs,
limitations and the distinction between nonlinear attribution and spatial
neighbourhood input.

## Previous remaining sequence (superseded on 28 September)

```text
GBM and CAC frozen validation complete
  -> cross-dataset synthesis and final figures
  -> limitations and computational comparison
  -> dissertation-ready methods, results and discussion
```

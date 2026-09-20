# Metrics and Statistics

## PCC: Pearson correlation coefficient

For one m/z bin, form an ion image containing that bin’s intensity at every
measured pixel. Form a binary mask vector for one tissue class. PCC measures
their centred linear association:

```text
r = sum((mask - mean(mask)) × (ion - mean(ion)))
    / sqrt(sum((mask - mean(mask))²) × sum((ion - mean(ion))²))
```

An `r` near +1 means high intensity tends to occur in the class. Near 0 means
little linear spatial association. Near −1 means intensity tends to avoid it.

If either input is constant, its variance is zero and PCC is undefined. This is
why SciPy produced `ConstantInputWarning` for constant ion images. Such a bin
does not provide usable correlation evidence.

## F1 and mSCF1

For a PCC threshold such as 0.3, a bin is considered a reference-positive peak
when its class correlation passes the threshold. A model’s selected bins are
then compared with this reference set.

```text
precision = TP / (TP + FP)
recall    = TP / (TP + FN)
F1        = 2 × precision × recall / (precision + recall)
```

Precision asks how many selected peaks were spatially relevant. Recall asks how
many reference peaks were recovered. F1 balances both.

We calculate F1 at PCC thresholds 0.3, 0.4, 0.5 and 0.6. mSCF1 is their
arithmetic mean:

```text
mSCF1 = (F1@0.3 + F1@0.4 + F1@0.5 + F1@0.6) / 4
```

Higher is better. A fixed or matched peak budget is important because selecting
more bins generally increases recall while risking lower precision.

## Reconstruction metrics

### Mean squared error

```text
MSE = mean((reconstruction - target)²)
```

It penalises larger errors more strongly because errors are squared. Lower is
better. TIC-normalised spectra contain many small values, so absolute MSE values
are tiny; relative paired differences are easier to interpret.

### Mean absolute error

```text
MAE = mean(abs(reconstruction - target))
```

Lower is better and less dominated by large individual errors than MSE.

### Cosine similarity

```text
cosine = dot(reconstruction, target)
         / (norm(reconstruction) × norm(target))
```

It measures spectral shape alignment. A value near 1 means the vectors point in
almost the same direction. Higher is better. It is less sensitive to overall
scale than MSE.

### Scaled categorical cross-entropy

This matches the msiPL-style reconstruction objective on normalised spectra.
Its scale depends on implementation and spectral dimensionality, so it should
mainly be used for matched comparisons rather than as an intuitive standalone
number.

## Balanced accuracy and macro F1

Ordinary accuracy can look good on an imbalanced section by predicting the
majority class. Balanced accuracy averages per-class recall, giving each class
equal weight. Macro F1 calculates F1 per class and averages the classes.

These are preferable for sections such as `GBM12_1`, where tumour pixels are a
small minority.

## ROC AUC

ROC AUC measures whether the probe ranks positive examples above negative ones
across all classification thresholds. A value of 0.5 is chance ranking; 1.0 is
perfect ranking. It does not choose one operating threshold.

## ARI and NMI

Adjusted Rand Index compares pairs of samples under two clusterings and adjusts
for agreement expected by chance. It is 1 for identical partitions and can be
near 0 for chance-level agreement.

Normalised Mutual Information measures shared information between cluster IDs
and labels, scaled to 0–1. Both are invariant to arbitrary swapping of GMM
component numbers.

## Silhouette score

Silhouette compares within-label distance with distance to the other label in
latent space. Larger positive values indicate better-separated groups. It is a
geometric diagnostic, not a classifier score.

## Moran’s I

Moran’s I measures whether neighbouring pixels have similar values:

```text
I = spatially weighted cross-product of centred values
    / total centred variance
```

Higher positive values mean stronger local spatial autocorrelation. High
Moran’s I is not automatically good: an over-smoothed representation can be
spatially smooth while erasing biologically meaningful boundaries.

## Integrated Gradients completeness

Integrated Gradients should approximately satisfy:

```text
sum(attributions) = model_target(input) - model_target(baseline)
```

The residual measures numerical approximation error. Small residuals show that
the path integration accounts for the output change; they do not by themselves
prove that the chosen target or baseline is biologically correct.

## Deletion faithfulness

Selected bins are replaced by baseline values and the assigned GMM posterior is
recomputed:

```text
posterior drop = original posterior - posterior after deletion
```

A larger positive drop means the removed bins mattered to the decision. We
compare Integrated Gradients with first-layer L2 and random selections at the
same deletion budgets.

## Jaccard similarity

For two selected peak sets:

```text
Jaccard(A, B) = size(A intersection B) / size(A union B)
```

It measures exact-set stability from 0 to 1. Stable mSCF1 with imperfect
Jaccard means different but similarly effective bins can be selected.

## Wilcoxon signed-rank test

The whole-GBM comparisons are paired because both methods are evaluated on the
same sections. The Wilcoxon signed-rank test asks whether paired differences
are systematically centred away from zero without assuming normality.

With only eight sections, p-values have low resolution and power. Always report
them with:

- per-section values;
- win/loss counts;
- mean and median change;
- range and standard deviation;
- computational cost.

A large p-value is not proof that two methods are identical. It means this
small paired sample did not provide evidence of a consistent directional
difference.

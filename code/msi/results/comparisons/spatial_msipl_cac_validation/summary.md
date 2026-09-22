# Frozen CAC validation summary

Eight CAC sections were evaluated with the frozen uniform-neighbourhood and centre-only VAEs.
Peak selection used GMM Integrated Gradients with the same tuned legacy msiPL count per section.

## Aggregate results

- Spatial IG mean mSCF1: 0.5595
- Centre-only IG mean mSCF1: 0.5285
- Legacy msiPL mean mSCF1: 0.4024
- S3PL reproduction mean mSCF1: 0.5915 (peak-count matched)
- Spatial GMM mean balanced accuracy: 0.6690
- Centre-only GMM mean balanced accuracy: 0.6845

## Paired conclusions

- spatial IG versus centre-only IG: mean difference +0.0310; wins 8/8; exact two-sided Wilcoxon p=0.007812.
- spatial IG versus legacy msiPL: mean difference +0.1572; wins 8/8; exact two-sided Wilcoxon p=0.007812.
- spatial IG versus S3PL reproduction: mean difference -0.0320; wins 2/8; exact two-sided Wilcoxon p=0.039062.
- spatial versus centre-only GMM balanced accuracy: mean difference -0.0155; wins 2/8; exact two-sided Wilcoxon p=0.250000.
- spatial versus centre-only reconstruction MSE: mean difference -0.0000; wins 4/8; exact two-sided Wilcoxon p=1.000000.
- spatial versus centre-only IG faithfulness: mean difference +0.0405; wins 6/8; exact two-sided Wilcoxon p=0.078125.

## Interpretation

Spatial context consistently improves IG peak-selection mSCF1 over the matched centre-only control,
but it does not consistently improve reconstruction or GMM agreement with expert classes.
Both nonlinear IG methods outperform legacy msiPL. First-layer L2 remains an inadequate peak ranking.
S3PL has the highest mean mSCF1 after using the same section-specific peak counts as the other methods.

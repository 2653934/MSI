# Abstract options (30 Oct)

There was no abstract file in the dump; this is new. Pick the points you want (tick the boxes), then pick or mix a draft. IEEE abstracts are usually 150–250 words; at 8 pages, aim for ~180.

**Numbers marked ⟳ may change after the IG completeness reruns (supervisor chat 30 Oct 12:58).** Example: "136 of 140" becomes "x of 144" once the four missing seed-arms are in.

## 1. Candidate content (one line each)

| # | Point | Evidence | Must / nice / cut? |
|---|---|---|---|
| A | MSI has thousands of m/z channels per pixel, so analysis starts by selecting peaks | intro | must |
| B | Learned methods: msiPL (VAE weights), S3PL (3D conv, spatial) | related work | must |
| C | Question: does cheap neighbourhood context help a lightweight VAE, and which pipeline stage decides peak quality? | intro | must |
| D | Method: VAE ± 3×3 context → GMM segmentation → rank by IG vs correlation with posterior maps | methods | must |
| E | Fair comparison: matched peak budgets, 24 sections, 3 public collections (GBM, CAC, RCC), predeclared rules, 3 seeds, paired Wilcoxon + Holm | methods | must (compressed) |
| F | Correlation beats IG in 136/140 ⟳ paired comparisons; supported in 6/6 dataset–arm comparisons (Holm p ≤ 0.047 ⟳) | C-main, stats 6.6 | must |
| G | Pipeline still beats reproduced msiPL (+0.09 to +0.16) | tab:main | nice |
| H | Neighbourhood input: no consistent spatially specific gain (small CAC gain, +0.023; equivalent on GBM ⟳) | Test R/V | must |
| I | Spatially aware ranking statistics (posterior correlation, Moran's I) were the strongest label-free rankings | tab:main | must |
| J | PCA-5 segmentation ≈ VAE (so the encoder is not the bottleneck) | Test V | nice |
| K | Correlation is ~700× faster than IG on GBM (1.1 s vs 770 s per section) | runtime | nice |
| L | S3PL GBM not reproduced: 0.32 ± 0.04 over 10 seeds vs 0.496 published; seed effect is mostly initialisation | Inv. 21 | nice |
| M | Contribution sentence: where spatial information helps learned peak ranking (the ranking statistic, not the encoder input) | — | must |

## 2. Drafts

### Draft 1: short (~150 words; A, C, D, E, F, H, I, M)

Mass spectrometry imaging (MSI) records thousands of mass-to-charge channels at every pixel of a tissue section, so analysis usually begins by selecting a few informative peaks. We ask whether local spatial context improves learned peak ranking, and where in the pipeline it matters. We trained variational autoencoders with and without 3×3 neighbourhood input, segmented their latent spaces with a Gaussian mixture model, and ranked peaks either by Integrated Gradients (IG) through the model or by correlating each ion image with the segment posterior maps. On 24 sections from three public datasets, at matched peak budgets and under predeclared rules, correlation outperformed IG in 136 of 140 ⟳ paired comparisons across three seeds (Holm-adjusted p ≤ 0.047 ⟳ in all six dataset–model comparisons). Neighbourhood input gave no consistent gain, whereas spatially aware ranking statistics, namely correlation and Moran's I, were the strongest label-free rankings. In this setting, spatial information helps at the ranking stage, not at the encoder input.

### Draft 2: balanced (~190 words; adds B, G, J, K)

Mass spectrometry imaging (MSI) measures thousands of mass-to-charge (m/z) channels at every tissue location, so analyses begin by selecting informative peaks. Learned methods such as msiPL rank peaks from an unsupervised model, and S3PL adds spatial context through 3D convolution. We test whether cheap neighbourhood input gives a lightweight variational autoencoder (VAE) the same benefit, and which pipeline stage determines peak quality. VAEs with and without 3×3 context were segmented with a Gaussian mixture model. Peaks were ranked by Integrated Gradients (IG) through the model or by correlation of each ion image with the posterior maps. All rankings were compared at matched budgets on 24 sections from three public datasets, under predeclared decision rules and paired tests with Holm correction. The pipeline outperformed reproduced msiPL, but not because of IG: with the segmentation held fixed, correlation beat IG in 136 of 140 ⟳ comparisons over three seeds, was statistically supported in all six dataset–model comparisons, and was about 700 times faster. Neighbourhood input gave no consistent gain, a PCA segmentation matched the VAE, and spatially aware statistics (correlation, Moran's I) were the best label-free rankings.

### Draft 3: full (~240 words; Draft 2 + L)

Draft 2, plus before the final sentence: "We also could not reproduce S3PL's published glioblastoma score: ten seeds of the released code gave 0.32 ± 0.04 against 0.496, with seed variation driven mainly by weight initialisation." End with M.

## 3. My recommendation

Draft 2 without K, which brings it to about 175 words. F, H and I are the paper. G heads off "is your pipeline even good?". J is the cheapest way to support "the encoder is not the bottleneck". L is interesting but it's a side result, and it invites questions an abstract can't answer.

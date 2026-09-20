# Methodology and Rationale

## Overall experimental logic

The workflow deliberately moves from cheap checks to expensive claims:

```text
inspect data
  -> validate coordinates and masks
  -> reproduce baselines
  -> test model mechanics
  -> choose a method on one development section
  -> freeze the method
  -> validate across sections
  -> validate on a second dataset
```

This prevents a common research mistake: repeatedly changing the method after
seeing every test-section result.

## Why start with msiPL and S3PL?

Legacy msiPL provides a VAE-based self-supervised peak learner. S3PL explicitly
uses spatial patches. Reproducing both gives two relevant reference points:

- msiPL asks what can be learned from spectra without our contextual encoder.
- S3PL asks what an existing spatial self-supervised method achieves.

Our method should be compared with both, not only with a weak or unrelated
baseline.

## Input representation

Each measured pixel has a spectrum with one value per m/z bin. Every spectrum
is TIC-normalised:

```text
normalised intensity at bin j = intensity at bin j / sum of all bin intensities
```

TIC normalisation makes each spectrum sum to one. It reduces variation caused
only by total signal magnitude and lets the model focus on spectral shape.

For each central pixel, the code constructs the eight slots of a Moore
neighbourhood: horizontal, vertical and diagonal offsets around the centre.
Only actually measured coordinates are valid. Missing positions stay masked;
they are not silently treated as measured zero spectra.

## Spatial-msiPL model

The contextual model receives two spectra concatenated together:

1. the TIC-normalised central spectrum;
2. one aggregated neighbourhood-context spectrum.

The encoder maps this `2 × spectral_bins` vector through a 512-unit hidden
layer into a five-dimensional Gaussian latent distribution. The decoder sees a
sample from that distribution and reconstructs **only the central spectrum**.

That target is important. The neighbourhood is supporting context, not an
additional reconstruction target. The model must use nearby tissue information
only insofar as it helps represent the centre.

The centre-only control uses the same hidden and latent dimensions but receives
only the central spectrum. It answers Hairong’s baseline question: does context
help compared with an ordinary VAE under matched training controls?

## The three neighbourhoods

### Uniform mean

Every valid neighbour has equal weight. The weighted spectrum is TIC-normalised
again. This method has no learnable neighbourhood parameters and does not care
which direction a neighbour occupies.

### Depthwise weights

The model learns eight position weights independently for every m/z bin. This
is expressive but orientation-sensitive and adds many parameters. It starts as
the uniform mean so the initial comparison is controlled.

### Spectral attention

The centre and each neighbour are projected into a small learned embedding.
Scaled dot-product similarity produces neighbour weights. The same projection
is applied to every slot, so the mechanism is orientation-free. Input scaling
was investigated because TIC-normalised values are numerically small.

Uniform mean was frozen because the full development comparison showed only
minor differences among the variants. Selecting the simplest competitive model
reduces overfitting, parameter cost and explanation burden.

## VAE objective

The core loss has two components:

```text
VAE loss = reconstruction loss + beta × KL divergence
```

- Reconstruction loss rewards recovery of the central spectrum.
- KL divergence regularises the latent distribution toward a standard normal.
- Beta controls the strength of that regularisation.

A cosine learning-rate schedule is used. Seeds, data-loader state, optimiser,
scheduler and random states are stored in restart checkpoints so long jobs can
resume consistently.

## Explicit spatial loss experiment

We also tested:

```text
total loss = VAE loss + lambda × scale × adjacent-latent MSE
```

This directly pulls adjacent pixels’ latent means together. The experiment was
needed because contextual input alone does not mathematically guarantee a
smooth latent map. The result showed that stronger smoothing can reduce local
latent distance while harming reconstruction and not improving the spatial
probe. We therefore did not assume that “smoother” means “better”.

## Poisson augmentation experiment

MSI intensities arise from counts, so Poisson noise is a plausible robustness
augmentation. Training inputs were sampled as Poisson counts at a calibrated
effective count and TIC-normalised again; decoder targets stayed clean.

The augmentation was evaluated using a rule declared before looking at the
result: limited clean-data regression and at least 1% noisy-data improvement.
It failed the improvement gate and was not promoted.

## Representation evaluation

Labels are never used to train the VAE. They are used afterward to ask whether
the unsupervised latent space contains relevant structure.

- A spatially blocked probe predicts tissue labels from latent means.
- A one-pixel halo reduces leakage between neighbouring train and test tiles.
- GMM ARI and NMI compare unsupervised clusters with expert labels.
- Moran’s I measures spatial autocorrelation of latent dimensions.
- Silhouette score measures label separation in latent space.

These answer different questions and should not be collapsed into one score.

## Why Integrated Gradients?

The model is nonlinear. Inspecting only the first encoder layer ignores ReLU,
batch normalisation, latent mapping, neighbourhood interaction and the GMM
decision surface. Integrated Gradients follows a path from a baseline spectrum
to a real spectrum and integrates how the target output changes along that
path.

Our target is the posterior probability of the pixel’s assigned label-free GMM
component. The baseline is the section-wide mean TIC-normalised spectrum,
inserted into the centre and every valid neighbour slot. For every m/z bin, we
combine absolute central attribution with attribution across valid neighbours.

The implementation uses 64 trapezoidal intervals and checks completeness:

```text
sum of attributions ≈ target(input) − target(baseline)
```

## Peak selection and fair comparison

Each GMM component creates its own m/z ranking. A deterministic round-robin
procedure alternates among components, keeps bins unique and prevents the
larger or easier cluster from monopolising the peak list.

For evaluation, the number of selected bins exactly matches legacy msiPL for
that section. Counts differ across GBM sections, from 453 to 686, so using one
universal count would be unfair.

A 10-ppm non-maximum suppression produces a compact candidate list for human
interpretation and ion images. The matched mSCF1 calculation uses the raw
matched bins, not the consolidated display list.

## Faithfulness test

High-ranked bins are replaced with section-mean values in held-out pixels. We
then measure the decrease in the assigned GMM posterior. A useful ranking should
cause a larger decrease than random bins and the first-layer L2 comparator.
This tests whether attribution identifies features the model actually relies
on, not merely attractive-looking ion images.

## What first-layer L2 does and does not represent

First-layer L2 ranks each m/z bin by the Euclidean norm of its input weights
across all first hidden units. For the contextual model, central and context
norms are added. It is a deliberately simple linear comparator, not a complete
reimplementation of legacy msiPL LearnPeaks.

LearnPeaks additionally uses hidden-to-latent weights to choose a hidden neuron
for each latent feature, multiplies input weights by spectral standard
deviation, applies a beta-controlled threshold, unions candidates across latent
features and maps them to local maxima in the mean spectrum. A poor L2 result
therefore supports only the claim that raw first-layer magnitude is an
inadequate explanation of the contextual model.

## Matched centre-only attribution control

Comparing spatial IG with legacy msiPL changes both the model and the peak
explanation procedure. The centre-only IG control removes that ambiguity:

```text
centre-only VAE + identical IG and GMM
              versus
uniform-neighbourhood VAE + identical IG and GMM
```

The centre-only model receives no neighbour signal, so neighbour attributions
are structurally zero. All other evaluation settings and each section's matched
peak count are held fixed. This comparison tests the added value of context;
the spatial model is not assumed to win.

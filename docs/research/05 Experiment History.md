# Experiment History

This chronology records the reasoning chain rather than every shell command.

## 1. Initial inspection and repository setup — August 2026

- Inspected CAC imzML files, coordinate grids and masks.
- Generated masks, TIC images, base-peak images, coverage maps and ion images.
- Imported the original msiPL code and adapted it for cluster execution.
- Established the Git/cluster storage boundary: source and compact results in
  Git; raw data, environments and checkpoints outside Git.

## 2. Legacy msiPL baseline

- Diagnosed the legacy implementation and its TensorFlow/Keras requirements.
- Reproduced the original multi-section legacy workflow.
- Added peak evaluation using PCC thresholds and mSCF1.
- Later reran msiPL in a paper-aligned beta-tuned workflow on all eight GBM and
  eight CAC sections.
- Produced the Weigand comparison figure and recorded both the initial and tuned
  results rather than overwriting the history.

## 3. S3PL on CAC

- Adapted the released S3PL code to the cluster and fixed Windows line endings.
- Corrected Slurm resource requests after the cluster rejected the original
  GRES specification.
- Protected conda activation from an unbound MKL variable.
- Ran all CAC sections and recorded runtime and peak GPU memory.
- Corrected `280TopL` handling after its partial MSI coverage exposed dense-grid
  assumptions.

## 4. MassNet GBM acquisition and validation

- Transferred and extracted the eight HDF5 sections.
- Inspected HDF5 datasets, labels, coordinates and spectral orientation.
- Constructed normal/tumour masks from `Class_Label` at measured coordinates.
- Visualised every section and its coverage.
- Acquired the official imzML package and proved semantic agreement between the
  official masks and the HDF5-derived masks.

## 5. S3PL on MassNet GBM

- Added an HDF5 adapter to the released S3PL implementation.
- Tested patch size 9, then the paper-reported GBM patch size 3.
- Repeated `GBM108_positive` to verify deterministic reproducibility.
- Tested released-code normalisation and paper-described TIC normalisation.
- Tested official imzML on positive and negative pilot sections.
- Closed the format gate when imzML did not improve agreement with the paper.
- Formalised the remaining difference as a paper/release ambiguity rather than
  changing each section until it matched.

## 6. Spatial-msiPL implementation

- Built measured-neighbour preprocessing with eight Moore slots and masks.
- Implemented central-only and contextual VAEs.
- Implemented uniform mean, depthwise and attention neighbourhood aggregators.
- Added smoke tests, unit tests and GPU feasibility checks.
- Added restartable training with atomic checkpoints and complete RNG state.

## 7. Neighbourhood development and production

- Ran matched five-epoch stability pilots.
- Ran 100-epoch production models on `GBM108_positive`.
- Evaluated spatially blocked probes, GMM agreement, silhouette and Moran’s I.
- Investigated attention input scaling after TIC-normalised inputs made the
  original scale questionable.
- Froze uniform mean as the simplest competitive neighbourhood.

## 8. Additional development gates

- Trained a centre-only VAE to provide the required reconstruction baseline.
- Tested explicit latent spatial-coherence penalties over several lambdas.
- Calibrated and tested Poisson input augmentation.
- Rejected changes that did not pass predeclared improvement rules.

## 9. Nonlinear attribution

- Fitted a label-free GMM to frozen latent means.
- Implemented differentiable GMM posterior computation.
- Implemented Integrated Gradients through centre and neighbour inputs.
- Added completeness, deletion faithfulness and first-layer L2 comparison.
- Produced matched mSCF1 evaluation, GMM maps and ion images.
- Repeated attribution sampling with fixed model and GMM seeds to quantify
  sensitivity to the sampled attribution pixels.

## 10. Whole-GBM frozen validation

- Trained uniform-mean and centre-only models for every remaining GBM section.
- Used five-epoch restart checkpoints because individual runs could exceed one
  allocation.
- Audited all 14 configurations to 100/100 epochs.
- Evaluated deterministic reconstruction for all eight paired sections.
- Found a heterogeneous 4–4 MSE split rather than a consistent spatial benefit.

## 11. Current attribution campaign

- Generalised attribution and peak evaluation to all GBM sections.
- Matched each section’s legacy peak count instead of assuming 530 everywhere.
- Initial batches failed safely because Slurm repeatedly allocated nodes without
  usable CUDA.
- Added a real CUDA warm-up and bounded self-requeue that dynamically records
  and excludes a failing node for that job only.
- Submitted canary job `56971` for `GBM108_negative`.

## Why the history matters

Several negative or mixed results were retained: S3PL’s reproduction gap,
attention’s lack of a clear advantage, the failed Poisson gate and mixed
reconstruction effects. These are not wasted work. They define what was tested,
prevent circular tuning and make the final claims more credible.

# Spatial MSI Peak Learning Research

Honours research repository for reproducible experiments in spatially informed
peak learning for mass spectrometry imaging (MSI).

The current research question is:

> Can learned spatial context and nonlinear attribution improve MSI peak
> learning over fixed neighbourhood averaging and first-layer weight
> importance?

## Start here

- [`code/msi/README.md`](code/msi/README.md) - code, artifacts and cluster map
- [`docs/meetings/2026-09-14-progress-brief.md`](docs/meetings/2026-09-14-progress-brief.md) - current scientific narrative
- [`RP/proposal.pdf`](RP/proposal.pdf) - approved research proposal
- [`code/msi/cluster_node_issues.txt`](code/msi/cluster_node_issues.txt) - observed cluster incidents

## Repository boundaries

This Git repository contains source code, job definitions, compact results,
figures, logs and reproducibility metadata. Large raw datasets, Conda
environments and trained checkpoints do not belong in Git.

On the cluster:

```text
~/msi/                                      Git working tree
/datasets/zsuliman/msi_data/                raw and prepared datasets
/datasets/zsuliman/msi_checkpoints/         trained model checkpoints
~/miniconda3/envs/                          Conda environments
```

The normal local sync intentionally excludes raw data and checkpoints.

## Current status

- S3PL completed on all eight CAC sections.
- S3PL has a documented partial reproduction on eight MassNet GBM sections.
- Three matched Spatial-msiPL neighbourhood VAEs completed on GBM108-positive.
- The original attention mechanism was diagnosed as saturated.
- A `sqrt(D)` attention correction passed a full-section five-epoch pilot.
- A matched 100-epoch corrected-attention experiment is the current run.

Scientific claims should be based on saved metrics and comparisons, not on a
job merely completing successfully.

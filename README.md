# Spatial MSI Peak Learning Research

Honours research repository for reproducible experiments in spatially informed
peak learning for mass spectrometry imaging (MSI).

The current research question is:

> Can learned spatial context and nonlinear attribution improve MSI peak
> learning over fixed neighbourhood averaging and first-layer weight
> importance?

## Start here

- [`code/msi/README.md`](code/msi/README.md) - code, artifacts and cluster map
- [`docs/operations/cluster_sync.md`](docs/operations/cluster_sync.md) - safe cluster transfer commands
- [`docs/repository_audit_2026-09-20.md`](docs/repository_audit_2026-09-20.md) - repository audit and cleanup plan
- [`docs/research/README.md`](docs/research/README.md) - research results and methodology handbook
- [`docs/meetings/2026-09-14-progress-brief.md`](docs/meetings/2026-09-14-progress-brief.md) - current scientific narrative
- [`RP/proposal.pdf`](RP/proposal.pdf) - approved research proposal
- [`code/msi/cluster_node_issues.txt`](code/msi/cluster_node_issues.txt) - observed cluster incidents

## Repository boundaries

This Git repository contains source code, job definitions, compact results,
figures, selected diagnostic evidence and reproducibility metadata. Routine
Slurm logs, large raw datasets, Conda environments and trained checkpoints do
not belong in Git.

On the cluster:

```text
~/msi/                                      Git working tree
/datasets/zsuliman/msi_data/                raw and prepared datasets
/datasets/zsuliman/msi_checkpoints/         trained model checkpoints
~/miniconda3/envs/                          Conda environments
```

The normal local sync intentionally excludes raw data, checkpoints, Git
metadata and caches. Prefer the documented targeted pull when collecting
results so that cluster copies of source files do not overwrite local edits.

## Current status

- S3PL completed on all eight CAC sections.
- S3PL has a documented partial reproduction on eight MassNet GBM sections.
- Three matched Spatial-msiPL neighbourhood VAEs completed on GBM108-positive.
- The original attention mechanism was diagnosed as saturated.
- A `sqrt(D)` attention correction passed a full-section five-epoch pilot.
- A matched 100-epoch corrected-attention experiment is the current run.

Scientific claims should be based on saved metrics and comparisons, not on a
job merely completing successfully.

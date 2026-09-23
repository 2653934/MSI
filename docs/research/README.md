# MSI Research Handbook

Last updated: 2026-09-22

This folder is the human-readable guide to the MSI research project. The JSON,
CSV, logs and checkpoints remain the authoritative machine-readable artifacts;
these notes explain what those artifacts mean, why each experiment was run and
how the pieces fit together.

## Start here

1. [[01 Results Record]] — the main ledger of completed results and defensible conclusions.
2. [[02 Methodology and Rationale]] — what each model and experiment does, and why.
3. [[03 Datasets and Preprocessing]] — CAC and MassNet GBM structure, masks and adapters.
4. [[04 Metrics and Statistics]] — how every important metric is calculated and interpreted.
5. [[05 Experiment History]] — chronological account from initial inspection to the current campaign.
6. [[06 Cluster and Reproducibility]] — environments, Slurm, storage, checkpoints and failure handling.
7. [[07 Current Status and Next Steps]] — the live decision tree and remaining work.

8. [[08 Concepts Mathematics and Implementation Guide]] — the terminology, equations, rationale, code references and result links in one study guide.

## Research question

The project asks whether adding local spatial context to msiPL-style
self-supervised representation learning improves the selection of spatially
meaningful mass-spectrometry imaging peaks. It also asks whether any benefit is
consistent across tissue sections and across the GBM and CAC datasets.

The central comparison is not merely “does a larger model reconstruct better?”
It is:

> Does a contextual, nonlinear representation identify peaks that agree better
> with spatial tissue structure than legacy msiPL, S3PL and simple linear
> importance measures?

## Evidence hierarchy

- **Dataset validation** establishes that spectra, coordinates and masks align.
- **Baseline reproduction** establishes executable comparison points.
- **Development experiments** choose a method on `GBM108_positive` only.
- **Frozen validation** tests that choice on the other GBM sections.
- **Second-dataset validation** on CAC tests generalisation and is now complete.

This distinction matters. A good result on the development section is a reason
to continue, not proof that the method generalises.

## Repository links

- [Workspace README](../../README.md)
- [Spatial-msiPL package](../../code/msi/src/spatial_msipl/)
- [Python experiment scripts](../../code/msi/scripts/)
- [Slurm scripts](../../code/msi/slurm_jobs/)
- [Results](../../code/msi/results/)
- [Cluster node incident record](../../code/msi/cluster_node_issues.txt)

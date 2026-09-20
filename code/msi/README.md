# MSI Experiment Workspace

This directory contains the executable research workflow. It is organized by
the role of each artifact rather than by the date on which it was created.

## Directory map

```text
baselines/          External/reference implementations adapted for this study
  msipl/            Legacy msiPL implementation
  s3pl/             S3PL implementation and HDF5 adapter
src/                Our reusable Spatial-msiPL Python package
scripts/            Python entry points for inspection, training and evaluation
slurm_jobs/         Cluster job and submission scripts
results/
  baselines/        Outputs from reference methods
  validation/       Smoke tests, audits and decision-gate pilots
  experiments/      Full experiments used for scientific comparisons
  visualisations/   Dataset-level exploratory figures
logs/               Local Slurm stdout/stderr (new files are ignored by Git)
reproducibility/     Frozen manifests and compact snapshots for key reproductions
cluster_node_issues.txt
                    Factual record of node-specific incidents
```

## What each result category means

### `results/baselines/`

Results produced by msiPL or S3PL. These establish comparison points; they are
not outputs from our new model.

### `results/validation/`

Checks that answer a narrow question before an expensive run. Examples include
format validation, GPU feasibility, five-epoch stability and attention-scaling
diagnostics. A successful validation result is not automatically a final
scientific result.

### `results/experiments/`

Completed production runs and their matched evaluations. These are the primary
inputs to research comparisons.

### `results/visualisations/`

Dataset inspection figures such as masks, coverage, TIC images and ion images.
They validate data alignment and help interpret datasets; they do not by
themselves measure model performance.

## Cluster storage policy

Keep the following outside the Git working tree:

- Raw `.h5`, `.imzML`, `.ibd` and archive files
- Model checkpoints (`.pt`, `.pth`, `.ckpt`)
- Conda environments and package caches
- Temporary extraction directories

Canonical cluster locations:

```text
Data:        /datasets/zsuliman/msi_data/
Checkpoints: /datasets/zsuliman/msi_checkpoints/
Repository:  /home-mscluster/zsuliman/msi/
```

The `.gitignore` prevents common checkpoint formats and local caches from being
added accidentally. Transfer commands and their exact local/cluster path
mapping are documented in
[`../../docs/operations/cluster_sync.md`](../../docs/operations/cluster_sync.md).

Routine Slurm logs are useful locally while diagnosing a run, but they are not
permanent scientific artifacts by default. New files in `logs/` are ignored;
already tracked historical logs remain until the reviewed cleanup phase. The durable record should be compact
metrics, summaries, figures, manifests and selected diagnostic logs. See the
[repository audit](../../docs/repository_audit_2026-09-20.md) before changing the
current tracked log history.

## Environments

The main PyTorch environment specification is
[`baselines/s3pl/environment.yml`](baselines/s3pl/environment.yml). Current
Spatial-msiPL jobs use the same `s3pl_env` environment. Historical legacy msiPL
code has older TensorFlow/Keras requirements documented in its own README and
should not be mixed into the PyTorch environment casually.

## Artifact naming

- Slurm logs include the job ID: `<job-name>-<job-id>.out/.err`.
- Validation attempts use job-specific directories when reruns must coexist.
- Production experiment names describe the dataset, seed and method variant.
- A final checkpoint must never be overwritten silently.

## Safe cleanup rules

1. Never remove or move files used by a running Slurm job.
2. Preserve final metrics, figures, manifests and the script/config that made
   them.
3. Failed preflight logs may be compacted only after their node incident is
   recorded.
4. Validation checkpoints may be removed after their decision is documented
   and no resume or forensic check is needed.
5. Production checkpoints remain until evaluation and reproducibility checks
   are complete.
6. Inspect exact disk usage before deleting cluster data.

## Documentation

- [`../../docs/README.md`](../../docs/README.md) indexes all durable project
  documentation.
- [`../../docs/research/README.md`](../../docs/research/README.md) is the entry point for
  the research results and methodology handbook.
- [`../../docs/operations/cluster_sync.md`](../../docs/operations/cluster_sync.md) contains
  the copy-and-paste cluster transfer commands.
- [`../../docs/repository_audit_2026-09-20.md`](../../docs/repository_audit_2026-09-20.md)
  records what belongs in Git, what should remain local, and the proposed
  cleanup phases.

## Typical workflow

```text
inspect data -> validate adapter -> smoke/stability test -> production run
             -> evaluation -> comparison -> document conclusion
```

For the current work, GBM108-positive is a development section. Broader runs
should begin only after the method and evaluation protocol are frozen.

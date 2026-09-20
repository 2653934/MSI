# Repository audit — 2026-09-20

## Verdict

The repository is scientifically valuable and recoverable, but it currently
mixes three different lifecycles:

1. source code and experiment definitions;
2. compact, durable research evidence;
3. transient execution evidence and large intermediate arrays.

The first two belong in the remote repository. Most of the third category
should remain on the cluster and local workstation, with only selected
diagnostics and summarized outputs committed.

No raw MSI datasets, Conda environments or model checkpoints are currently
tracked. That is good. The main cleanup opportunity is tracked Slurm output,
followed by large attribution intermediates and nested Git metadata.

## Snapshot

The audit inspected the working tree rather than guessing from names.

| Category | Current observation | Assessment |
|---|---:|---|
| Tracked files | 1,881 | High, but mostly explained by result artifacts |
| Tracked working-tree content | about 106 MB | Manageable, though inefficiently composed |
| Tracked PNG figures | 434 files, about 38.7 MB | Often useful; retain final/diagnostic figures selectively |
| Tracked Slurm `.out`/`.err` | 452 files, about 38.2 MB | Main remote-repository cleanup target |
| All files in `logs/` | 491 files | 477 were already tracked at audit time |
| Tracked NPZ arrays | 20 files, about 18.8 MB | Four attribution arrays account for about 18.2 MB |
| Tracked NPY arrays | 152 files, about 5.5 MB | Mostly compact derived labels/masks; reasonable for now |
| Results tree | 1,146 files, about 66.9 MB | Core evidence, but raw intermediates need a policy |
| Root `tmp/` | about 280 MB, 9,535 files | Local dependency/cache material; now explicitly ignored |

Large raw formats (`.h5`, `.imzML`, `.ibd`, archives), checkpoint formats
(`.pt`, `.pth`, `.ckpt`) and Python caches were not tracked.

## What should remain remote

### Source and configuration

- `src/`
- `scripts/`
- `slurm_jobs/`
- adapted baseline source under `baselines/`
- environment and requirements files
- dataset adapters and validation code

### Durable evidence

- compact JSON metrics and audit summaries;
- CSV peak lists and comparison tables;
- final or interpretation-critical PNG figures;
- masks/labels that are small, derived, versioned inputs and cannot be
  recreated ambiguously;
- manifests, hashes and provenance notes;
- short selected failure logs when the exact text is needed to justify a
  methodological or infrastructure decision.

### Human documentation

- the research handbook under `docs/research/`;
- cluster operating instructions;
- repository and methodology decisions;
- proposal/writing sources and intentional reference documents.

## What should normally remain local and on the cluster

- raw datasets and extracted copies;
- model checkpoints;
- Conda environments and package caches;
- complete Slurm stdout/stderr collections after a run is summarized;
- progress-bar-heavy training output;
- temporary directories;
- raw attribution tensors once the derived tables/figures have been verified;
- repeated exploratory plots that do not support a reported decision.

Local-only does not mean disposable. Important large artifacts should exist in
at least two intentional storage locations, for example cluster storage plus a
local/external backup. Git is not a substitute for backing up raw scientific
data.

## Specific findings

### 1. Slurm logs dominate file count and much of repository size

The largest log families were:

| Family | Files | Approximate size |
|---|---:|---:|
| `s3pl-gbm` | 58 | 23.1 MB |
| `s3pl-cac` | 18 | 7.0 MB |
| `spatial-gbm-val` | 84 | 1.8 MB |
| `msipl-massnet` | 16 | 1.6 MB |
| `msipl-cac` | 18 | 1.2 MB |

Many of these contain progress output already summarized by metrics and runtime
JSON. Keeping every attempt in Git makes reviews noisy and causes failed node
allocations to look as important as scientific results.

New routine files in `logs/` are now ignored while remaining available locally.
Copy only selected concise logs into the relevant `reproducibility/` record.
Before changing the historical tracked set, make one reviewed commit that
preserves the current local files while removing routine logs from the Git
index.

### 2. Four attribution arrays are large intermediates

These files are roughly 4.77 MB each:

```text
results/experiments/spatial_msipl_gmm_integrated_gradients/
  GBM108_positive_seed1/{uniform_mean,sampling_seed2,
  sampling_seed3,sampling_seed4}/attributions.npz
```

They are useful while attribution analysis is active, but derived summaries,
stability tables and figures are better permanent Git artifacts. Do not remove
them until the integrated-gradients campaign and any sensitivity analyses are
complete. Afterwards, archive them outside Git and retain hashes plus the code
needed to regenerate them.

### 3. The imported msiPL baseline contains a nested Git repository

`baselines/msipl/.git` points to
`https://github.com/wabdelmoula/msiPL.git` at commit
`1e8d5cff2d48851bf4b24dd43dbf8c9600ed9174`. It is not tracked by the outer
repository, but an unrestricted rsync can copy it. This creates confusing
nested repository behavior and unnecessary transfer volume.

The upstream information is now recorded in `baselines/msipl/UPSTREAM.md`.
Exclude `.git/` during transfers. The nested metadata can later be removed
locally after verifying the outer repository contains every wanted adaptation.

### 4. Documentation has one repository-level home

The research handbook, meeting/status material, operating instructions and
repository audit now live together under the outer `docs/` directory. This
keeps human documentation out of the executable `code/msi` tree that is synced
to the cluster. Both README files link back to this canonical location.

### 5. Exact duplicate files are not a major problem

Hashing tracked files larger than 100 KB found only a small repeated expert
mapping figure across attribution sampling seeds. Most similarly named results
are genuinely distinct experiment outputs. Reorganizing by deleting apparent
duplicates based on filenames alone would therefore be unsafe.

### 6. The old full-workspace rsync was too broad

The old download could overwrite local source with cluster copies and could
copy remote Git metadata. The old upload could copy nested Git metadata and
could overwrite cluster-generated artifacts with stale local versions.

The corrected commands are in `docs/operations/cluster_sync.md`. Daily result
collection is now targeted; full pulls remain available as an explicit
recovery operation with a dry-run first.

## Proposed cleanup phases

### Phase 1 — completed by this audit

- document safe, direction-specific rsync commands;
- explicitly ignore the root temporary directory and common tool caches;
- ignore new routine Slurm logs without deleting existing local evidence;
- record the imported msiPL upstream URL and commit;
- link the handbook, sync guide and audit from the README files;
- consolidate human documentation under the root `docs/` directory;
- make no bulk deletions and preserve the user's existing worktree changes.

### Phase 2 — completed locally; pending commit

- Routine logs are ignored for future Git additions.
- All 477 historically tracked files under `code/msi/logs/` were removed from
  the Git index with `git rm --cached`.
- All 491 physical log files, totalling about 38.3 MB, were verified to remain
  on the local workstation.
- Compact failure history remains summarized in `cluster_node_issues.txt`, and
  selected run evidence remains under `reproducibility/`.

This cleanup is staged and must be reviewed and committed before GitHub changes.
Existing Git history will still contain old versions unless history is
rewritten; a history rewrite is not recommended during active research.

### Phase 3 — after attribution evaluation is frozen

1. Verify every raw `attributions.npz` has a corresponding summary and figure.
2. Record SHA-256 hashes and the producing command/configuration.
3. Copy the raw arrays to intentional artifact storage.
4. Untrack the large arrays and add a narrow ignore rule for raw attribution
   tensors—not a blanket `*.npz` rule, because some compact NPZ files are useful
   research inputs.

Expected benefit: about 18 MB removed from future snapshots.

### Phase 4 — optional structural cleanup

- decide whether proposal/writing material should remain in this repository or
  move to a dedicated writing repository;
- remove the nested `baselines/msipl/.git` directory after final verification;
- establish `results/README.md` manifests that label outputs as `validation`,
  `intermediate` or `final`;
- promote only publication-ready figures into a small `figures/final/`
  directory while retaining exploratory figures locally.

## Working rule for future files

Before committing a generated file, ask:

1. Does it support a scientific claim or reproduce one?
2. Is it the compact summary, or merely an intermediate used to create the
   summary?
3. Can it be recreated deterministically from tracked code and stored input?
4. Will a future reader know which run produced it?
5. Is Git the appropriate storage system for its size and update frequency?

If the file is large, frequently regenerated and already summarized, keep it
in artifact storage rather than the remote Git repository.

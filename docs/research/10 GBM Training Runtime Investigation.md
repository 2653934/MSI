# GBM training runtime investigation

Status: phase profile (61461), cache batch benchmark (61464), and one-epoch full-section training comparison (61469) completed. One-epoch outputs match exactly; 100-epoch runtime and checkpoint/resume equivalence remain unmeasured.

## What the existing records actually show

All three figures below are for `GBM108_positive` (2,071 measured pixels and 85,062 m/z bins). They are training time only, not Slurm queue wait or the later attribution/evaluation stages.

| Run | Epochs | Training time | Time per epoch | Model size |
|---|---:|---:|---:|---:|
| Legacy msiPL | 100 | 1,549.5 s (25.8 min) | 15.5 s | dense VAE, approximately 87 million parameters |
| S3PL, 3×3 | 10 | 494.9 s (8.25 min) | 49.5 s | 470 trainable parameters |
| Our centre-only VAE | 100 | 40,178.6 s (11.16 h) | 401.8 s | 87,199,312 parameters |
| Our uniform-mean VAE | 100 | 40,608.9 s (11.28 h) | 406.1 s | 130,751,056 parameters |

Sources: `code/msi/results/baselines/msipl/massnet/GBM108_positive/results.json`, `code/msi/results/baselines/s3pl/GBM108_positive_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_3/runtime_metrics.json`, and each VAE's `metadata.json` under `code/msi/results/experiments/spatial_msipl_reconstruction/GBM108_positive_seed1/central_only/` and `spatial_msipl_neighbourhood/GBM108_positive_seed1/uniform_mean/`.

The **centre-only and uniform-mean times differ by only about 1%**. Therefore, the neighbourhood arithmetic and its extra parameters do not explain most of the eleven hours. S3PL's 10-epoch total is not an equal-work comparison with our 100 epochs; even per-epoch comparison is confounded by architecture, input handling and loss. The 100-epoch legacy msiPL comparison is more revealing, although its TensorFlow/Keras implementation and experimental settings are not identical.

## What a runtime comparison actually measures

There are two legitimate but different questions: **How costly is the model on an already-prepared batch?** and **How long does the complete research workflow take?** The first concerns forward/backward computation and device memory; the second includes loading, normalisation, transfers, checkpoints, attribution and evaluation. Neither should silently stand in for the other. A fixed number of epochs or steps is not equal computational work across different architectures, spectra, losses and batch sizes. Report the number of measured pixels, spectral bins, examples and optimiser steps alongside time.

The saved `training_seconds` fields do not even have identical timing boundaries:

| Implementation | What its saved training time includes | Major exclusions |
|---|---|---|
| Legacy msiPL GBM | Keras `model.fit` on a spectrum array already loaded into memory | Initial HDF5 loading/normalisation and weight saving |
| S3PL | Its epoch loop, including patch fetching/normalisation, GPU transfer and model steps | Initial dataset/model setup, subsequent weight saving and evaluation |
| Spatial-msiPL VAE | Sum of epoch timers, including repeated HDF5 sample construction, transfer and model steps | Dataset initialization, final checkpoint write and later IG/evaluation |

Therefore the historical 11-hour VAE number is a valid observed **training-loop time for that implementation**, but it is **not** eleven hours of VAE arithmetic and must not be divided by another method's saved time to claim an architectural speed ratio. The cache benchmark isolates an avoidable data-pipeline cost; it does not erase the historical observation. If the cache passes full training-equivalence checks, we will retain the old measurement as the streaming-loader version and label any new time as a separately measured cached-loader version.

For the final computational comparison, show at least: (1) model-step or phase timing on ready batches, (2) data/preprocessing and one-time cache setup, (3) complete training wall time including setup/checkpoints, and (4) peak selection/attribution/evaluation time and total workflow time. Keep Slurm queue wait and node failures separate. Report parameter count, peak **allocated GPU tensor memory**, and peak **host RAM** separately: the cache is about 672 MiB of host data before temporary arrays, not free memory. Use matched hardware and repeated measurements where practical. Compare released/reproduced protocols as *practical workflows* and an explicit equal-budget diagnostic for efficiency; do not call the existing S3PL 10-epoch and VAE 100-epoch totals a fair model-efficiency test.

## Investigated explanation: repeated HDF5 access

Legacy msiPL loads and TIC-normalises the whole HDF5 spectrum matrix once, then calls `model.fit` on the in-memory array. Our `H5SpatialContextDataset.__getitem__` reads the centre and up to eight neighbours from HDF5, TIC-normalises those spectra and constructs both the contextual input and the full eight-neighbour tensor **for every pixel in every epoch**. Training uses a single-process loader (`num_workers=0`). The centre-only model still requests and transfers the neighbour tensor, although its forward method ignores it.

At 85,062 bins, 128 samples of one central plus eight neighbour spectra represent about **374 MiB of float32 values** before additional copies and intermediate tensors. Across 100 epochs, the dataset can request the equivalent of up to about **591 GiB of float32 spectrum values** even though a single float32 copy of the matrix would be only about **0.66 GiB**. The stored HDF5 dtype may differ; the profiler records it. This is a logical traffic estimate, not a measurement of physical disk reads; OS/HDF5 caching, missing neighbours, array layout and copies affect actual cost. The HDF5 array is shaped `(85,062, 2,071)`, so fetching arbitrary pixel columns may also be expensive depending on chunk layout.

Other possible contributors are the 87–131-million-parameter dense VAE, full-spectrum reconstruction loss, GPU transfers, repeated GPU-to-CPU scalar conversions for logging, and computing the adjacency-based spatial loss even when its weight is zero. Checkpoint writes add session time but are outside the reported sum of epoch times. None should be labelled the dominant cause before profiling.

## Short diagnostic, with no production output changed

`code/msi/scripts/profile_spatial_msipl_training.py` runs only four fresh-model batches for each of centre-only and uniform mean. It times HDF5 read/normalisation/collation, transfer, forward, loss/spatial-pair check, backward/optimizer and scalar logging. It also records HDF5 shape/chunks, tensor parameter counts and peak GPU memory. The script is deliberately diagnostic: per-phase GPU synchronisation adds overhead, and the first batch includes warm-up effects. Interpret later-batch timings as an indication, not as exact full-run time.

From `~/msi` on the cluster, after syncing the two new scripts:

```bash
sbatch slurm_jobs/profile_spatial_msipl_training.sh
```

When it completes, rsync back as usual. Outputs will be in `results/validation/spatial_msipl_runtime_profile/`; the Slurm log will be `logs/spatial-profile-<jobid>.out` and `.err`. If CUDA is unavailable on the allocated node, it stops before the diagnostic. No existing checkpoint or result is overwritten.

## Measured result: job 61461

Both variants completed on an RTX 3090 with no stderr errors. The HDF5 `Data` array has shape `(85,062, 2,071)`, `float64` values and a **single chunk spanning the entire array**; the production dataset requests columns corresponding to a centre and its valid neighbours for each sample. Its `DataLoader` has `num_workers=0`. The same dataset class and batch size were used in this diagnostic and in production training, though the diagnostic used fresh weights, four batches and phase-by-phase CUDA synchronization.

| Phase, excluding first batch | Centre-only | Uniform mean |
|---|---:|---:|
| HDF5 read + TIC normalisation + collation | 24.565 s/batch | 24.442 s/batch |
| CPU-to-GPU transfer | 0.163 s | 0.163 s |
| Forward | 0.0018 s | 0.0045 s |
| Loss + spatial-pair check | 0.0085 s | 0.0011 s |
| Backward + optimiser | 0.0126 s | 0.0164 s |

Thus data preparation accounts for **about 99% of the measured steady-batch phase time** for both models. The first batch took 36–38 s for data preparation, so it should not be used as the steady-state estimate. The two variants' near-identical data time explains why adding uniform context barely changed their eleven-hour production runtimes: centre-only still receives the neighbour batch, and both repeatedly construct it from HDF5. This is a measured bottleneck in the current implementation, **not evidence that the neighbourhood idea itself requires eleven hours**.

As a sanity check, roughly 24.5 seconds × 17 batches × 100 epochs is about 11.6 hours, close to the recorded 11.2-hour training runs. This extrapolation is approximate; the four-batch probe did not benchmark full epochs, checkpointing or all epoch-to-epoch cache effects. The single full-array HDF5 chunk is a likely reason column access is slow, but the probe does not separate HDF5 I/O, NumPy conversion, TIC normalisation and PyTorch collation, nor does it measure physical disk traffic. We should not claim the GPU or a particular HDF5 internal operation is independently proven to be the root cause.

Evidence: `code/msi/results/validation/spatial_msipl_runtime_profile/central_only-61461.json`, `uniform_mean-61461.json`, and `code/msi/logs/spatial-profile-61461.{out,err}`. Code path: `H5SpatialContextDataset._read_spectra` and `__getitem__` in `code/msi/src/spatial_msipl/preprocessing.py`, and the loader/training loop in `code/msi/src/spatial_msipl/training.py`.

## Decision after the profile

The first controlled test now loads raw spectra **once** into a float32 `(pixels, m/z)` matrix in host memory. It still uses the original per-sample TIC normalisation and the *same* centre/neighbour slot construction, so the primary changed variable is repeated HDF5 access. `CachedH5SpatialContextDataset` is opt-in and does not alter existing training. The benchmark compares exact sample arrays (including boundary and missing-neighbour pixels) and then times eight matched, identically ordered batches for each loader. A single float32 matrix is about 0.66 GiB; actual peak memory is higher during loading and collation. Run from `~/msi` after syncing the new source and job script:

```bash
sbatch slurm_jobs/benchmark_spatial_msipl_cache.sh
```

This is a CPU-only data-loading benchmark, so a node's CUDA state is irrelevant. It writes `results/validation/spatial_msipl_cache_benchmark/cache-<jobid>.json` and `logs/spatial-cache-<jobid>.{out,err}`. The job runs the small numerical unit tests first and stops if any exact sample comparison fails. No model is trained and no checkpoint is written.

### Result: job 61464

The three preprocessing unit tests passed. On the real `GBM108_positive` HDF5 section, all fields of 35 selected samples matched exactly, including centre spectra, neighbour spectra, masks, context, coordinates and order. Both loaders used the same first-batch indices.

| Measurement | Streaming HDF5 | In-memory cache |
|---|---:|---:|
| Mean batch preparation after the first batch | 24.704 s | 0.724 s |
| Eight-batch mean | 24.580 s | 0.721 s |

That is a **34.1× speedup in data-loader batch preparation**, not yet a measured 34.1× speedup in total training. Loading the entire float32 cache took 12.8 s and occupied 704,653,608 bytes (about 672 MiB). This strongly supports repeated HDF5 access as the dominant avoidable cost in the existing loader. The result does not prove identical training trajectories or final metrics: the full optimiser loop, GPU transfer, random state, checkpoint/resume and repeated epochs still need an end-to-end equivalence check. Evidence: `code/msi/results/validation/spatial_msipl_cache_benchmark/cache-61464.json` and `code/msi/logs/spatial-cache-61464.{out,err}`.

Since parity passed and data loading improved materially, the next test is a one-epoch end-to-end training comparison on all 2,071 GBM108-positive pixels. The new `compare_spatial_msipl_cache_training.py` runs the **existing `train_vae` loop** for centre-only and uniform-mean models with each loader, matching seed, initialization, batch order and production model size. It reports epoch time, training loss, final parameter differences and peak GPU memory. The separate Slurm job uses CUDA, so it retains the production CUDA-node quarantine. It disables checkpoints and writes only under a new `results/validation/spatial_msipl_cache_training/<jobid>/` directory:

```bash
sbatch slurm_jobs/compare_spatial_msipl_cache_training.sh
```

Its stdout/stderr are `logs/spatial-cache-train-<jobid>.out` and `.err`. A `matched` summary means the predeclared loss and weight tolerances passed for this one-epoch diagnostic; `needs_review` means inspect the numeric differences before drawing a conclusion. Neither status substitutes for a 100-epoch scientific replication. Only after this end-to-end check should a separately named optimised production run be considered. Do not silently replace the frozen 100-epoch results. Pre-normalising the whole matrix once could save still more time, but that is a **second** optimisation requiring its own equivalence test.

### Result: job 61469

The preprocessing tests passed and 35 real-section samples again matched exactly. The four runs used the full 2,071-pixel section, batch size 128, seed 1, the existing training loop and an RTX 3090. For each model, streaming and cached runs started from the same model-state hash and selected the same pixels.

| Model | Streaming epoch | Cached epoch | Epoch speedup | Losses and final state |
|---|---:|---:|---:|---|
| Centre-only | 402.072 s | 12.726 s | 31.59× | Exact equality |
| Uniform mean | 400.840 s | 12.373 s | 32.40× | Exact equality |

Peak allocated GPU tensor memory was also **identical within each pair**: 2,197,544,448 bytes for centre-only and 3,112,135,168 bytes for uniform mean. This does not count the cached host-memory matrix (704,653,608 bytes) or its temporary construction overhead. The one-time cache load was about 12.8 seconds in job 61464; it is **outside** the epoch timings above. No checkpoint was written in 61469.

This is much stronger evidence than a data-loader-only microbenchmark: replacing repeated HDF5 reads preserved the measured one-epoch model trajectory exactly on this node while cutting training-loop time by over 30×. It is still a **one-epoch, one-section diagnostic**, not a measured 100-epoch runtime or a cross-model fair-cost comparison. A separately named full-run or multi-epoch checkpoint/resume check is needed before changing production timing claims. Evidence: `code/msi/results/validation/spatial_msipl_cache_training/61469/summary.json` and `code/msi/logs/spatial-cache-train-61469.{out,err}`.

## Next gate: resume test and separately named 100-epoch measurement

The production training command now accepts an **opt-in** `--cache-spectra` flag. Without that flag, its original streaming-loader behaviour is unchanged. A small synthetic-data test interrupts cached training immediately after a periodic checkpoint, resumes it, and compares its losses and final tensors with uninterrupted streaming training under the same seed and settings. The Slurm job runs this test before the full experiment; it is not yet a measured pass until the cluster test log confirms it.

The full run uses `GBM108_positive`, seed 1, 100 epochs, batch size 128, and otherwise frozen production model settings. It writes to `results/validation/spatial_msipl_cached_full/GBM108_positive_seed1/<variant>/` with checkpoints under `/datasets/zsuliman/msi_checkpoints/spatial_msipl/cache_validation/...`, **not** the historical model directories. It records both summed epoch time and the separate cache construction time; the script-level wall timer includes model setup and checkpoint saving for that allocation. If a run is resumed in another allocation, that session timer is not the campaign total. Submit the two independent variants from `~/msi` after uploading these new code changes:

```bash
sbatch slurm_jobs/run_spatial_msipl_cached_full.sh central_only
sbatch slurm_jobs/run_spatial_msipl_cached_full.sh uniform_mean
```

Do not replace historical runtimes with these new timings. After completion, compare all 100 per-epoch losses and metrics against the original runs, account for cache/setup/checkpoint and host RAM, and clearly label streaming versus cached implementations. The result is a pipeline optimisation, not a new model or proof of S3PL-equivalent computational efficiency.

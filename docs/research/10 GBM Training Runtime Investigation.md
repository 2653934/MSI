# GBM training runtime investigation

Status: initial code-and-artifact audit, 28 September 2026. The causes below are hypotheses until the short phase profiler has run on the cluster.

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

## Leading explanation to test: repeated HDF5 access

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

## Decision after the profile

If HDF5/sample construction dominates, test an **equivalent** preloaded or cached loader on a short run and check exact sample/normalisation parity before considering production changes. If GPU compute dominates, compare encoder, decoder and loss phases and consider memory/precision/batch-size options only after checking numerical and scientific equivalence. If neither dominates, inspect logging, checkpoint and thread settings. Any optimisation of the scientific pipeline would need a targeted equivalence test and a separately named benchmark before replacing frozen results.

# S3PL versus Spatial-msiPL: architecture and runtime audit

Status: code-path audit completed; matched-node phase probe prepared but **not yet run**. This follows the [GBM runtime investigation](10%20GBM%20Training%20Runtime%20Investigation.md). No new S3PL result is claimed here.

## The central architectural difference

On `GBM108_positive`, one measured spectrum has 85,062 m/z bins (`D`). Both methods can inspect a 3×3 spatial window, but they do different work with it.

| Feature | S3PL, paper-aligned p=3 reproduction | Our uniform-mean contextual VAE | Our centre-only VAE |
|---|---|---|---|
| Input per pixel | Full patch `(1, D, 3, 3)` with zero slots for unmeasured positions | Centre `(D)` plus mean of up to eight measured neighbours `(D)`; loader also constructs the eight separate spectra | Centre `(D)`; current loader still constructs/transfers neighbours although the model ignores them |
| Spatial operation | A learned 3D convolution spans the entire 3×3 patch and 51 spectral bins | Fixed mean of valid neighbour spectra; then concatenation with centre | No model-side spatial context |
| Learned core | One `Conv3d` mask, multiplicative attention on centre, then one `ConvTranspose3d` | Dense VAE: 2D-bin input, 512 hidden units, 5 latent units, D-bin output | Dense VAE: D-bin input, 512 hidden units, 5 latent units, D-bin output |
| Training target | Reconstruct the **whole normalised 3×3 patch** | Reconstruct the **normalised centre spectrum** | Reconstruct the **normalised centre spectrum** |
| Loss | Patch mean-squared error | msiPL-style categorical cross-entropy reconstruction + beta-weighted KL; spatial coherence weight zero in frozen GBM runs | Same VAE loss |
| Optimiser; batch; epochs | Adam, `1e-2`; 16; 10 | Adam, `1e-3` initial; 128; 100 | Same VAE schedule |
| Trainable parameters at D=85,062 | 470 at p=3 | 130,751,056 | 87,199,312 |
| Peak selection | Per-pixel top-256 attention values, spatial frequency ranking, then section peak-count cutoff | GMM target posterior with Integrated Gradients ranking, then section peak-count cutoff | Same downstream GMM/IG family |
| Expert mask | Used for downstream PCC/F1 scoring, not reconstruction training | Used for downstream scoring, not VAE training | Same |

Read this as a **protocol map**, not evidence that parameter count alone causes a speed or quality difference. S3PL applies a small kernel repeatedly over all spectral bins; the dense VAE multiplies large full-spectrum matrices. The former can have far fewer weights but still process a substantial patch tensor. The task, input, objective, optimiser, batch size, epoch count and peak-ranking method all differ. For CAC, we already re-evaluated the existing S3PL checkpoints at the same section-specific peak counts as the other methods; that controls the *final count*, not the other protocol differences.

Code references: [S3PL model](../../code/msi/baselines/s3pl/model/Attention3DConvAutoencoder.py), [training](../../code/msi/baselines/s3pl/train.py), [HDF5 patch adapter](../../code/msi/baselines/s3pl/utils/data_source.py), [normalisation](../../code/msi/baselines/s3pl/utils/helpers.py), [peak extraction](../../code/msi/baselines/s3pl/test.py), [our model](../../code/msi/src/spatial_msipl/model.py), [our preprocessing](../../code/msi/src/spatial_msipl/preprocessing.py), and [our training loss](../../code/msi/src/spatial_msipl/training.py).

## A particularly important normalisation difference

Our VAE divides each measured spectrum by its total ion current (TIC). The current S3PL GBM job defaults to `reference_spatial_max`, which takes a maximum over array axis 2 of a `(1,D,3,3)` patch. That axis is one spatial direction, **not the m/z axis**. It therefore normalises entries within the patch differently from per-spectrum TIC. S3PL also has a `paper_tic` option, but the historical `GBM108_positive` reference run used the default. This may affect reconstruction values and peak rankings; it does not, by itself, explain the observed quality gap. A controlled one-factor normalisation test would be needed for that claim.

## What the saved clocks include

S3PL loads the GBM HDF5 spectrum table into float32 host memory before `training_seconds` starts. Its epoch clock includes patch construction, normalisation, transfer, forward/backward and optimiser. Its `total_seconds` begins before the first table load and continues through its test/peak evaluation, but excludes Slurm queue wait and Conda/job-shell startup. Our historical streaming VAE epoch clocks included repeated HDF5 reads. The opt-in cached VAE loads its float32 table once before training, and records that setup separately. These timing boundaries explain why the historical 11-hour VAE observation cannot be treated as 11 hours of model arithmetic.

For `GBM108_positive`, the existing outputs report S3PL p=3 training **494.9 s for 10 epochs**, versus cached centre-only and uniform VAE epoch sums of **1,309.0 and 1,355.4 s for 100 epochs**. Dividing those totals to declare a winner would confound epoch count and task. The S3PL result includes a 73.9 s evaluation, while our VAE needs a separate IG/GMM/peak-evaluation stage. A practical *full workflow* comparison must include those downstream stages and one-time setup for both.

## Next measurement: one-node phase probe

The new [Slurm phase probe](../../code/msi/slurm_jobs/compare_s3pl_cached_vae_phases.sh) runs all three fresh models sequentially on one allocated node, using the same `GBM108_positive.h5`. It calls [S3PL profiler](../../code/msi/scripts/profile_s3pl_training.py) and the existing [VAE profiler](../../code/msi/scripts/profile_spatial_msipl_training.py) with its new `--cache-spectra` option. S3PL uses its production p=3, batch 16, reference normalisation, MSE and Adam settings; the VAE uses batch 128, beta 1, and the production model/loss. The outputs record spectrum-table load time, parameters, batch payload, time for loading/collation, transfer, forward, loss, backward/optimizer, scalar logging, throughput, allocated/reserved GPU tensor memory, and Linux process peak resident memory. The VAE also records its one-time cache load. Process RSS is not a pure data-cache measurement: it includes imports, model objects and temporaries.

From `~/msi` **after syncing the new scripts to the cluster**:

```bash
sbatch slurm_jobs/compare_s3pl_cached_vae_phases.sh
```

Then check `logs/s3pl-vae-phases-<jobid>.out` and `.err`, and sync back `results/validation/s3pl_cached_vae_phases/<jobid>/`. The probe never writes production checkpoints. It samples 8 S3PL batches (128 pixels) and 4 VAE batches (up to 512 pixels); compare **per-pixel throughput and phase proportions**, not raw sampled duration. The first batch can include warm-up, so inspect later-batch averages too. CUDA synchronisation makes each phase measurable but adds overhead. Sequential execution controls the node/GPU, not thermal state or all I/O conditions. One short probe is diagnostic; repeat and run full epochs/workflows before strong cost claims.

After its results return, the next research decision is whether S3PL's remaining runtime advantage is primarily model-step computation, patch/evaluation design, or protocol duration. CAC quality already has a [matched-count section summary](../../code/msi/results/comparisons/spatial_msipl_cac_validation/summary.md); selected-peak overlap and representative ion images remain useful diagnostics of *why* the quality differs. The GBM paper-reproduction gap must be reported separately from any measured CAC advantage.

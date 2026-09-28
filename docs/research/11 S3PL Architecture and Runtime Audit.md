# S3PL versus Spatial-msiPL: architecture and runtime audit

Status: code-path audit and matched-node phase probe **61555 completed**. This follows the [GBM runtime investigation](10%20GBM%20Training%20Runtime%20Investigation.md). The phase probe is diagnostic; it did not train new scientific models.

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

## Measurement protocol: one-node phase probe

The new [Slurm phase probe](../../code/msi/slurm_jobs/compare_s3pl_cached_vae_phases.sh) runs all three fresh models sequentially on one allocated node, using the same `GBM108_positive.h5`. It calls [S3PL profiler](../../code/msi/scripts/profile_s3pl_training.py) and the existing [VAE profiler](../../code/msi/scripts/profile_spatial_msipl_training.py) with its new `--cache-spectra` option. S3PL uses its production p=3, batch 16, reference normalisation, MSE and Adam settings; the VAE uses batch 128, beta 1, and the production model/loss. The outputs record spectrum-table load time, parameters, batch payload, time for loading/collation, transfer, forward, loss, backward/optimizer, scalar logging, throughput, allocated/reserved GPU tensor memory, and Linux process peak resident memory. The VAE also records its one-time cache load. Process RSS is not a pure data-cache measurement: it includes imports, model objects and temporaries.

Submitted from `~/msi` after syncing the scripts to the cluster:

```bash
sbatch slurm_jobs/compare_s3pl_cached_vae_phases.sh
```

The job wrote `logs/s3pl-vae-phases-61555.out` and `.err`, and `results/validation/s3pl_cached_vae_phases/61555/`. The probe never writes production checkpoints. It samples 8 S3PL batches (128 pixels) and 4 VAE batches (512 pixels); compare **per-pixel throughput and phase proportions**, not raw sampled duration. The first batch can include warm-up, so inspect later-batch averages too. CUDA synchronisation makes each phase measurable but adds overhead. Sequential execution controls the node/GPU, not thermal state or all I/O conditions. One short probe is diagnostic; repeat and run full epochs/workflows before strong cost claims.

The next research decision is which parts of the overall workflow, beyond sampled training batches, explain the observed run durations. CAC quality already has a [matched-count section summary](../../code/msi/results/comparisons/spatial_msipl_cac_validation/summary.md); selected-peak overlap and representative ion images remain useful diagnostics of *why* the quality differs. The GBM paper-reproduction gap must be reported separately from any measured CAC advantage.

## Result: matched-node phase probe 61555

All three probes wrote complete JSON reports and the job's `.err` was empty. They ran sequentially on `mscluster49` with an RTX 3090, on the same 2,071-pixel, 85,062-bin `GBM108_positive` HDF5 section. “Steady” below sums each phase's mean **excluding its first batch**; the first batch includes CUDA warm-up and differed substantially. S3PL sampled seven warm batches of 16 pixels; each VAE sampled three warm batches of 128 pixels.

| Method | Batch | Steady batch | Steady pixels/s | Data preparation share | Model/loss/transfer/other per pixel | Peak allocated GPU | Process peak RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| S3PL p=3 | 16 | 0.380 s | 42.1 | 85.9% | 3.35 ms | 0.238 GiB | 1.56 GiB |
| Cached centre-only VAE | 128 | 0.865 s | 148.0 | 92.5% | 0.51 ms | 2.047 GiB | 3.53 GiB |
| Cached uniform-mean VAE | 128 | 0.855 s | 149.7 | 91.6% | 0.56 ms | 2.857 GiB | 3.55 GiB |

The S3PL patch/normalise/collate phase took 0.326 s per 16-pixel batch, versus 0.800 and 0.783 s per 128-pixel VAE batch. On a per-pixel basis those are approximately 20.4 ms for S3PL and 6.25/6.12 ms for the VAEs. S3PL's steady forward + MSE + backward/optimizer time was about 0.044 s per 16 pixels; the VAEs' corresponding phases were about 0.0147/0.0221 s per 128 pixels. This is a **measured throughput difference at each method's own production batch size**, not an equal-batch-size microbenchmark or proof about intrinsic architecture speed.

Extrapolating the short warm-batch timings to the number of batches in one epoch gives roughly **49.0 s for S3PL** and **14.7/14.5 s for the cached VAEs**. This is a check, not a full-epoch measurement: the saved full-run clocks are about 49.5 s per S3PL epoch (494.9 s / 10) and 13.1/13.6 s per cached VAE epoch (1,309.0/1,355.4 s / 100). Their agreement in scale supports the diagnosis. The S3PL 10-epoch run's shorter total training time therefore reflects **far fewer epochs**, not faster processing per epoch on this section. Its small model uses markedly less GPU tensor memory; the VAE's larger model and in-memory data path have a higher memory footprint.

One-time HDF5/table loading took 14.9 s for S3PL, 13.5 s for the first cached VAE process, and 0.96 s for the second VAE process. The third figure is consistent with warm filesystem caching after earlier reads, so it must not be interpreted as an intrinsic loading advantage of uniform mean. Process peak RSS includes Python/PyTorch and intermediate arrays, not just the data matrix; all three jobs were separate processes on the same node. The S3PL historical `peak_gpu_memory_bytes` includes training **and evaluation**, while the phase probe's GPU peak covers training batches only, so those peaks have different boundaries.

Evidence: [S3PL JSON](../../code/msi/results/validation/s3pl_cached_vae_phases/61555/s3pl_p3.json), [centre-only JSON](../../code/msi/results/validation/s3pl_cached_vae_phases/61555/central_only_cached.json), [uniform JSON](../../code/msi/results/validation/s3pl_cached_vae_phases/61555/uniform_mean_cached.json), and [job log](../../code/msi/logs/s3pl-vae-phases-61555.out).

**What remains open:** complete, consistently bounded workflow time still needs S3PL peak extraction/evaluation and VAE GMM/IG/evaluation measured together; this probe only sampled fresh training batches. The different normalisations, reconstruction targets, peak selectors and optimisation schedules also prevent a causal claim that one architecture alone is “more efficient.” The quality question—especially why matched-count S3PL remains stronger on CAC—requires per-section/threshold and peak-image diagnostics, not this timing probe.

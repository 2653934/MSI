# S3PL GBM stability and runtime synthesis

Status: 8 October 2026. This memo closes the two remaining S3PL gates: whether the short GBM protocol is stable across weight initializations, and how the native S3PL and VAE workflows compare when measured repeatedly on the same CAC section and GPU type.

## Questions answered

1. Is the unusual seed sensitivity seen on `GBM108_positive` confined to that section?
2. Is a single 10-epoch S3PL GBM result a reliable baseline?
3. Are the native S3PL and VAE workflow costs in the same broad range, and are the measurements repeatable?

## GBM initialization screen

All runs used patch size 3, 10 epochs, sample-order seed 1 and initialization seeds 1–3. No result was selected because it was favourable.

| Section | Seed 1 | Seed 2 | Seed 3 | Mean | Sample SD | Range |
|---|---:|---:|---:|---:|---:|---:|
| `GBM108_positive` | 0.026 | 0.444 | 0.079 | 0.183 | 0.227 | 0.418 |
| `GBM108_negative` | 0.357 | 0.570 | 0.659 | 0.529 | 0.155 | 0.302 |
| `GBM12_1` | 0.131 | 0.075 | 0.099 | 0.102 | 0.028 | 0.056 |
| `GBM12_2` | 0.508 | 0.273 | 0.488 | 0.423 | 0.130 | 0.235 |
| `GBM22_1` | 0.292 | 0.171 | 0.257 | 0.240 | 0.062 | 0.121 |
| `GBM22_2` | 0.349 | 0.290 | 0.332 | 0.324 | 0.030 | 0.059 |
| `GBM39_1` | 0.277 | 0.137 | 0.206 | 0.207 | 0.070 | 0.140 |
| `GBM39_2` | 0.464 | 0.487 | 0.595 | 0.515 | 0.070 | 0.131 |

Six of eight sections have an absolute three-seed range of at least 0.10 mSCF1. The selected peak lists also move substantially in several sections. Similar final reconstruction losses can lead to materially different mSCF1 values, so the reconstruction objective is not a reliable proxy for downstream peak quality at this short stopping point.

The collection-level mean is more stable than several section-level values: **0.300**, **0.306** and **0.339** for initialization seeds 1–3. This does not erase section instability. It shows that positive and negative section movements partly cancel when averaged.

The earlier 25/50-epoch diagnostic explains one mechanism. Seeds 1 and 2 reproduced their first ten losses exactly, then their peak sets and scores converged with longer training. The exceptional 10-epoch score was therefore a transient caused by initialization and early stopping, not sample-order randomness.

## S3PL reporting rule

- Never choose the best seed per section or quote it as the reproduced baseline.
- Report every declared initialization seed.
- Report section mean, sample SD, range and selected-peak overlap.
- Report collection aggregation separately from section-level variation.
- Keep tissue section and patient as distinct units; paired sections from one patient are not independent patients.
- Describe the released 10-epoch GBM protocol as initialization-sensitive. Do not silently replace it with a longer protocol when comparing with the paper.
- Keep the unreproduced paper value as a contextual reference, not as measured evidence from this pipeline.

## Native workflow runtime repetitions

All three measurements used `160TopL` on an NVIDIA GeForce RTX 3060 and each method's existing native protocol.

| Job | S3PL full workflow (s) | VAE training (s) | VAE attribution (s) | VAE scoring (s) | VAE total (s) |
|---:|---:|---:|---:|---:|---:|
| 65630 | 151.18 | 83.21 | 13.29 | 38.80 | 135.30 |
| 65854 | 173.90 | 90.33 | 27.94 | 3.36 | 121.63 |
| 65855 | 173.87 | 88.74 | 29.82 | 3.31 | 121.87 |

The VAE workflow used less total wall time in all three measurements. S3PL maximum resident memory was approximately 1.31–1.32 GiB and its sampled whole-device GPU memory was 315 MiB. The maximum VAE stage used approximately 1.15–1.18 GiB and 237 MiB. The stable memory values are stronger evidence than small timing differences between individual stages. The scoring and attribution timings vary with process and filesystem state, which is why complete-workflow totals and repeated measurements are retained.

This is a **native-workflow cost comparison**, not an equal-work or intrinsic-efficiency comparison. S3PL and the VAE use different architectures, objectives and peak-selection procedures; S3PL trains for 10 epochs and the VAE for 100. The valid claim is that both workflows are in the same broad operational range on this section and hardware, and that the VAE workflow was faster and used slightly less sampled memory in these three runs.

## Decision

The S3PL reproduction gap should no longer block the principal report. It has become a bounded result: the executable 10-epoch GBM baseline is section- and initialization-sensitive, and its paper-level GBM score remains unreproduced. Comparisons must use declared multi-seed summaries rather than a favourable run.

No further large campaign is justified before synthesis. The next work is to incorporate these results into the main figures, tables and claims, then identify whether any remaining experiment can change a principal conclusion rather than merely add another diagnostic.

## Evidence

- [Machine-readable synthesis](../../../code/msi/results/comparisons/s3pl_gbm_stability_runtime/summary.json)
- [Per-run seed table](../../../code/msi/results/comparisons/s3pl_gbm_stability_runtime/s3pl_gbm_seed_screen.csv)
- [Per-section seed summary](../../../code/msi/results/comparisons/s3pl_gbm_stability_runtime/s3pl_gbm_seed_summary.csv)
- [Runtime-stage table](../../../code/msi/results/comparisons/s3pl_gbm_stability_runtime/runtime_repeats.csv)
- [GBM stability figure](../../../results/model-comparisons/s3pl_gbm_seed_stability.png)
- [Native runtime figure](../../../results/model-comparisons/s3pl_vae_native_runtime_repeats.png)
- [Rebuild script](../../../code/msi/scripts/summarise_s3pl_gbm_stability_runtime.py)

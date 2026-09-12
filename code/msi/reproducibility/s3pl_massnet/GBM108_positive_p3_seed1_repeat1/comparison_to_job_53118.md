# GBM108_positive p=3 deterministic repeat comparison

## Runs

- Original: Slurm job `53118`
- Repeat: Slurm job `53146`
- Dataset: `GBM108_positive`
- Configuration: ten epochs, spatial patch size 3, 256 selected-peak target, random seed 1
- Repeat artifact root: `/home-mscluster/zsuliman/msi/reproducibility/s3pl_massnet/GBM108_positive_p3_seed1_repeat1`

## Exact comparisons

| Artifact or value | Result |
|---|---|
| Metrics JSON | SHA-256 identical |
| Picked-peaks CSV | SHA-256 identical |
| Peak-evaluation report | SHA-256 identical |
| Ten-epoch training-loss sequence | Exactly identical |
| Configuration excluding `artifact_root` | Exactly identical |
| Picked peaks | 581 in both runs |
| Candidate peaks before cutoff | 4,555 in both runs |
| F1@0.3 | 0.04602235371466141 in both runs |
| F1@0.4 | 0.03098106712564544 in both runs |
| F1@0.5 | 0.034858387799564274 in both runs |
| F1@0.6 | 0.02197802197802198 in both runs |
| mSCF1 | 0.033 in both runs |
| Peak allocated GPU memory | 315,762,176 bytes in both runs |

The configuration JSON files are not byte-identical only because `artifact_root` deliberately points to different output locations.

## Runtime

| Run | Training seconds | Evaluation seconds | Total seconds |
|---|---:|---:|---:|
| `53118` | 494.919 | 73.909 | 583.417 |
| `53146` | 511.309 | 75.554 | 600.024 |

The repeat took 16.607 seconds longer overall (2.85%), which is normal operational timing variation and did not change any scientific output.

## Log validation

Job `53146` completed all 2,071 evaluations. No traceback, CUDA out-of-memory error, NaN/Inf result, exception, cancellation, or killed process was detected. The stdout reports an NVIDIA GeForce RTX 3090, 85,062 input channels, 470 trainable parameters, and the expected isolated checkpoint path.

## Conclusion

The anomalous `GBM108_positive` p=3 result is deterministically reproducible under the current fixed-seed pipeline. The result is therefore not explained by a transient node problem or ordinary random-seed instability. A seed sweep is not the next experiment. The next investigation should audit systematic factors: HDF5 coordinate interpretation, mask orientation/alignment, spatial-neighbour construction at p=3, preprocessing equivalence, and the exact dataset/version assumptions behind the paper's aggregate.

The repeat checkpoint was not included in the local sync, so model-weight hashes were not compared. This does not weaken the observed output-level determinism: the full loss sequence, selected peaks, evaluation report, and metrics are identical.

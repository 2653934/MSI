# Neighbourhood window and control implementation

Status: 1 October 2026. Implementation foundation prepared; cluster numerical tests pending. No new window training results exist yet.

## Where we are

The [two-week plan](09%20Two-Week%20Spatial%20Model%20Investigation%20Plan.md) remains our direction. The [runtime investigation](10%20GBM%20Training%20Runtime%20Investigation.md) identified repeated HDF5 reads as the major historical training bottleneck. Cached GBM108_positive training preserved the centre/uniform histories and final tensors exactly. The [S3PL phase audit](11%20S3PL%20Architecture%20and%20Runtime%20Audit.md) distinguishes preparation from GPU work. The [CAC gap diagnostics](12%20CAC%20S3PL%20Gap%20Diagnostics.md) confirmed identical reference peak sets; differing selected peaks explain the score arithmetic, but not yet the architectural cause.

Notion tasks 15, 17 and 18 are now in progress. Their full acceptance criteria are not complete: shuffled context, window experiments, causal quality diagnosis and complete evaluation-phase profiling remain open.

## What the next controls mean

| Comparison | Question |
|---|---|
| Uniform 3×3 vs uniform 5×5 | Does access to a wider spatial scale change reconstruction and peak selection? |
| Uniform vs zero context, both with a 2D-wide encoder | Does access to neighbours help beyond the same nominal encoder size? |
| Uniform vs reproducibly shuffled context (not implemented yet) | Is any benefit specific to local spatial relationships rather than extra spectral input? |
| Centre-only D-wide encoder vs zero-context 2D-wide encoder | What changes when the nominal input layer is larger but no neighbour signal is supplied? |

Here D is the number of spectral bins, not the number of pixels. A 5×5 window has 24 possible neighbours, but averaging them still gives a D-vector. Thus uniform 3×3 and 5×5 have identical VAE parameter counts and input width, although preparation and temporary neighbour tensors are larger for 5×5.

Zero context feeds `[centre, zeros]`. It has the same stored parameters as uniform, and its VAE initialization is identical under the same seed. However, the context-side encoder weights receive zero data gradients: equal nominal parameter count is not equal usable capacity. This control cannot on its own exclude every capacity explanation.

For measured neighbour set N(i), the uniform context is:

$$
c_i = \frac{1}{|N(i)|}\sum_{j\in N(i)}\operatorname{TIC}(x_j),
\qquad c_i=0\text{ when }|N(i)|=0.
$$

The model aggregator then TIC-renormalizes this mean, preserving the existing implementation (relevant if measured neighbours include zero-TIC spectra). Missing coordinates are not treated as zero-intensity measured tissue and are excluded from the denominator. The centre is excluded. A 1×1 window has no neighbours; the D-wide centre-only model and 2D-wide zero-context model remain distinct architectures.

## Code changes and compatibility

- [preprocessing.py](../../code/msi/src/spatial_msipl/preprocessing.py): odd square offsets, variable measured-neighbour slots, configurable cached/streamed loader; default remains 3×3 with historical slot order.
- [neighbourhood.py](../../code/msi/src/spatial_msipl/neighbourhood.py): uniform/attention accept variable slots, empty windows return finite zero context, zero-context strategy added. Depthwise remains eight-position/3×3 only.
- [model.py](../../code/msi/src/spatial_msipl/model.py): explicit window and input-slot validation; non-default windows recorded in model configuration. Default 3×3 configuration is unchanged.
- [training.py](../../code/msi/src/spatial_msipl/training.py): non-default dataset window enters the resume signature to prevent incompatible resumes.
- [training entry point](../../code/msi/scripts/train_spatial_msipl_production.py): exposes window size and zero-context options. This is not authorization to overwrite existing baseline output directories.
- [window tests](../../code/msi/src/spatial_msipl/tests/test_windows.py): independent distance-based neighbour membership, holes/boundaries, both HDF5 orientations, streamed/cache equality, masked gradients, equal initialization/parameter counts and zero-control invariance.

Local Python AST, shell syntax and diff-whitespace checks passed. Seventy-two independent NumPy neighbour-membership checks passed across 1×1, 3×3 and 5×5 windows on a synthetic grid with a missing pixel. The local WSL runtime lacks PyTorch and h5py, so the complete numerical suite must run in the existing cluster environment; it has not been claimed as passed.

## Immediate next step: CPU-only tests

Upload the changed code using the usual local-to-cluster command from `code/msi`, then on the cluster:

```bash
cd ~/msi
sbatch slurm_jobs/check_spatial_window_implementation.sh
```

After it finishes (replace JOB_ID):

```bash
sacct -j JOB_ID --format=JobID,State,Elapsed,NodeList,ExitCode
cat logs/window-tests-JOB_ID.out
cat logs/window-tests-JOB_ID.err
```

Expect `WINDOW IMPLEMENTATION TESTS PASSED`, unittest `OK`, and job exit 0:0. Unittest progress is normally written to stderr; a nonempty `.err` is not itself a failure. This CPU-only job needs no CUDA quarantine, raw data or production checkpoints.

## Before production experiments

1. Pass the numerical suite and a checkpoint/resume canary with non-default window metadata.
2. Implement a reproducible shuffled-context control without using class masks; record the permutation and seed in provenance/resume metadata.
3. Extend evaluation/checkpoint reconstruction to the new configurations. Existing evaluation scripts must not silently reconstruct a 5×5 or zero-context checkpoint as default 3×3 uniform.
4. Freeze one GBM and one CAC development section, window/control arms, seed, batch, 100-epoch objective, matched peak counts, IG settings and resource limits in a separate protocol. Evaluate reconstruction **and** peak quality: reconstruction alone cannot select the winning peak picker.
5. Use separate experiment/checkpoint roots. Confirm promising or informative findings on other sections/seeds without changing the frozen scoring rules.

No new cluster production command is supplied yet: we are testing the implementation before spending time on interpretation.

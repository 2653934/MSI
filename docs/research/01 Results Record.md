# Results Record

Last updated: 2026-10-15

> **Note (15 October 2026): this executive summary is superseded in part by the 9–10 October fair-scoring results.** See [Fair-scoring gates (a)/(b)](#fair-scoring-gates-ab-9-october-2026) and [Gate (d) attribution-pixel count](#gate-d-attribution-pixel-count-910-october-2026) at the end of this record. Under fair scoring, IG still beats legacy msiPL, but it does not beat the no-IG posterior-correlation baseline, which ranks bins by correlation with the same GMM posterior. The claims below are not rewritten yet; the framing waits for the supervisor meeting on 19 October.

This is the main results ledger. Values are copied from the committed JSON and
CSV outputs. “Complete” means the planned computation and audit finished; it
does not automatically mean the scientific hypothesis was supported.

## Executive summary

- Both datasets were inspected, visualised and aligned with their masks.
- Legacy msiPL was reproduced on all eight GBM and eight CAC sections.
- The tuned msiPL reproduction is descriptively consistent with the published
  Weigand et al. aggregate on both collections.
- The S3PL GBM reproduction remains below the paper value despite format and
  normalisation checks; this gap is documented rather than hidden.
- Three spatial neighbourhood mechanisms were tested. Their development-section
  representation scores were very similar, so the parameter-free uniform mean
  was frozen as the simplest *baseline* for the initial validation, not
  established as the best spatial method.
- Across all eight GBM sections, uniform spatial context did **not** consistently
  improve reconstruction over a centre-only VAE.
- Across all eight GBM sections, nonlinear Integrated Gradients from both the
  spatial and centre-only VAEs selected better peaks than legacy msiPL.
- The matched centre-only control found no consistent peak-selection advantage
  from neighbourhood context. *(Corrected 15 October 2026.)* The IG gain over
  legacy msiPL holds under fair scoring (8/8 sections in every arm and
  collection). But IG does not beat the no-IG posterior-|PCC| baseline, which
  ranks bins by correlation with the same GMM posterior: it is below that
  baseline in all 32 section-arms at bin level. So the gain cannot be credited
  to nonlinear attribution itself.

## Dataset validation

### MassNet GBM

All eight HDF5 sections contain a shared 85,062-bin m/z axis from approximately
101.924 to 999.986. Expert H&E annotations distinguish normal and tumour tissue.
Coverage ranges from 54.62% to 82.95% because unmeasured grid positions exist.

The reconstructed HDF5 masks and official imzML masks had zero semantic
disagreements across every measured pixel. Their numeric encodings differ, but
their biological meaning does not.

![GBM masks and coverage](../../code/msi/results/visualisations/gbm_massnet/gbm_massnet_overview_masks.png)

![Official GBM masks](../../code/msi/results/visualisations/gbm_imzml_comparison/official_masks_overview.png)

### CAC

The eight CAC sections have 1,481 bins and three mask classes. Seven sections
have complete rectangular MSI coverage. `280TopL` has 4,160 measured spectra on
a 4,623-pixel grid, or 89.98% coverage; processing therefore uses measured
coordinates rather than assuming a dense grid.

![CAC 40TopL TIC and mask](../../code/msi/results/visualisations/cac/40TopL/tic_mask_overlay.png)

![CAC 280TopL partial coverage](../../code/msi/results/visualisations/cac/280TopL/msi_coverage.png)

## Legacy msiPL reproduction

The first complete run used the legacy VAE-BN and LearnPeaks implementation.
Subsequent beta selection produced the paper-aligned comparison used as the
main msiPL reproduction.

| Collection | Initial mean mSCF1 | Tuned mean mSCF1 | Paper mean | Paper 95% interval | Tuned result inside interval? |
|---|---:|---:|---:|---:|---|
| GBM | 0.364 | 0.414 | 0.403 | 0.330–0.475 | Yes |
| CAC | 0.219 | 0.402 | 0.431 | 0.391–0.479 | Yes |

Interval membership is descriptive consistency, not statistical equivalence or
proof that every undocumented detail of the paper was reproduced.

![Tuned msiPL versus Weigand et al.](../../code/msi/results/comparisons/msipl_weigand_2026_tuned/msipl_weigand_comparison.png)

## S3PL reproduction

### CAC

S3PL was successfully executed across the CAC sections using the repository’s
10-epoch configuration. The first completed `40TopL` run produced mSCF1 0.687
with 342 selected peaks and demonstrated that the adapter, masks and evaluation
path worked. The remaining sections were then completed.

### MassNet GBM

The paper-aligned spatial patch size is 3. With the released-code spatial-maximum
normalisation, the eight-section mean mSCF1 was 0.3155, versus 0.496 reported in
the paper. Paper-described TIC normalisation produced 0.28875. An earlier
patch-size-9 transfer run produced 0.3461 but is not paper-aligned.

Official imzML pilots also failed to close the gap:

- `GBM108_positive`: 0.033 in HDF5 versus 0.027 in official imzML.
- `GBM108_negative`: 0.664 in HDF5 versus 0.655 in official imzML.

Therefore the discrepancy is unlikely to be explained by HDF5 conversion,
mask geometry, coordinate order or simply switching to official imzML. The
executable baseline is retained, while the published value is not claimed as
reproduced.

![S3PL GBM patch-3 performance](../../code/msi/results/baselines/s3pl/massnet_gbm_summary_p3/performance_overview.png)

## Spatial-msiPL neighbourhood development

Three ways of summarising the eight-position Moore neighbourhood were compared
on `GBM108_positive` after matched 100-epoch training.

| Variant | Balanced accuracy | Macro F1 | ROC AUC | GMM ARI | Mean Moran’s I |
|---|---:|---:|---:|---:|---:|
| Uniform mean | 0.890 | 0.890 | 0.962 | 0.644 | 0.744 |
| Depthwise | 0.892 | 0.892 | 0.962 | 0.641 | 0.740 |
| Attention | 0.894 | 0.894 | 0.965 | 0.629 | 0.744 |
| Attention, sqrt-bin scaling | 0.885 | 0.885 | 0.960 | 0.630 | 0.746 |

The differences were small and inconsistent across metrics. Uniform mean has no
learnable neighbourhood parameters, is orientation-free and is easier to
explain. It was therefore frozen for broader validation rather than choosing a
more complex method from a marginal development-section difference.

![Neighbourhood comparison](../../code/msi/results/experiments/spatial_msipl_neighbourhood_evaluation/GBM108_positive_seed1/neighbourhood_comparison.png)

## Spatial-loss and Poisson development gates

Adding explicit adjacent-latent MSE reduced neighbour latent distances, but
stronger penalties worsened reconstruction and did not consistently improve
the held-out spatial probe. This showed that spatial smoothness can be forced
without necessarily creating a better representation.

![Spatial-loss pilots](../../code/msi/results/experiments/spatial_msipl_spatial_loss_evaluation/GBM108_positive_seed1/spatial_loss_pilot_comparison.png)

Poisson augmentation passed the allowed clean-reconstruction regression rule
but failed the predeclared requirement for at least 1% improvement on noisy
inputs. Its observed noisy-MSE change was only about 0.022%, so it was not
promoted into the frozen production method.

![Poisson augmentation pilot](../../code/msi/results/experiments/spatial_msipl_poisson_evaluation/GBM108_positive_seed1/poisson_pilot_comparison.png)

## Whole-GBM reconstruction validation

All 14 new frozen configurations—uniform mean and centre-only for the seven
non-development sections—completed 100 epochs and passed the strict audit.
Together with `GBM108_positive`, this gives eight paired sections.

| Section | Uniform-mean MSE change vs centre-only |
|---|---:|
| GBM108_positive | +15.97% |
| GBM108_negative | −0.68% |
| GBM12_1 | −3.80% |
| GBM12_2 | +7.50% |
| GBM22_1 | −3.58% |
| GBM22_2 | −36.20% |
| GBM39_1 | +1.92% |
| GBM39_2 | +1.72% |

Negative means uniform mean reconstructed better. The result is mixed:

- MSE wins: 4 uniform mean, 4 centre-only.
- Mean relative change: −2.14%, heavily influenced by `GBM22_2`.
- Median relative change: +0.52%, slightly favouring centre-only.
- Paired Wilcoxon MSE p-value: 0.945.
- Mean cosine change: +0.000114.
- Mean training-runtime ratio: 1.002.

Uniform mean uses 130,751,056 parameters versus 87,199,312 for centre-only and
about 2.90 GiB versus 2.05 GiB peak allocated GPU memory. The defensible result
is that spatial context does not consistently improve reconstruction and costs
more memory. Its value must be judged through representation and peak quality.

![Whole-GBM reconstruction validation](../../code/msi/results/experiments/spatial_msipl_gbm_validation/reconstruction/reconstruction_validation.png)

## Nonlinear peak attribution pilot

On frozen `GBM108_positive`, a two-component label-free GMM was fitted to the
five-dimensional latent means. Integrated Gradients then attributed each GMM
posterior through the complete nonlinear encoder to the central spectrum and
its neighbourhood context.

At a matched budget of 530 bins:

| Method | mSCF1 |
|---|---:|
| Spatial-msiPL Integrated Gradients | 0.528 |
| Legacy msiPL | 0.404 |
| First-layer L2 | 0.068 |

The GMM-to-mask balanced accuracy was 0.893, ARI was 0.644 and NMI was 0.545.
Integrated Gradients passed its numerical completeness check. Deleting its
high-ranked bins caused much larger posterior drops than deleting L2-ranked or
random bins, supporting faithfulness on this development section.

![Matched peak evaluation](../../code/msi/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1/uniform_mean/matched_mscf1_comparison.png)

![GMM and expert mask](../../code/msi/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1/uniform_mean/gmm_expert_mapping.png)

![Attribution deletion faithfulness](../../code/msi/results/experiments/spatial_msipl_gmm_integrated_gradients/GBM108_positive_seed1/uniform_mean/deletion_faithfulness.png)

## Attribution sampling stability

Four attribution-pixel sampling runs produced mean mSCF1 0.533, standard
deviation 0.0137 and range 0.0310. Pairwise Jaccard similarity for the complete
530-bin sets was roughly 0.78–0.86. This indicates stable conclusion-level peak
quality and substantial, though not perfect, exact-set stability.

![Attribution sampling stability](../../code/msi/results/experiments/spatial_msipl_attributed_peak_evaluation/GBM108_positive_seed1/sampling_stability/attribution_sampling_stability.png)

## Whole-GBM nonlinear peak attribution

The frozen uniform-mean Spatial-msiPL model was evaluated on all eight MassNet
GBM sections. Each section used its own legacy msiPL peak count, so every method
was scored at an identical section-specific selection budget.

| Method | Mean mSCF1 | Standard deviation | Median |
|---|---:|---:|---:|
| Spatial-msiPL Integrated Gradients | **0.456** | 0.090 | 0.474 |
| Legacy msiPL | 0.364 | 0.075 | 0.381 |
| First-layer L2 | 0.214 | 0.112 | 0.219 |

Integrated Gradients beat legacy msiPL on all eight sections. The mean absolute
gain was 0.0919 mSCF1 (25.2% relative), with paired section-level Wilcoxon
`p = 0.0078125`. Direction consistency and effect sizes are primary because the
eight sections are not asserted to be eight independent patients.

Integrated Gradients beat the deliberately simple first-layer L2 comparator on
seven of eight sections. `GBM12_1` was the exception. Legacy msiPL is not
equivalent to this L2 comparator: LearnPeaks also traces a selected hidden
neuron toward each latent feature, scales by spectral variability, thresholds
candidates and snaps them to local spectral maxima.

The label-free GMM had mean balanced accuracy 0.911 against the expert masks.
All eight Integrated Gradients completeness checks passed.

![Whole-GBM attributed peak validation](../../code/msi/results/experiments/spatial_msipl_gbm_validation/attributed_peaks/attributed_peak_validation.png)

## Matched centre-only attribution control

The same GMM-targeted Integrated Gradients procedure was applied to the frozen
100-epoch centre-only VAEs. Section, seed, hidden and latent dimensions, GMM
settings, attribution settings and peak budget were matched. The intended
difference was the encoder input: centre spectrum alone versus centre plus
uniform-mean neighbourhood context.

| Method | Mean mSCF1 | Standard deviation | Median |
|---|---:|---:|---:|
| **Centre-only IG** | **0.4665** | 0.0820 | 0.4935 |
| Spatial IG | 0.4562 | 0.0898 | 0.4743 |
| Legacy msiPL | 0.3643 | 0.0749 | 0.3809 |
| Spatial first-layer L2 | 0.2139 | 0.1124 | 0.2191 |

Spatial IG won five sections and centre-only IG won three. The mean spatial
minus centre-only change was -0.0103 mSCF1, while the median change was +0.0067.
The paired Wilcoxon result was `p = 0.9453125`. The correct conclusion is that
neighbourhood context did not provide a consistent peak-selection benefit.
The positive median and 5-3 win count show small spatial gains were common, but
two larger centre-only wins (`GBM22_2` and `GBM39_2`) reversed the mean.

Centre-only IG beat legacy msiPL on all eight sections. Its mean improvement
was 0.1022 mSCF1, approximately 28.1% relative, with paired Wilcoxon
`p = 0.0078125`. Spatial IG also beat legacy on all eight sections. Together,
these results identify nonlinear attribution, rather than neighbourhood input,
as the robust source of improved GBM peak selection.

Spatial context may still affect representation structure. Mean GMM balanced
accuracy was 0.9113 for spatial models versus 0.8676 for centre-only models,
although the centre-only mean was strongly reduced by `GBM12_1` (0.3214).
This possible representation-level effect did not translate into a consistent
mSCF1 advantage.

Every centre-only run used a 100-epoch checkpoint, passed all 37 tests, reported
`status: valid`, passed IG completeness and produced the exact matched peak
count. The aggregate summary completed without errors.

![Matched centre-only attribution control](../../code/msi/results/experiments/spatial_msipl_gbm_validation/context_attribution_control/context_attribution_control.png)

## Frozen CAC validation

The GBM-selected uniform-mean Spatial-msiPL method was frozen and applied to
all eight CAC sections without section-by-section retuning. Each spatial model
was paired with a centre-only model trained for the same 100 epochs, and peak
selection used the same nonlinear GMM-targeted Integrated Gradients procedure.
Legacy msiPL, the two IG methods and S3PL were evaluated at the same
section-specific peak count. S3PL reused its existing ten-epoch checkpoints;
only its final evaluation count was changed, so no S3PL retraining was needed.

| Method | Mean CAC mSCF1 |
|---|---:|
| **S3PL reproduction (matched peak count)** | **0.5915** |
| **Spatial-msiPL IG** | **0.5595** |
| Centre-only IG | 0.5285 |
| Legacy msiPL | 0.4024 |
| Centre-only first-layer L2 | 0.0238 |
| Spatial first-layer L2 | 0.0079 |

Spatial IG beat centre-only IG on all eight CAC sections. The mean absolute
gain was 0.0310 mSCF1 and the exact paired Wilcoxon result was
`p = 0.0078125`. Spatial IG also beat legacy msiPL on all eight sections, with
a mean gain of 0.1572 and the same exact paired `p = 0.0078125`. These are
strong directionally consistent results, while still being interpreted as
section-level evidence rather than eight independent-patient replications.

Against matched-count S3PL, spatial IG won two of eight sections and averaged
0.0320 lower mSCF1. Re-evaluating S3PL at the shared peak counts changed its
mean only from 0.5908 to 0.5915. The earlier peak-count mismatch therefore did
not explain the performance gap. S3PL remains the strongest CAC baseline in
this executable comparison, while its ten-epoch architecture and training
protocol differ from the 100-epoch VAE experiments.

The context benefit was specific to nonlinear peak ranking. Mean GMM balanced
accuracy was 0.6690 for spatial models and 0.6845 for centre-only models
(`p = 0.25`). Reconstruction MSE split four wins each (`p = 1.0`). Spatial IG
had higher deletion faithfulness in six of eight sections, with a mean gain of
0.0405 (`p = 0.078125`). Thus neighbourhood context did not universally
improve reconstruction or latent clustering, but it consistently changed the
nonlinear attribution ranking in a way that improved CAC mSCF1.

Mean training time was 128.4 seconds for spatial models and 125.0 seconds for
centre-only models, both at 100 epochs. S3PL averaged 55.1 seconds at 10 epochs,
so those raw times must not be presented as per-epoch-equivalent. Mean reported
GPU allocation was 68.7 MiB for spatial, 53.3 MiB for centre-only and 97.0 MiB
for S3PL; this is allocated tensor memory, not total device occupancy.

These are the **historical implementation runtimes**, not isolated neural-network
compute costs. Our VAE epoch timer includes HDF5 reads and TIC normalisation,
whereas the legacy msiPL GBM timer starts after loading an in-memory spectrum
matrix; the timing boundaries and the S3PL protocol differ too. A GBM108-positive
phase profile found data preparation dominated the VAE loop, and an opt-in
cache reduced measured batch preparation from 24.704 to 0.724 seconds without
changing checked sample arrays. That initial batch-only result did not, by
itself, establish a full-training speedup; the later full-run result below did.
The historical CAC runtimes above remain unchanged. See the
[runtime investigation](investigations/10%20GBM%20Training%20Runtime%20Investigation.md) for
timing boundaries and the still-needed cross-method cost comparison. GPU tensor
memory must also be reported separately from the extra host RAM used by caching.

A subsequent one-epoch GBM108-positive check using the actual VAE training loop
found 402.1 versus 12.7 seconds for centre-only and 400.8 versus 12.4 seconds
for uniform mean (streaming versus cached), with exactly equal losses and final
model tensors within each pair. That established the first **one-epoch**
implementation speedup; the 100-epoch test followed.

Separate cached 100-epoch GBM108-positive validations have now completed.
Centre-only and uniform mean took 1,309.0 and 1,355.4 seconds of summed epoch
time, respectively, versus 40,178.6 and 40,608.9 seconds in the frozen
streaming runs. Every shared per-epoch history field matched the corresponding
frozen run exactly across all 100 epochs; their initial model-state hashes
also matched. Script wall time to summary was 25.56 and 27.94 minutes for the
cached runs, including setup and checkpoints. This is an implementation/data
pipeline improvement, not a new peak-quality result.

The read-only cluster checkpoint audit subsequently found exact equality for
all 20 final model-state tensors in **both** centre-only and uniform-mean
GBM108-positive runs (job 61491). This closes the parameter-equivalence check
for those two cached-versus-streaming pairs. It does not, by itself, extend
the timing or equivalence result to the other GBM or CAC sections.

### S3PL and cached VAE phase probe

On one RTX 3090 node (`mscluster49`), job 61555 compared S3PL at its 16-pixel
batch size with the cached VAEs at their 128-pixel batch size on
`GBM108_positive`. Steady throughput was 42.1 pixels/s for S3PL and
148.0/149.7 pixels/s for centre-only/uniform VAE. Data preparation occupied
85.9%/92.5%/91.6% of the sampled batch time. Peak allocated GPU memory was
0.238/2.047/2.857 GiB, respectively. These are short training-batch probes,
not whole-workflow measurements; batch sizes and training objectives differ.
S3PL's shorter observed training total on this section uses 10 epochs versus
100 for the VAE. GMM, IG, peak selection and evaluation still need
consistently bounded end-to-end timing. See the
[architecture and timing audit](investigations/11%20S3PL%20Architecture%20and%20Runtime%20Audit.md)
and its [machine-readable phase results](../../code/msi/results/validation/s3pl_cached_vae_phases/61555/).

### Where the matched CAC S3PL lead occurs

At matched peak counts S3PL leads uniform-context IG in mean CAC mSCF1 by
about 0.032 and wins six of eight sections. The mean mixed-F1 lead is 0.0476,
0.0460, 0.0294 and 0.0048 at PCC thresholds 0.3, 0.4, 0.5 and 0.6.
The selected lists share 69.9%–84.6% of their m/z values by section
(mean 79.4%). A direct audit of the stored S3PL labels and independently
recomputed PCC references found *exactly the same* reference-positive bins
for all 32 section–threshold unions and all 96 class comparisons. At a fixed
count, the score difference therefore comes from peaks selected by only one
method. This identifies the set-level source of the gap; it does not identify
which architecture or training choice produced those selections.

![CAC S3PL versus IG F1 by threshold](../../results/model-comparisons/cac_s3pl_ig_thresholds.png)

![CAC selected-peak overlap](../../results/model-comparisons/cac_s3pl_ig_peak_overlap.png)

The [detailed CAC diagnostic](investigations/12%20CAC%20S3PL%20Gap%20Diagnostics.md)
links the [reference-set audit](../../code/msi/results/comparisons/s3pl_cac_gap_diagnostics/reference_set_audit.json)
and exploratory exclusive-ion images. The GBM S3PL paper-reproduction gap is
a separate unresolved question.

The cross-dataset conclusion is deliberately nuanced. Neighbourhood context
did not consistently improve peak selection on GBM, but it improved it on all
eight CAC sections. Nonlinear Integrated Gradients was the robust contribution
on both datasets. The value of neighbourhood context is therefore
dataset-dependent rather than universal.

![CAC matched peak-selection comparison](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_peak_selection_comparison.png)

![CAC context effects](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_context_effects.png)

![CAC computational comparison](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_computational_comparison.png)

## Targeted training-seed stability

The frozen `GBM108_positive` comparison was repeated with model-training seeds
2 and 3 for centre-only, uniform-mean and corrected-attention VAEs. Together
with seed 1, this gives three independently trained models per variant. The GMM
seed, attribution-pixel sampling seed, evaluation procedure and 530-peak budget
were fixed at 1 so that only model training changed.

| Variant | mSCF1 mean +/- sample SD | GMM balanced accuracy | IG deletion faithfulness | Peak GPU memory |
|---|---:|---:|---:|---:|
| Centre-only | 0.5120 +/- 0.0179 | 0.8745 +/- 0.0039 | 0.1120 +/- 0.0147 | 2.05 GiB |
| Uniform mean | 0.5250 +/- 0.0132 | 0.8735 +/- 0.0274 | **0.1224 +/- 0.0255** | 2.90 GiB |
| Corrected attention | **0.5454 +/- 0.0188** | **0.8822 +/- 0.0072** | 0.1179 +/- 0.0099 | 3.20 GiB |

Corrected attention beat uniform mean in all three training seeds. The
per-seed mSCF1 gains were +0.0347, +0.0120 and +0.0144, giving a mean gain of
+0.0204. This narrowly met the predeclared +0.02 peak-quality requirement.
Uniform mean beat centre-only in two of three seeds and averaged +0.0130, so
the simple context benefit was less stable on this development section.

The attention result did not pass the full predeclared gate. Its deletion
faithfulness was lower than uniform mean in two of three seeds and by 0.0045
on average. The defensible conclusion is therefore that corrected attention
produces a small, training-seed-consistent improvement in matched peak mSCF1 on
`GBM108_positive`, but we do not have evidence that its attribution is more
faithful. This targeted three-seed result does not replace the eight-section
seed-1 validation and should not be presented as whole-dataset multi-seed
replication.

![GBM108-positive training-seed stability](../../code/msi/results/experiments/spatial_msipl_training_seed_stability_summary/gbm108_positive_seed_stability.png)

## Spatial window and context controls (3 October 2026)

The seed-1 window campaign has complete local training, reconstruction,
attribution and peak-evaluation artifacts for all 48 configurations: 16
sections (eight CAC, eight MassNet GBM) times three new arms. The arms are a
real 5x5 uniform neighbourhood (`uniform_p5`), zeroed 3x3 context
(`zero_p3`), and a seeded nonlocal shuffled 3x3 context (`shuffled_p3`). Each
is compared with the previously frozen real 3x3 uniform model, using the
same section-specific matched peak count. The two development sections are
`40TopL` and `GBM108_positive`; the seven remaining sections in each
collection form the confirmation sets.

| Confirmation set, mean IG mSCF1 | Real 3x3 | Real 5x5 | Zero 3x3 | Shuffled 3x3 |
|---|---:|---:|---:|---:|
| Seven CAC sections | 0.5419 | 0.5352 | 0.5235 | 0.5425 |
| Seven MassNet GBM sections | 0.4460 | 0.4334 | 0.4594 | 0.4430 |

On CAC, the real 3x3 ranking exceeds zero context by 0.0184 mSCF1 on
average, but is essentially tied with shuffled context (-0.0006). On GBM,
real 5x5 is 0.0126 below real 3x3; zero context is 0.0134 above it, while
shuffled context is 0.0030 below it. The section-level results are mixed, so
these means do **not** show a robust spatial-specificity gain or that more
neighbours help. Equally, they do not prove spatial information is useless:
the controls perturb the input and are only one seed. In particular, the
strong earlier CAC real-3x3 versus centre-only result and the present
real-3x3 versus shuffled near-tie answer different questions and should both
be reported.

Source artifacts: [new window-arm evaluations](../../code/msi/results/experiments/spatial_msipl_window_pilot/), [frozen CAC real-3x3 evaluations](../../code/msi/results/experiments/spatial_msipl_cac_attributed_peak_evaluation/), and [frozen GBM real-3x3 evaluations](../../code/msi/results/experiments/spatial_msipl_attributed_peak_evaluation/). The local completion audit checks each arm's training `summary.json` (`complete`), attribution `summary.json` (`valid`), peak-evaluation `summary.json` (`complete`), and reconstruction JSON; cluster checkpoints were not synced locally. These are seed-1 descriptive comparisons, not a significance or multi-seed claim.

### What the shuffled input changes, and whether frozen models respond

A post-hoc, class-balanced input audit found that shuffled context is not
equivalent to real local context. For sampled centres classified post hoc as
interior from their real neighbours, the fraction of neighbours sharing the
centre's expert class was 1.000 for real context by construction
versus 0.317 for shuffled context on `160TopL`, and 1.000 versus 0.514 on
`GBM22_2`. The [input-information records](../../code/msi/results/diagnostics/spatial_context_information/)
also cover `200TopL` and `GBM39_2`; all four report `valid`. Expert classes
defined these diagnostic groups *after* the label-free context construction.

In a separate frozen-model intervention, the already trained real-context
models reconstructed their sampled training-section pixels worse when fed
shuffled instead of real context: mean scaled cross-entropy increased by 32.89
on `160TopL` and 7,713.04 on `GBM22_2`. The corresponding shuffled-trained
models favoured shuffled input by 6.53 and 421.48, respectively, on the same
cross-entropy scale. The [frozen-model records](../../code/msi/results/diagnostics/spatial_context_model_sensitivity/)
show the same direction separately for boundary and interior groups. These
results establish that the sampled inputs carry different local information
and that the saved models respond to it; they do **not** show that real context
improves peak selection. The swaps are out-of-training-distribution
interventions on training sections, not held-out performance or causal tests.
The saved-latent audit below separates representation, clustering and
peak-ranking effects.

### Saved latent information versus the fitted GMM

A label-free GMM was refitted five times to each saved five-dimensional latent
representation, then its components were compared with expert classes *post
hoc*. On `GBM22_2`, the saved real-context model's GMM had class ARI 0.165,
versus 0.888 for the shuffled-context model; the five refits stayed near
those values. Yet both saved representations had about 0.985 balanced accuracy
under a label-trained linear probe, and about 0.978 same-class ten-nearest-
neighbour purity. Thus expert-class information is accessible in both GBM
latents, while this particular unsupervised GMM partitions them very
differently. On `160TopL`, real/shuffled GMM ARI was 0.474/0.383, linear-probe
balanced accuracy 0.752/0.747, and ten-neighbour purity 0.760/0.762. See the
[latent-separability records](../../code/msi/results/diagnostics/spatial_latent_separability/)
for the saved-model hashes, counts and refit seeds.

The probe uses expert labels and five random pixel folds within the *same
training section*. Nearby pixels and the same patient/section can occur in
both train and test folds, so its accuracy is not patient-independent
validation and is **not** an unsupervised result. ARI and neighbour purity
also use labels only for post-hoc assessment; none of these diagnostics is a
peak-picking score or a causal explanation for mSCF1. A subsequent
[frozen-latent clusterer audit](../../code/msi/results/diagnostics/spatial_unsupervised_clusterers/)
compared covariance structures and KMeans without retraining or selecting by
expert labels. Full-covariance GMM still had the lowest BIC on both tested
sections; on `GBM22_2` real context, a tied-covariance GMM had much higher
post-hoc class ARI (0.899 versus 0.165) but substantially worse BIC. Thus
changing the clusterer solely to improve agreement with the expert mask would
be label-guided method selection, not an unsupervised correction. The completed
48-arm window campaign does not support promoting fixed uniform averaging
as the final spatial method; it remains a useful control while learned
neighbourhood mechanisms are investigated.

### Targeted learned-attention context check (4 October 2026)

Matched real-context and seeded nonlocal shuffled-context attention models
were trained for 100 epochs at seed 1 on `160TopL` and `GBM22_2`. All four
local training, reconstruction, attribution and peak-evaluation summaries
report complete or valid status. At the frozen section peak count, Integrated
Gradients gave:

| Section | Peaks | Real attention mSCF1 | Shuffled attention mSCF1 |
|---|---:|---:|---:|
| `160TopL` | 210 | 0.4662 | 0.4618 |
| `GBM22_2` | 464 | 0.4364 | 0.4422 |

The real-minus-shuffled differences are +0.0044 and -0.0058 respectively;
these two single-seed sections do not establish a consistent spatial-specific
peak-selection advantage for learned attention. On `GBM22_2`, post-hoc GMM
class ARI was 0.147 for real attention and 0.204 for shuffled attention, so
the earlier uniform-mean model's large shuffled-GMM advantage does not simply
carry over to this learned aggregator. See the
[four attention result sets](../../code/msi/results/experiments/spatial_attention_context/).
The following frozen-model ablation separates the Integrated Gradients
contributions of the centre and neighbour input branches without retraining.

### Frozen attention Integrated Gradients contribution ablation

For each saved attention model, only the *ranking score* changed: combined,
centre contribution alone, or neighbour contribution alone. The model,
fitted GMM, IG target and sampled pixels stayed fixed within an arm. Both
[ablation summaries](../../code/msi/results/diagnostics/spatial_ig_component_ablation/)
are valid and reproduce the original combined ranking exactly.

| Section and context | Matched bins | Combined mSCF1 | Centre-only mSCF1 | Neighbour-only mSCF1 |
|---|---:|---:|---:|---:|
| `160TopL` real | 210 | 0.4662 | 0.4593 | 0.4507 |
| `160TopL` shuffled | 210 | 0.4618 | 0.4593 | 0.4232 |
| `GBM22_2` real | 464 | 0.4364 | 0.4306 | 0.4252 |
| `GBM22_2` shuffled | 464 | 0.4422 | 0.4545 | 0.3122 |

Real-neighbour-only rankings beat shuffled-neighbour-only rankings on both
sections, by 0.0275 and 0.1130 mSCF1. Yet the combined real-versus-shuffled
comparison remains mixed. Central input also accounts for the larger share
of absolute IG magnitude in every GMM component: 0.598-0.703 in real and
0.739-0.755 in shuffled `160TopL` models; 0.532-0.576 in real and
0.702-0.742 in shuffled `GBM22_2` models. These are contributions within
*jointly trained contextual models*, not scores from separately trained
centre-only and neighbour-only models. The real and shuffled arms have their
own trained weights and GMMs, so their component-ranking difference is not
causal proof that spatial topology improves peak selection. A bounded
same-checkpoint input-swap or topology counterfactual is the next logical
test before asserting spatial specificity.

### Frozen learned-attention neighbour-input swap (5 October 2026)

The [16 section summaries](../../code/msi/results/diagnostics/spatial_attention_input_swap/)
all report `valid` (eight CAC, eight MassNet GBM), with complete saved
real-attention training summaries. For each section, the diagnostic held the
trained real-attention checkpoint and a GMM fitted once on its real-input
latents fixed, then replaced the neighbour slots with the seeded nonlocal
shuffle. It did not retrain either model or refit the GMM between conditions.

Shuffled-input reconstruction MSE was higher in **all 16 sections**:
**1.36–3.38 times** the real-input MSE. The fixed GMM changed its assigned
component for a mean **4.27% of CAC pixels** and **8.48% of GBM pixels**
(unweighted section means). Thus the learned-attention model responds to
neighbour inputs even when its parameters and clusterer are held constant.
This is an in-sample response to an intervention that may be outside the
real-neighbour training distribution. It is **not** a demonstration that
spatial topology improves selected peaks: no Integrated Gradients ranking,
matched-count mSCF1, or molecular interpretation was recomputed in this
diagnostic. The separately trained real-versus-shuffled attention pilots and
the component-ranking ablation above remain mixed on peak quality.

### Frozen attention peak-ranking input swap (5 October 2026)

The [16 ranking-swap summaries](../../code/msi/results/diagnostics/spatial_attention_frozen_ranking_swap/)
report `valid`. Each test reused one real-neighbour-trained attention
checkpoint, its real-input GMM, the same attribution pixels and component
targets, and the same section-specific peak budget. Only the neighbour spectra
were shuffled when recomputing Integrated Gradients. The original real-input
peak order and mSCF1 were reproduced exactly before scoring the shuffled
ranking. These are *same-model input interventions*, unlike the separately
trained real-versus-shuffled comparison above.

| Development section | Matched bins | Real-input mSCF1 | Shuffled-input mSCF1 | Shared selected bins |
|---|---:|---:|---:|---:|
| `160TopL` | 210 | 0.4662 | 0.4843 | 179 |
| `GBM22_2` | 464 | 0.4364 | 0.4678 | 411 |

At PCC thresholds 0.3, 0.4, 0.5 and 0.6, the shuffled ranking added
**9, 4, 0, 0** matched true-positive bins on `160TopL` and
**13, 19, 23, 23** on `GBM22_2`, respectively, compared with the frozen
real ranking. Integrated Gradients completeness passed in both sections.
Across all 16 sections, the real ranking was better on 4/8 CAC and 1/8 GBM
sections; the shuffled ranking was better on 4/8 CAC and 7/8 GBM sections.
The mean shuffled-minus-real mSCF1 difference was +0.0049 on CAC and +0.0183
on GBM. Neighbour input changes some peak choices, but the effect is mixed on
CAC and usually does not favour *real* neighbours on GBM. Because the
checkpoint was trained on real neighbours, shuffled inputs may be out of
distribution. These are seed-1 section-level observations, not a causal
demonstration that shuffling improves the method.

### Changed-peak audit of the frozen attention ranking swap (5 October 2026)

The [16 CPU-only changed-peak audits](../../code/msi/results/diagnostics/spatial_attention_changed_peaks/)
report `valid` and reproduced both frozen mSCF1 scores for every section. The
`changed_bins.csv` files identify every bin entering or leaving the selected
list, its m/z, per-class PCC and status under the existing four-threshold
reference rule. The figures show all changed-bin PCC distributions and the
highest-ranked three entering and three leaving ion images per section;
individual ion maps are scaled separately and are qualitative illustrations.

| Example section | Entering / leaving bins | Net reference-positive entering minus leaving at PCC 0.3, 0.4, 0.5, 0.6 |
|---|---:|---|
| `160TopL` | 31 / 31 | +9, +4, 0, 0 |
| `240TopL` | 37 / 37 | −10, −11, −9, −3 |
| `400TopL` | 28 / 28 | +13, +6, +3, 0 |
| `GBM12_2` | 53 / 53 | +30, +34, +35, +26 |
| `GBM22_2` | 53 / 53 | +13, +19, +23, +23 |

The changed reference-positive counts explain the score differences under
the existing four-threshold rule: some sections gain and others lose when the
ranking is recomputed with shuffled neighbours. Two of the highest-ranked
`GBM22_2` entering ion maps (m/z 541.904 and 399.971) visibly concentrate in the expert tumour
region and have positive tumour-class PCCs of 0.789 and 0.763. This is
post-hoc evidence of better mask alignment for these selected ions, **not**
proof of their molecular identities or that shuffling improves the trained
model. The cause of the ranking shift remains unresolved: the intervention
may be out of distribution, and the 16 sections represent one training seed
per section (with multiple GBM sections from the same patients). The
[local comparison figures](../../results/README.md) show the collection-level
pattern; they do not turn this post-hoc audit into a deployment comparison.

### Centre–context distribution screen for the frozen shuffle (6 October 2026)

The [CPU-only screen](../../code/msi/results/diagnostics/spatial_attention_context_shift/)
recreated the exact seed-1701 shuffle used above (saved source-slot hashes
matched). It sampled 512 measured centres in each of the two earlier
exploratory sections, with no zero-spectrum exclusions, masks, model, GMM,
IG or peak evaluation. The cosine compares the *spectral pattern* of each
centre with its mean context; half-L1 measures their absolute difference.

| Section | Median cosine, real → shuffled | Shuffled cosine below real 5th percentile | Median half-L1, real → shuffled | Shuffled half-L1 above real 95th percentile |
|---|---:|---:|---:|---:|
| `160TopL` | 0.984 → 0.811 | 81.1% | 0.164 → 0.420 | 92.0% |
| `GBM22_2` | 0.979 → 0.889 | 66.2% | 0.212 → 0.346 | 70.9% |

Both sampled sections show a substantial shift in the centre–context
relationship under this nonlocal shuffle. This strengthens the
**out-of-distribution warning** for feeding shuffled neighbours into a
real-neighbour-trained checkpoint: the frozen ranking-swap gains cannot be
interpreted as evidence that realistic shuffled deployment or real spatial
context is harmful. This screen measures only two simple input statistics,
on outcome-known sections with spatially dependent sampled pixels; it does
not prove the full model input is out of distribution or identify why IG
rankings changed. The separately trained real-versus-shuffled attention
comparison above is the relevant, though still single-seed, peak-quality
control.

### Matched learned-attention training-seed repeat (7 October 2026)

The [seed-2/3 result sets](../../code/msi/results/experiments/spatial_attention_context_seed_stability/)
are complete for both exploratory sections and both arms (8/8). They extend
the already completed seed-1 pilot. Each pair used the same initial VAE state
within its training seed, 100 epochs, corrected 3×3 attention, and the same
section-specific peak count. The shuffled-context source map remained fixed
at seed 1701 and its saved hash matched across training seeds; downstream
GMM/IG sampling seeds remained fixed. All twelve training, attribution and
peak-evaluation summaries report complete/valid/complete, and all twelve IG
completeness checks passed. The first seed-2 `160TopL` shuffled allocation
stopped at concurrent shared-folder creation; its single-index retry completed
without changing the scientific settings.

| Section | Training seed | Real mSCF1 | Separately trained shuffled mSCF1 | Real − shuffled |
|---|---:|---:|---:|---:|
| `160TopL` | 1 | 0.4662 | 0.4618 | +0.0044 |
| `160TopL` | 2 | 0.4843 | 0.4906 | −0.0063 |
| `160TopL` | 3 | 0.4834 | 0.4748 | +0.0086 |
| `GBM22_2` | 1 | 0.4364 | 0.4422 | −0.0058 |
| `GBM22_2` | 2 | 0.4176 | 0.4492 | −0.0316 |
| `GBM22_2` | 3 | 0.4617 | 0.4833 | −0.0217 |

The constituent mixed-class F1 scores make clear which PCC thresholds drove
the mean (real/shuffled shown in each cell):

| Section | Seed | PCC 0.3 | PCC 0.4 | PCC 0.5 | PCC 0.6 |
|---|---:|---:|---:|---:|---:|
| `160TopL` | 1 | .7166/.7112 | .6422/.6300 | .3893/.3893 | .1166/.1166 |
| `160TopL` | 2 | .7647/.7701 | .6667/.6789 | .3893/.3969 | .1166/.1166 |
| `160TopL` | 3 | .7594/.7326 | .6606/.6606 | .3969/.3893 | .1166/.1166 |
| `GBM22_2` | 1 | .3958/.4021 | .4290/.4303 | .4500/.4633 | .4711/.4731 |
| `GBM22_2` | 2 | .3851/.4011 | .4005/.4493 | .4300/.4733 | .4545/.4731 |
| `GBM22_2` | 3 | .4064/.4233 | .4520/.4817 | .4883/.5117 | .5000/.5165 |

Mean paired real-minus-shuffled change was +0.0022 mSCF1 on `160TopL`
(range −0.0063 to +0.0086) and −0.0197 on `GBM22_2` (range −0.0316 to
−0.0058). Thus real context did **not** meet the predeclared +0.02 practical
promotion signal on either section. CAC changes sign with the seed; on this
GBM section shuffled training won all three, but the two sections were
outcome-known exploratory choices, not independent validation. GBM within-arm
seed ranges were also material (real 0.4176–0.4617, shuffled 0.4422–0.4833).
Unrounded scores and the confusion counts remain in each linked
`peak_evaluation/summary.json`.

The reconstruction MSE did not track a consistent real-context benefit:
`160TopL` real/shuffled pairs were 9.589/9.675, 9.671/9.534 and 9.315/9.636
×10⁻⁷ for seeds 1–3; `GBM22_2` pairs were 1.864/2.005, 2.913/2.873 and
2.882/2.897 ×10⁻⁹. IG completeness is a numerical consistency check, not
proof that every peak ranking is faithful: at a 128-bin deletion budget, IG
exceeded the random posterior-drop control for only 2/3 CAC components in
each arm/seed; GBM was usually 1/2 components (shuffled seed 2 was 2/2).
The shuffled GBM attribution stage took about 32–33 minutes per seed versus
17–18 minutes for real context, despite similar ~42–44-minute training times.
GPU peak allocation was about 3.20 GiB for GBM and 0.07 GiB for CAC; these
are **not** peak host-RAM measurements and do not justify the 32-GB Slurm
request by themselves. Node hardware and queue wait differ, so this is not a
matched-hardware runtime benchmark.

The bounded repeat resolves the seed-1 ambiguity only for these two tested
configurations: no reproducible real-neighbour peak-quality advantage appears
here. It does not prove that spatial context is generally useless, explain
the CAC–GBM difference, or validate shuffled context as a deployment method.

### S3PL GBM initialization stability and repeated native runtime (8 October 2026)

The complete fixed-order S3PL screen now contains initialization seeds 1–3 for
all eight GBM sections under the released 10-epoch, patch-size-3 protocol.
Six of eight sections have an absolute mSCF1 seed range of at least 0.10:
`GBM108_positive` 0.418, `GBM108_negative` 0.302, `GBM12_2` 0.235,
`GBM22_1` 0.121, `GBM39_1` 0.140 and `GBM39_2` 0.131. `GBM12_1` and
`GBM22_2` have smaller ranges of 0.056 and 0.059. The collection means are
more stable at 0.300, 0.306 and 0.339 for seeds 1–3 because section-level
movements partly cancel. This does not make a single section seed reliable.

Combined with the earlier controlled order test and 25/50-epoch continuation,
the evidence identifies weight initialization and the short stopping point as
the source of the instability. Similar reconstruction losses can lead to
different selected peaks and mSCF1. Report all declared seeds, section mean and
sample SD, peak-set overlap and collection aggregation; never choose the best
seed per section.

Three complete native-workflow measurements on `160TopL` recorded S3PL totals
of 151.18, 173.90 and 173.87 seconds, and VAE training + attribution + scoring
totals of 135.30, 121.63 and 121.87 seconds. S3PL used approximately
1.31–1.32 GiB maximum RSS and 315 MiB sampled GPU memory; the maximum VAE stage
used approximately 1.15–1.18 GiB and 237 MiB. The VAE used less wall time and
sampled memory in these runs, but this is a native-workflow comparison rather
than an equal-work efficiency result because S3PL uses 10 epochs and the VAE
100, with different objectives and downstream stages.

The exact tables, figures, reporting rule and decision are in the
[stability/runtime synthesis](investigations/16%20S3PL%20GBM%20Stability%20and%20Runtime%20Synthesis.md).

## Fair-scoring gates (a)/(b) (9 October 2026)

**Protocol:** [protocol 18](18%20Fair%20Scoring%20and%20Simple%20Baselines%20Protocol.md) (v3.2), seed 1, all 16 sections in both arms. Two kinds of comparison:
- **Bin level at K_bin** (budget multiplier m = 1): array 66053, decision table 66097.
- **Approved peak partitions** (P1 on GBM; P1 and P3 on CAC, which are identical to bin level there): arrays 66114 and 66179, decision table 66238.

The question: does IG add value beyond its own segmentation target? The no-IG baseline answers it. It ranks bins by the absolute Pearson correlation of their TIC-normalised intensity with the soft GMM posterior maps, balanced across components. That is the same label-free segmentation IG explains, with no gradients at all ("posterior-|PCC|").

**Result (wording from protocol 18 Section 7.1):** neither predeclared verdict applies, because IG scored below posterior-|PCC| in every section (bin level: 0/8 sections positive in each of the four collection-arms). The summariser prints "mixed / not resolved by the predeclared rule". That label is a fall-through, not a mixed result: the rule has no "IG worse" category, and none is added after the fact. Under P1, one section-arm out of 32 goes the other way: CAC 280TopL, uniform_mean, +0.058 at K_peak 70.

**IG versus legacy msiPL** is positive in 8/8 sections in every collection-arm, both at bin level and in the K_bin collapse diagnostic. The rule's budget-stability clause cannot be assessed, because legacy is scored at m = 1 only. So this is reported as **two of three clauses met**, not as the rule being met. Legacy is not K_peak-matched, so the peak-level IG-versus-legacy comparison is a collapse diagnostic only.

Collection summary at bin level, K_bin (IG minus each baseline; "IG ahead" counts sections where IG is higher):

| Collection, arm | IG mean | Posterior mean | IG − posterior: mean / median / IG ahead | IG − legacy: mean / IG ahead | IG − mean intensity: mean / IG ahead | IG − Moran's I: mean / IG ahead |
|---|---:|---:|---|---|---|---|
| GBM central_only | 0.518 | 0.743 | −0.225 / −0.233 / 0/8 | +0.104 / 8/8 | +0.035 / 8/8 | −0.166 / 0/8 |
| GBM uniform_mean | 0.511 | 0.744 | −0.233 / −0.229 / 0/8 | +0.097 / 8/8 | +0.028 / 5/8 | −0.173 / 0/8 |
| CAC central_only | 0.528 | 0.606 | −0.078 / −0.073 / 0/8 | +0.126 / 8/8 | −0.084 / 0/8 | −0.077 / 0/8 |
| CAC uniform_mean | 0.560 | 0.607 | −0.047 / −0.042 / 0/8 | +0.157 / 8/8 | −0.053 / 0/8 | −0.046 / 1/8 |

**GBM patient grouping.** There are 8 sections from 4 patients, two sections each, so sections are not independent patients. Per-patient means of IG − posterior-|PCC| at bin level:
- central_only: patient 108 −0.174, 12 −0.185, 22 −0.248, 39 −0.293. All four are negative; the mean over patients is −0.225.
- uniform_mean: 108 −0.166, 12 −0.289, 22 −0.209, 39 −0.269. All four are negative; the mean over patients is −0.233.

Under P1 the GBM means are −0.201 (central_only) and −0.213 (uniform_mean), with 0/8 sections positive in each. CAC under P1/P3 gives −0.092 (central_only, 0/8) and −0.039 (uniform_mean, 1/8).

Per section (mSCF1 at K_bin, m = 1). The last column is IG − posterior-|PCC| at the matched P1 K_peak. Legacy, mean intensity, Moran's I and the oracle do not depend on the arm. The oracle is a supervised ceiling (maximum signed expert-class PCC) and cannot be deployed. "(dev)" marks development sections, which are not confirmation evidence.

| Section | Patient | Arm | K_bin | IG | Posterior-\|PCC\| | IG − posterior | Legacy | Mean intensity | Moran's I | Oracle | IG − posterior, P1 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GBM108_positive (dev) | 108 | central_only | 584 | 0.508 | 0.692 | −0.184 | 0.410 | 0.450 | 0.590 | 0.724 | −0.160 |
| GBM108_positive (dev) | 108 | uniform_mean | 584 | 0.533 | 0.705 | −0.172 | 0.410 | 0.450 | 0.590 | 0.724 | −0.153 |
| GBM108_negative | 108 | central_only | 940 | 0.654 | 0.818 | −0.164 | 0.548 | 0.603 | 0.672 | 0.821 | −0.131 |
| GBM108_negative | 108 | uniform_mean | 940 | 0.659 | 0.818 | −0.159 | 0.548 | 0.603 | 0.672 | 0.821 | −0.132 |
| GBM12_1 | 12 | central_only | 691 | 0.291 | 0.406 | −0.115 | 0.245 | 0.283 | 0.561 | 0.767 | −0.090 |
| GBM12_1 | 12 | uniform_mean | 691 | 0.279 | 0.629 | −0.350 | 0.245 | 0.283 | 0.561 | 0.767 | −0.308 |
| GBM12_2 | 12 | central_only | 986 | 0.569 | 0.824 | −0.255 | 0.478 | 0.539 | 0.741 | 0.830 | −0.231 |
| GBM12_2 | 12 | uniform_mean | 986 | 0.595 | 0.823 | −0.228 | 0.478 | 0.539 | 0.741 | 0.830 | −0.214 |
| GBM22_1 | 22 | central_only | 834 | 0.520 | 0.804 | −0.285 | 0.381 | 0.474 | 0.710 | 0.820 | −0.266 |
| GBM22_1 | 22 | uniform_mean | 834 | 0.538 | 0.807 | −0.270 | 0.381 | 0.474 | 0.710 | 0.820 | −0.252 |
| GBM22_2 (dev) | 22 | central_only | 1028 | 0.611 | 0.822 | −0.211 | 0.469 | 0.587 | 0.700 | 0.831 | −0.196 |
| GBM22_2 (dev) | 22 | uniform_mean | 1028 | 0.527 | 0.676 | −0.149 | 0.469 | 0.587 | 0.700 | 0.831 | −0.145 |
| GBM39_1 | 39 | central_only | 695 | 0.421 | 0.746 | −0.325 | 0.315 | 0.385 | 0.718 | 0.821 | −0.303 |
| GBM39_1 | 39 | uniform_mean | 695 | 0.429 | 0.737 | −0.308 | 0.315 | 0.385 | 0.718 | 0.821 | −0.283 |
| GBM39_2 | 39 | central_only | 911 | 0.568 | 0.830 | −0.262 | 0.469 | 0.545 | 0.781 | 0.854 | −0.232 |
| GBM39_2 | 39 | uniform_mean | 911 | 0.530 | 0.759 | −0.229 | 0.469 | 0.545 | 0.781 | 0.854 | −0.219 |
| 40TopL (dev) | – | central_only | 315 | 0.680 | 0.727 | −0.047 | 0.478 | 0.729 | 0.731 | 0.756 | −0.046 |
| 40TopL (dev) | – | uniform_mean | 315 | 0.683 | 0.745 | −0.062 | 0.478 | 0.729 | 0.731 | 0.756 | −0.041 |
| 160TopL (dev) | – | central_only | 210 | 0.480 | 0.525 | −0.045 | 0.358 | 0.523 | 0.512 | 0.527 | −0.064 |
| 160TopL (dev) | – | uniform_mean | 210 | 0.483 | 0.522 | −0.039 | 0.358 | 0.523 | 0.512 | 0.527 | −0.044 |
| 200TopL | – | central_only | 221 | 0.623 | 0.677 | −0.054 | 0.426 | 0.675 | 0.674 | 0.682 | −0.081 |
| 200TopL | – | uniform_mean | 221 | 0.633 | 0.677 | −0.044 | 0.426 | 0.675 | 0.674 | 0.682 | −0.085 |
| 240TopL | – | central_only | 255 | 0.566 | 0.694 | −0.127 | 0.398 | 0.678 | 0.677 | 0.715 | −0.141 |
| 240TopL | – | uniform_mean | 255 | 0.608 | 0.647 | −0.039 | 0.398 | 0.678 | 0.677 | 0.715 | −0.016 |
| 280TopL | – | central_only | 245 | 0.376 | 0.403 | −0.028 | 0.319 | 0.415 | 0.387 | 0.438 | −0.052 |
| 280TopL | – | uniform_mean | 245 | 0.387 | 0.398 | −0.011 | 0.319 | 0.415 | 0.387 | 0.438 | +0.058 |
| 360TopL | – | central_only | 247 | 0.495 | 0.601 | −0.106 | 0.401 | 0.634 | 0.585 | 0.678 | −0.112 |
| 360TopL | – | uniform_mean | 247 | 0.565 | 0.595 | −0.030 | 0.401 | 0.634 | 0.585 | 0.678 | −0.020 |
| 400TopL | – | central_only | 133 | 0.362 | 0.487 | −0.125 | 0.326 | 0.491 | 0.524 | 0.608 | −0.161 |
| 400TopL | – | uniform_mean | 133 | 0.398 | 0.478 | −0.080 | 0.326 | 0.491 | 0.524 | 0.608 | −0.078 |
| 520TopL | – | central_only | 232 | 0.645 | 0.736 | −0.091 | 0.512 | 0.755 | 0.750 | 0.827 | −0.079 |
| 520TopL | – | uniform_mean | 232 | 0.719 | 0.790 | −0.072 | 0.512 | 0.755 | 0.750 | 0.827 | −0.088 |

**Provisional reading (the framing waits for the 19 October meeting).** On GBM, the label-free GMM segmentation plus a correlation ranking comes close to the supervised oracle (0.743 versus 0.809 mean). On CAC, the same baseline is only comparable to mean intensity and Moran's I (0.606 versus 0.612 and 0.605). IG trails the correlation ranking in both collections. Spatial context was not tested by this gate. **Qualification (supervisor, 15 October):** The production K equals the number of annotated classes, so the segmentation is label-free in training and ranking but class-informed in its component count. See [the BIC result](#gate-d-bic-selected-k-15-october-2026).

Artifacts: `code/msi/results/diagnostics/fair_scoring_baselines/bin_level_only/` (per-section `summary.json`, `summary_66097/decisions.json`) and `.../with_approved_partitions/` (`summary_66238/decisions.json`). Curated tables: `code/msi/results/publication/current_evidence/fair_scoring_bin_level_sections.csv`, `fair_scoring_collection_summary.csv` and `fair_scoring_partition_sections.csv`, all built by `code/msi/scripts/build_current_evidence_tables.py` and cross-checked against both decision tables.

## Gate (d) attribution-pixel count (9–10 October 2026)

**Question:** is IG's deficit an artifact of sampling only 12 attribution pixels per GMM component? The test reruns IG with 48 and 192 nested pixels (12 ⊂ 48 ⊂ 192), on the two development sections GBM108_positive and 40TopL, in both arms. The decision rule was fixed beforehand (protocol 18 Section 6): a 16-section rerun is triggered only if the change in mSCF1 at K_bin is ≥ +0.02 on **both** sections for an arm.

**Run validity:**
- Every n = 12 rerun reproduced the saved production bin set, with mSCF1 difference 0.0.
- GMM labels were aligned to production: the identity everywhere except the 40TopL central_only permutation {0→0, 1→2, 2→1}, adopted before any central_only score existed.
- IG status was `valid`, and every count was distinct from the next smaller one.
- Jobs: 40TopL 66324–66332; GBM108_positive 66390–66393, then 66399–66406.

**Result:** "Gate (d) attribution-pixel count: production n = 12 stands in both arms (no setting reached +0.02 on both development sections); no 16-section rerun; reported descriptively."

| Section | Arm | n | IG mSCF1 at K_bin | Change vs saved n = 12 | Jaccard vs n = 12 | IG − posterior-\|PCC\| | Verdict |
|---|---|---:|---:|---:|---:|---:|---|
| GBM108_positive | central_only | 12 | 0.508 | +0.000 | 1.000 | −0.184 | reference (saved production n = 12) |
| GBM108_positive | central_only | 48 | 0.520 | +0.011 | 0.881 | −0.172 | production n=12 stands |
| GBM108_positive | central_only | 192 | 0.525 | +0.017 | 0.872 | −0.166 | production n=12 stands |
| GBM108_positive | uniform_mean | 12 | 0.533 | +0.000 | 1.000 | −0.172 | reference (saved production n = 12) |
| GBM108_positive | uniform_mean | 48 | 0.537 | +0.005 | 0.878 | −0.168 | production n=12 stands |
| GBM108_positive | uniform_mean | 192 | 0.547 | +0.015 | 0.863 | −0.158 | production n=12 stands |
| 40TopL | central_only | 12 | 0.680 | +0.000 | 1.000 | −0.047 | reference (saved production n = 12) |
| 40TopL | central_only | 48 | 0.679 | −0.001 | 0.795 | −0.048 | production n=12 stands |
| 40TopL | central_only | 192 | 0.705 | +0.024 | 0.805 | −0.023 | production n=12 stands |
| 40TopL | uniform_mean | 12 | 0.683 | +0.000 | 1.000 | −0.062 | reference (saved production n = 12) |
| 40TopL | uniform_mean | 48 | 0.674 | −0.008 | 0.853 | −0.071 | production n=12 stands |
| 40TopL | uniform_mean | 192 | 0.686 | +0.003 | 0.848 | −0.059 | production n=12 stands |

Descriptive, no verdict (supervisor, 10 October):
- On GBM108_positive, every larger count improved slightly, by +0.005 to +0.017, and more at n = 192 than at n = 48 in both arms. More attribution pixels give a small, consistent gain that stays below the practical threshold.
- **That gain is about ten times smaller than the IG − posterior-|PCC| gap on the same section (−0.16 to −0.18 at K_bin). So undersampled attribution pixels do not explain why IG trails the correlation ranking.**
- IG − posterior-|PCC| stays negative at every n and every budget multiplier on both sections. The 40TopL central_only n = 192 change (+0.024) is from one section and one seed, with bin-set Jaccard of about 0.8 between counts.

Artifacts: `code/msi/results/diagnostics/gate_d_pixel_counts/<section>_seed1/<arm>/evaluation/summary.json` and `summary_66406/decisions.json`. Curated table: `code/msi/results/publication/current_evidence/gate_d_pixel_counts.csv`.

### Gate (d) BIC-selected K (15 October 2026)

**Question (protocol 18 Section 6, "BIC run specification"):** is the production K supported by BIC, or arbitrary? This is descriptive per section-arm: there is no verdict, and production K stays the reported setting whatever BIC shows.

**Run:**
- CPU array 68496 on `bigbatch` (`batch` was down), run on the saved production latents, with no labels read.
- Settings: K ∈ {1, …, 6}, StandardScaler, full covariance, `n_init` 20, seed 1. The rule is the smallest K within ΔBIC < 10 of the minimum.
- Refitting production K reproduced the saved assignment (ARI 1.0) in all four section-arms.
- Test job 68489 passed 92/92.

**Primary result (wording confirmed by the supervisor, 15 October):** "BIC does not support the production K; it selects the largest candidate (K = 6), with no minimum within the predeclared range; descriptive only. The production K equals the number of annotated classes, so the segmentation is label-free in training and ranking but class-informed in its component count." Production K is 2 for GBM108_positive and 3 for 40TopL. Every candidate converged.

**Read this with care:** K = 6 is the *largest candidate*. BIC drops by at least 314 at every added component, far beyond the 10-point tie margin, and is still falling at K = 6. So the BIC minimum is not reached within the predeclared range: BIC favours "more components than 6" rather than identifying a particular K. With thousands of pixels and a full-covariance model, that is common for BIC. It says the latent distribution is not well described by a few Gaussian clusters; it does not say six tissue classes exist. Candidates above 6 were not predeclared and were not run.

"BIC-K segmentation sensitivity, descriptive" (no trigger, no verdict): the GMM was refitted at K = 6 with the production settings, and posterior-|PCC| was rescored at K_bin. Before that, each run reproduced the saved production-K score exactly.

| Section | Arm | Production K | BIC-selected K | BIC decrease per added component (1→2 … 5→6) | Refit ARI vs saved | Posterior-\|PCC\|, production K | at K = 6 | Change | ARI / NMI vs labels, production K | at K = 6 |
|---|---|---:|---:|---|---:|---:|---:|---:|---|---|
| GBM108_positive | central_only | 2 | 6 | 2680, 1181, 666, 314, 476 | 1.0 | 0.692 | 0.391 | −0.300 | 0.559 / 0.448 | 0.249 / 0.297 |
| GBM108_positive | uniform_mean | 2 | 6 | 2254, 1094, 911, 582, 472 | 1.0 | 0.705 | 0.406 | −0.299 | 0.644 / 0.545 | 0.219 / 0.314 |
| 40TopL | central_only | 3 | 6 | 10900, 3608, 2325, 2486, 1601 | 1.0 | 0.727 | 0.729 | +0.001 | 0.435 / 0.465 | 0.340 / 0.461 |
| 40TopL | uniform_mean | 3 | 6 | 11392, 3535, 1964, 2677, 1550 | 1.0 | 0.745 | 0.724 | −0.021 | 0.624 / 0.525 | 0.352 / 0.469 |

- **GBM108_positive:** the six-component segmentation makes the correlation ranking much worse (−0.30 in both arms), and it agrees less with the expert labels (ARI 0.56–0.64 at production K, 0.22–0.25 at K = 6).
- **40TopL:** the ranking barely changes (+0.001 and −0.021); label agreement also falls (ARI 0.43–0.62 at production K, 0.34–0.35 at K = 6).
- So the posterior-|PCC| baseline's strength at production K does not come from a BIC-supported cluster count. On GBM it depends on using a coarse two-component segmentation. These are development sections, one seed, and descriptive only.
- No IG was run at any BIC or forced K (specification item a).

Artifacts: `code/msi/results/diagnostics/gate_d_bic/<section>_seed1/<arm>/bic_selection.json` and `.../bic_k_sensitivity/summary.json`. Curated table: `code/msi/results/publication/current_evidence/gate_d_bic.csv`.

## S3PL CAC spatial-input controls (7–15 October 2026)

All eight CAC sections. Original S3PL architecture: 10 epochs, patch size 9, `reference_spatial_max`, matched peak counts (40TopL 315, 160TopL 210, 200TopL 221, 240TopL 255, 280TopL 245, 360TopL 247, 400TopL 133, 520TopL 232). Details are in [investigation 15](investigations/15%20Overnight%20S3PL%20CAC%20Controls%20-%207%20October%202026.md). There are two kinds of control:

- **Retrained tile-centre (seed 1):** a separate model is trained with every patch position replaced by the normalised centre spectrum, while still reconstructing the real patch. It is evaluated the same way.
- **Frozen interventions on the original real-input checkpoint** (out-of-distribution sensitivity tests, not spatial-benefit ablations):
  - `s3pl_cac_frozen_context`: zero the neighbours, or tile the centre;
  - `s3pl_cac_frozen_topology`: rotate the patch 90°, or cyclically shift positions within each Chebyshev ring.
  - Each frozen campaign re-evaluated the real input on the same node ("fresh real"). Each intervention is compared against its own campaign's fresh real. Status `valid_pair_with_prior_drift` means the fresh real selected set differs slightly from the historical matched-count set. On 240TopL, the two campaigns' fresh real values themselves differ (0.672 versus 0.670), so both are shown.

| Section | Peaks | Real input | Retrained tile-centre | Real − retrained | Frozen: fresh real | Frozen: tile centre | Frozen: zero neighbours | Topology: fresh real | Rotate 90° | Ring shift | Status (context / topology) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 40TopL | 315 | 0.715 | 0.177 | +0.538 | 0.715 | 0.626 | 0.048 | 0.715 | 0.715 | 0.714 | valid_pair_with_prior_drift / valid_pair_with_prior_drift |
| 160TopL | 210 | 0.495 | 0.130 | +0.365 | 0.495 | 0.456 | 0.015 | 0.495 | 0.494 | 0.495 | valid / valid |
| 200TopL | 221 | 0.665 | 0.356 | +0.309 | 0.665 | 0.605 | 0.008 | 0.665 | 0.662 | 0.665 | valid / valid |
| 240TopL | 255 | 0.670 | 0.144 | +0.526 | 0.672 | 0.642 | 0.015 | 0.670 | 0.665 | 0.672 | valid_pair_with_prior_drift / valid_pair_with_prior_drift |
| 280TopL | 245 | 0.378 | 0.168 | +0.210 | 0.378 | 0.377 | 0.007 | 0.378 | 0.378 | 0.378 | valid / valid |
| 360TopL | 247 | 0.643 | 0.149 | +0.494 | 0.643 | 0.601 | 0.009 | 0.643 | 0.643 | 0.643 | valid / valid |
| 400TopL | 133 | 0.459 | 0.143 | +0.315 | 0.459 | 0.436 | 0.002 | 0.461 | 0.460 | 0.452 | valid / valid_pair_with_prior_drift |
| 520TopL | 232 | 0.707 | 0.163 | +0.544 | 0.707 | 0.668 | 0.005 | 0.708 | 0.716 | 0.711 | valid / valid_pair_with_prior_drift |

**Summary (seed 1):**
- **Retrained tile-centre:** the real-input model beats it in 8/8 sections, by +0.210 to +0.544 (mean 0.592 versus 0.179).
- **Frozen tile-centre:** it costs the frozen checkpoint +0.001 to +0.089, mean 0.040.
- **Frozen zero neighbours:** this collapses the frozen model (mean 0.014), which shows it relies on non-zero neighbour input.
- **Rotation and ring shift:** these change mSCF1 by at most 0.009 in either direction. The frozen ranking is largely insensitive to these particular rearrangements. That is not evidence of general position invariance.

**Caveat to carry everywhere:** the tile-centre model still reconstructs the real patch, so its training target is harder. This is not a pure information ablation. Also, normalisation happens before tiling, so the centre value can still reflect neighbouring intensities through its scale.

**Two-seed rule (predeclared on 15 October, before any seed-2 output):** "S3PL benefits from real neighbourhood input during training" is reported as **supported** only if real beats tile-centre by ≥ 0.02 mSCF1 on ≥ 7/8 sections **in both seeds**, and the mean paired difference is ≥ 0.02 in both seeds. Otherwise it is reported as mixed, with per-section values. Seed 1 meets its half (8/8, mean +0.413). Seed 1 used the released code path, so the two seeds also differ in sample order. Both arms within a seed share the same handling.

**Seed 2 (15 October; initialization seed 2, sample-order seed 1):**
- Jobs: pilot 68500 (160TopL), then 68501. All 16 runs exited 0 on RTX 3090 nodes after the CUDA warm-up, and none had to be retried.
- The status-only checker verified 16/16: checkpoint, configuration (seeds, epochs, patch size, matched count) and input-mode labels.

| Section | Peaks | Seed 1 real | Seed 1 retrained tile | Seed 1 difference | Seed 2 real | Seed 2 retrained tile | Seed 2 difference |
|---|---:|---:|---:|---:|---:|---:|---:|
| 40TopL | 315 | 0.715 | 0.177 | +0.538 | 0.700 | 0.188 | +0.511 |
| 160TopL | 210 | 0.495 | 0.130 | +0.365 | 0.493 | 0.130 | +0.363 |
| 200TopL | 221 | 0.665 | 0.356 | +0.309 | 0.657 | 0.149 | +0.508 |
| 240TopL | 255 | 0.670 | 0.144 | +0.526 | 0.673 | 0.144 | +0.529 |
| 280TopL | 245 | 0.378 | 0.168 | +0.210 | 0.381 | 0.159 | +0.222 |
| 360TopL | 247 | 0.643 | 0.149 | +0.494 | 0.632 | 0.150 | +0.482 |
| 400TopL | 133 | 0.459 | 0.143 | +0.315 | 0.478 | 0.139 | +0.339 |
| 520TopL | 232 | 0.707 | 0.163 | +0.544 | 0.712 | 0.165 | +0.547 |

**Two-seed rule outcome: supported.** Real input beats the retrained tile-centre model by ≥ 0.02 in **8/8 sections in both seeds**:
- seed 1: mean 0.591 versus 0.179, paired difference +0.413;
- seed 2: mean 0.591 versus 0.153, paired difference +0.438.

The real-input scores are stable across seeds (per-section change at most 0.019). The tile-centre scores are also stable, except 200TopL (0.356 in seed 1, 0.149 in seed 2). Reported wording: "S3PL benefits from real neighbourhood input during training (supported under the predeclared two-seed rule)". It always carries the caveat below. It concerns S3PL's own training, not the VAE, and does not explain the S3PL–VAE gap.

Artifacts: `code/msi/results/baselines/s3pl/<section>_..._matched_<count>peaks/metrics.json` (real), `.../<section>_..._train_tile_centre/metrics.json` (retrained), `code/msi/results/diagnostics/s3pl_cac_frozen_context/<section>.json` and `.../s3pl_cac_frozen_topology/<section>.json`. Seed 2: `code/msi/reproducibility/s3pl_cac_centre_control/seed2_init2_order1/results/baselines/s3pl/*/metrics.json`. Curated: `code/msi/results/publication/current_evidence/s3pl_cac_controls.csv` and `s3pl_cac_seed_rule.json`. The table uses unrounded mSCF1 (the mean of the four mixed-F1 values, which is checked to round to the stored 3-decimal value).

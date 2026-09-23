# Concepts, mathematics, and implementation guide

This is the study companion to the supervisor-facing [weekly progress document](../meetings/progress.md). It answers four questions for every important term:

1. What does it mean in plain language?
2. What is the relevant mathematics?
3. Why did we use it?
4. Where is it implemented and where can I see its results?

The links are ordinary relative Markdown links. They work on GitHub, in VS Code, and in Obsidian. Obsidian is optional: it can display backlinks and a graph, but the repository already provides the useful part—a connected set of version-controlled notes beside the code and results.

## Navigation

- [Results record](01%20Results%20Record.md): numerical findings and evidence locations.
- [Methodology and rationale](02%20Methodology%20and%20Rationale.md): fuller method narrative and experimental decisions.
- [Datasets and preprocessing](03%20Datasets%20and%20Preprocessing.md): section dimensions, masks, coverage, HDF5 layout, and normalisation.
- [Metrics and statistics](04%20Metrics%20and%20Statistics.md): fuller metric definitions and interpretation.
- [Experiment history](05%20Experiment%20History.md): chronological record of what was tried.
- [Cluster and reproducibility](06%20Cluster%20and%20Reproducibility.md): environments, Slurm, provenance, and known node failures.
- [Current status and next steps](07%20Current%20Status%20and%20Next%20Steps.md): project-level status.
- [Proposal source](../../RP/proposal.tex): original research questions and proposed methodology.
- [Current publication evidence](../../code/msi/results/publication/current_evidence/README.md): concise frozen evidence package.

## End-to-end map

```text
MSI section (one spectrum at each measured x,y coordinate)
        |
        v
TIC normalisation + mask/coordinate validation
        |
        +------------------------------+
        |                              |
        v                              v
centre-only spectrum          centre + eight-neighbour context
        |                              |
        +---------------+--------------+
                        v
                 VAE encoder and decoder
                        |
                        v
              deterministic latent means
                        |
                        v
                  two-component GMM
                        |
                        v
        posterior-targeted Integrated Gradients
                        |
                        v
          matched-count ranked m/z peak bins
                        |
                        v
 ion images -> PCC with expert masks -> F1 at four thresholds -> mSCF1
```

The central scientific separation is:

- **Architecture question:** Does neighbourhood context change what the VAE learns?
- **Explanation question:** Given a trained model, which input m/z bins contribute to a spatially meaningful latent cluster?

Those questions must not be collapsed into one. Centre-only IG can improve peak selection without any neighbourhood input, while context can affect peak rankings without improving reconstruction.

## Quick terminology index

| Term | Short meaning | Detailed section |
|---|---|---|
| MSI | A spectrum measured at each tissue coordinate | [MSI data representation](#msi-data-representation) |
| m/z bin | One mass-to-charge feature/column of the spectrum | [MSI data representation](#msi-data-representation) |
| Ion image | Intensity of one m/z bin placed back on the 2D grid | [Ion images and masks](#ion-images-and-masks) |
| TIC normalisation | Divide each spectrum by its total intensity | [TIC normalisation](#tic-normalisation) |
| Moore neighbourhood | Up to eight immediately adjacent grid positions | [Neighbourhood construction](#neighbourhood-construction) |
| VAE | Probabilistic encoder-decoder with a regularised latent space | [VAE model and loss](#vae-model-and-loss) |
| Beta | Weight on the VAE KL term | [VAE model and loss](#vae-model-and-loss) |
| GMM | Probabilistic clusters fitted to latent vectors | [Latent GMM](#latent-gmm) |
| Integrated Gradients | Path-integrated input attribution for a chosen output | [Integrated Gradients](#integrated-gradients) |
| First-layer L2 | Norm of each input bin’s first-layer weights | [First-layer L2](#first-layer-l2) |
| PCC | Linear spatial similarity between ion image and mask | [Pearson correlation](#pearson-correlation-pcc) |
| mSCF1 | Mean peak-selection F1 over four PCC thresholds | [F1 and mSCF1](#f1-and-mscf1) |
| Balanced accuracy | Mean recall over expert classes | [Latent-space evaluation](#latent-space-evaluation) |
| Deletion faithfulness | Drop in target posterior after removing top-ranked bins | [Deletion faithfulness](#deletion-faithfulness) |
| Wilcoxon signed-rank | Paired non-parametric test across sections | [Statistics and experimental units](#statistics-and-experimental-units) |

## MSI data representation

An MSI section can be written as a matrix

\[
X \in \mathbb{R}_{\ge 0}^{N \times D},
\]

where \(N\) is the number of measured tissue pixels and \(D\) is the number of aligned m/z bins. Row \(x_i\) is the spectrum at spatial coordinate \((u_i,v_i)\). Column \(X_{:k}\) contains the intensities of m/z bin \(k\) over the tissue.

The GBM HDF5 files have 85,062 m/z bins. The CAC continuous-imzML sections have 1,481 aligned bins. The large difference in dimensionality is one reason the dense GBM models are expensive.

**Why it matters:** ordinary tabular methods see \(X\), but MSI also has a coordinate map. The research asks whether that spatial information improves feature/peak selection.

**Read more:** [Datasets and preprocessing](03%20Datasets%20and%20Preprocessing.md).  
**Code:** [HDF5 spatial dataset](../../code/msi/src/spatial_msipl/preprocessing.py), class `H5SpatialContextDataset` beginning at line 67.  
**Evidence:** [dataset audit results](../../code/msi/results/validation).

## Ion images and masks

For m/z bin \(k\), its ion image is formed by placing \(X_{ik}\) at each measured coordinate \((u_i,v_i)\). An expert mask assigns a tissue class to the same coordinates. The ion image is continuous; a class mask is binary when evaluating one class against the rest.

The masks are **evaluation data**, not VAE training targets. Training remains label-free. This distinction is essential to the self-supervised/unsupervised claim.

**Code:** spatial image construction in [peak evaluation](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), function `spatial_image` at line 174; Pearson labels in [create_pearson_labels.py](../../code/msi/baselines/s3pl/utils/create_pearson_labels.py), lines 8–71.  
**Visual examples:** [GBM/CAC visualisation results](../../code/msi/results/visualisations).

## TIC normalisation

Total ion current (TIC) normalisation removes overall intensity scale from each spectrum:

\[
\operatorname{TIC}(x_i)=\sum_{k=1}^{D}x_{ik}, \qquad
\tilde{x}_{ik}=\frac{x_{ik}}{\operatorname{TIC}(x_i)}.
\]

Each valid normalised spectrum sums approximately to one. The model therefore focuses more on the relative spectral distribution than on total signal magnitude.

**Why we used it:** spectra can differ greatly in total intensity for technical as well as biological reasons. TIC gives the VAE a consistent probability-like target and matches the reconstruction formulation.

**Caution:** TIC can also alter the meaning of absolute intensity. It is a preprocessing choice, not a harmless mathematical identity.

**Code:** [tic_normalize](../../code/msi/src/spatial_msipl/preprocessing.py), lines 17–34.  
**Validation:** [validate_spatial_msipl_preprocessing.py](../../code/msi/scripts/validate_spatial_msipl_preprocessing.py).  
**Read more:** [preprocessing note](03%20Datasets%20and%20Preprocessing.md#tic-normalisation).

## Neighbourhood construction

For a centre coordinate \((u,v)\), the Moore neighbourhood is

\[
\mathcal{N}(u,v)=\{(u+a,v+b):a,b\in\{-1,0,1\},\;(a,b)\ne(0,0)\}.
\]

There are at most eight neighbours. Missing grid positions and unmeasured pixels are masked rather than treated as real zero-intensity tissue.

We evaluated three aggregators:

### Uniform mean

\[
c_i=\frac{1}{|\mathcal{N}(i)|}\sum_{j\in\mathcal{N}(i)}\tilde{x}_j.
\]

Every available neighbour receives equal weight. This is the simplest and most interpretable spatial input.

### Depthwise weighting

For each spectral bin \(k\), the model learns a separate distribution over the eight relative neighbour positions:

\[
c_{ik}=\sum_{s=1}^{8}a_{sk}\tilde{x}_{isk},
\qquad \sum_s a_{sk}=1.
\]

This can learn, for example, that an upper-left neighbour matters differently from a lower-right neighbour for a particular bin, but it does not make weights depend on the current spectrum.

### Attention

The centre and neighbour spectra are projected into smaller embeddings. Similarity scores are scaled and normalised over valid neighbours:

\[
e_{ij}=\frac{q_i^T k_{ij}}{\sqrt{d_a}}, \qquad
\alpha_{ij}=\frac{\exp(e_{ij})}{\sum_{r\in\mathcal{N}(i)}\exp(e_{ir})},
\qquad
c_i=\sum_j\alpha_{ij}\tilde{x}_j.
\]

The corrected development variant multiplies the tiny TIC-normalised inputs by \(\sqrt{D}\) before projection. This gives the projection a usable numerical scale without applying the stronger \(D\)-fold scaling that was also tested.

**Code:** [neighbourhood.py](../../code/msi/src/spatial_msipl/neighbourhood.py): validation line 9, uniform mean line 38, depthwise line 54, attention line 86.  
**Tests:** [test_neighbourhood.py](../../code/msi/src/spatial_msipl/tests/test_neighbourhood.py) and [test_attention_scaling.py](../../code/msi/src/spatial_msipl/tests/test_attention_scaling.py).  
**Results:** [seed-stability figure](../../code/msi/results/experiments/spatial_msipl_training_seed_stability_summary/gbm108_positive_seed_stability.png).

## Centre-only control

The centre-only VAE receives only \(\tilde{x}_i\). The contextual model receives the centre plus an aggregated neighbourhood representation. Both reconstruct the same centre spectrum.

This is the causal logic of the architectural ablation: if the matched models differ, the intended changed factor is access to context. Without this control, a strong spatial model result would not tell us whether context helped or whether the underlying VAE/explanation method was already sufficient.

**Code:** [model.py](../../code/msi/src/spatial_msipl/model.py), `CentralOnlyVAE` line 89 and `NeighbourhoodSpatialVAE` line 117.  
**Results:** [GBM context control](../../code/msi/results/experiments/spatial_msipl_gbm_validation/context_attribution_control/context_attribution_control.png) and [CAC context effects](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_context_effects.png).

## VAE model and loss

### Encoder and reparameterisation

The encoder maps an input \(z_i^{\text{in}}\) to a Gaussian latent distribution:

\[
q_\phi(h_i\mid z_i^{\text{in}})
=\mathcal{N}\!\left(\mu_i,\operatorname{diag}(\sigma_i^2)\right).
\]

During training, a latent sample is produced with the reparameterisation trick:

\[
h_i=\mu_i+\sigma_i\odot\epsilon,
\qquad \epsilon\sim\mathcal{N}(0,I).
\]

The decoder maps \(h_i\) back to a reconstruction of the **central** TIC-normalised spectrum.

### Reconstruction term

The code uses a scaled categorical cross-entropy for non-negative, TIC-normalised spectra:

\[
\mathcal{L}_{\text{recon}}
=-D\sum_{k=1}^{D}\tilde{x}_{ik}\log(\hat{x}_{ik}+\varepsilon).
\]

The factor \(D\) keeps the magnitude useful as spectral dimensionality changes.

### KL term

The Gaussian KL divergence to a unit-normal prior is

\[
\mathcal{L}_{\text{KL}}
=-\frac{1}{2}\sum_{r}
\left(1+\log\sigma_{ir}^{2}-\mu_{ir}^{2}-\sigma_{ir}^{2}\right).
\]

The total loss is

\[
\mathcal{L}_{\text{VAE}}
=\mathcal{L}_{\text{recon}}+\beta\mathcal{L}_{\text{KL}}.
\]

Beta controls the reconstruction–regularisation trade-off. It is a training hyperparameter: changing it after training cannot retroactively change the representation.

**Code:** [Spatial VAE definitions](../../code/msi/src/spatial_msipl/model.py); [msipl_vae_loss](../../code/msi/src/spatial_msipl/training.py), lines 27–53; training loop begins at line 172.  
**Tests:** [test_model.py](../../code/msi/src/spatial_msipl/tests/test_model.py).  
**Read more:** [methodology note](02%20Methodology%20and%20Rationale.md#vae-objective).

## Explicit spatial loss

The proposed extra penalty encourages adjacent pixels to have similar latent means:

\[
\mathcal{L}_{\text{spatial}}
=\frac{1}{|E|L}\sum_{(i,j)\in E}\sum_{r=1}^{L}
(\mu_{ir}-\mu_{jr})^2,
\]

with total objective

\[
\mathcal{L}=\mathcal{L}_{\text{VAE}}+\lambda\mathcal{L}_{\text{spatial}}.
\]

where \(L\) is the number of latent dimensions and \(E\) contains unique adjacent pairs in the training batch. This encodes the prior belief that nearby tissue tends to be molecularly similar. The risk is oversmoothing real boundaries, so a lower spatial loss is not automatically a better scientific model.

Our pilots showed that the penalty could force smoothness, but worsened reconstruction and did not consistently improve the held-out spatial probe. It was therefore retained as an informative negative ablation rather than promoted.

**Code:** [latent_spatial_coherence_loss](../../code/msi/src/spatial_msipl/training.py), line 56; [spatial-loss evaluation](../../code/msi/scripts/evaluate_spatial_loss_pilots.py).  
**Rationale/results:** [methodology note](02%20Methodology%20and%20Rationale.md#explicit-spatial-loss).

## Poisson augmentation

For a TIC-normalised spectrum \(x\) and effective count \(C\), the augmentation approximates ion-counting noise by

\[
n_k\sim\operatorname{Poisson}(Cx_k), \qquad
x_k'=\frac{n_k}{\sum_r n_r}.
\]

The central and measured-neighbour spectra are perturbed independently during training. The target remains clean.

The implementation worked, but the noisy-input MSE improvement was only about 0.022%, below the predeclared 1% gate. It was not promoted.

**Code:** [poisson_augment_tic_normalized](../../code/msi/src/spatial_msipl/training.py), line 83; [calibration](../../code/msi/scripts/calibrate_poisson_augmentation.py); [pilot evaluation](../../code/msi/scripts/evaluate_poisson_augmentation_pilot.py).  
**Read more:** [methodology note](02%20Methodology%20and%20Rationale.md#poisson-augmentation).

## Deterministic evaluation

Training samples \(h\) from the latent distribution. Evaluation instead uses \(\mu\), the latent mean, so repeated evaluation of the same model and pixel does not change because of latent sampling.

For reconstruction, the code computes

\[
\hat{x}_i=\operatorname{decoder}(\mu_i)
\]

and then TIC-normalises the decoder output before comparing it with the target.

**Code:** [evaluate_spatial_reconstruction.py](../../code/msi/scripts/evaluate_spatial_reconstruction.py), function `deterministic_reconstruction_metrics` at lines 109–153, with decoding from the mean at lines 130–132.  
**Result:** [GBM reconstruction comparison](../../code/msi/results/experiments/spatial_msipl_gbm_validation/reconstruction/reconstruction_validation.png).

## Latent GMM

A two-component full-covariance Gaussian mixture is fitted to the deterministic latent means. For component \(c\),

\[
p(c\mid h)=
\frac{\pi_c\,\mathcal{N}(h\mid\mu_c,\Sigma_c)}
{\sum_j \pi_j\,\mathcal{N}(h\mid\mu_j,\Sigma_j)}.
\]

The GMM is useful for two reasons:

1. it gives a nonlinear, continuous component-posterior target for IG; and
2. it gives an unsupervised latent partition that can be compared with expert classes after training.

The GMM components are arbitrary labels such as 0 and 1. For evaluation, the code tries the possible component-to-class mappings and selects the mapping with the highest balanced accuracy. This evaluation mapping does not train the VAE or GMM.

**Code:** GMM fitting in [run_spatial_msipl_gmm_integrated_gradients.py](../../code/msi/scripts/run_spatial_msipl_gmm_integrated_gradients.py), around lines 400–430; differentiable posterior in [attribution.py](../../code/msi/src/spatial_msipl/attribution.py), lines 8–39; mapping in [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), lines 143–171.

## Integrated Gradients

For model output \(F_c(x)\), input \(x\), and baseline \(x'\), Integrated Gradients for feature \(k\) is

\[
\operatorname{IG}_k(x)=
(x_k-x_k')
\int_0^1
\frac{\partial F_c\left(x'+\alpha(x-x')\right)}{\partial x_k}
\,d\alpha.
\]

Our \(F_c\) is the posterior probability of the spectrum’s selected GMM component. The baseline is the section-wide mean TIC-normalised spectrum for the centre and each valid neighbour; missing neighbour positions stay zero and masked. Numerically, the integral is approximated over interpolation steps.

For contextual models, the per-bin combined score is

\[
s_k=|\operatorname{IG}^{\text{centre}}_k|
+\sum_{j\in\mathcal{N}(i)}
|\operatorname{IG}^{\text{neighbour }j}_k|,
\]

aggregated over sampled spectra and GMM components. Component-balanced round-robin selection stops a larger/easier component from taking the complete peak budget.

### What IG does and does not mean

IG answers: “Along the path from the reference spectrum to this input, which bins changed the selected model posterior?” It does not establish that a bin is a causal biomarker, identify its molecule, or guarantee that the model’s reasoning is biologically correct.

**Code:** [integrated_gradients_cluster_posterior](../../code/msi/src/spatial_msipl/attribution.py), lines 42–141; orchestration and aggregation in [run_spatial_msipl_gmm_integrated_gradients.py](../../code/msi/scripts/run_spatial_msipl_gmm_integrated_gradients.py), especially lines 440–506; matched evaluation in [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), lines 333 onward.  
**Tests:** [test_attribution.py](../../code/msi/src/spatial_msipl/tests/test_attribution.py).  
**Results:** [primary figure](../../code/msi/results/publication/current_evidence/figure_1_primary_peak_quality.png).

## First-layer L2

For input bin \(k\) and first-layer weight matrix \(W\), the simple importance score is

\[
s_k^{L2}=\sqrt{\sum_h W_{hk}^2}.
\]

For a contextual model, centre and context pathway norms are combined. This measures the magnitude of the direct first-layer connections, not the feature’s effect after nonlinear layers, and not its contribution to a particular output or cluster.

It was included because it closely reflects the original proposal and provides a cheap linear comparator. It performed poorly and is now an ablation. It must not be called an exact implementation of legacy msiPL LearnPeaks, which uses a different procedure.

**Code:** [first_layer_l2_importance](../../code/msi/src/spatial_msipl/attribution.py), line 144; ranking at lines 375–376 of [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py).  
**Result:** [explanation ablation](../../code/msi/results/publication/current_evidence/figure_3_explanation_ablation.png).

## Matched peak budgets

If method A selects 100 peaks and method B selects 500, their precision and recall are affected by selection count even if the rankings have similar quality. The strict comparison therefore selects exactly \(K_s\) peaks from each method for section \(s\).

In CAC, \(K_s\) is set by the tuned legacy msiPL result. In the current frozen GBM comparison, \(K_s\) came from the original legacy run. The later paper-aligned beta-tuned GBM run has different counts and a higher mean mSCF1 (0.4142 rather than 0.3643), so the saved GBM IG rankings should be re-evaluated at those tuned counts before the final cross-collection figure is frozen. This is an evaluation correction, not a model-retraining task.

S3PL originally selected its own counts. We corrected the CAC comparison by re-ranking its saved scores and taking the same \(K_s\), without retraining the model.

**Code:** selection and scoring in [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), especially lines 110–140 and 363–400.  
**Result:** [matched CAC comparison](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_peak_selection_comparison.png).  
**Machine-readable evidence:** [CAC comparison JSON](../../code/msi/results/comparisons/spatial_msipl_cac_validation/comparison.json).

## Pearson correlation (PCC)

For flattened ion image \(a\) and binary class mask \(b\),

\[
$r(a,b)=
\frac{\sum_i(a_i-\bar a)(b_i-\bar b)}
{\sqrt{\sum_i(a_i-\bar a)^2}\sqrt{\sum_i(b_i-\bar b)^2}}.$
\]

PCC lies between −1 and 1. A large positive value means high ion intensity tends to occur inside the mask; a negative value means it tends to occur outside; a value near zero means weak linear spatial agreement.

For multiclass masks, the bin is compared with each one-vs-rest class mask and the largest relevant correlation is used by the peak-evaluation logic.

If an ion image is constant, its standard deviation is zero and PCC is undefined. The code handles this rather than treating the warning as a model-training failure.

**Code:** chunked Pearson implementation in [create_pearson_labels.py](../../code/msi/baselines/s3pl/utils/create_pearson_labels.py), lines 8–29.  
**Read more:** [metrics note](04%20Metrics%20and%20Statistics.md#pearson-correlation-coefficient-pcc).

## F1 and mSCF1

For a PCC threshold \(t\), a bin is a spatially positive reference peak if its correlation with at least one expert structure is at least \(t\). For the method’s selected set:

\[
\operatorname{Precision}_t=\frac{TP_t}{TP_t+FP_t},
\qquad
\operatorname{Recall}_t=\frac{TP_t}{TP_t+FN_t},
\]

\[
F1_t=\frac{2\operatorname{Precision}_t\operatorname{Recall}_t}
{\operatorname{Precision}_t+\operatorname{Recall}_t}.
\]

The mean Spatial Correlation F1 is

\[
\operatorname{mSCF1}
=\frac{1}{4}\sum_{t\in\{0.3,0.4,0.5,0.6\}}F1_t.
\]

The multiple thresholds prevent the conclusion from depending on one arbitrary PCC cutoff. mSCF1 measures whether the selected bins have spatial patterns aligned with the supplied masks. It is not a molecule-identification metric.

**Code:** [PeakEvaluation.py](../../code/msi/baselines/s3pl/utils/PeakEvaluation.py), threshold/F1 logic around lines 41–124 and multiclass logic from line 126; our matched wrapper in [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), lines 110–140.  
**Results:** [section-level result table](../../code/msi/results/publication/current_evidence/section_level_results.csv).

## Reconstruction metrics

The deterministic reconstruction evaluation reports several views of \(x_i\) versus \(\hat{x}_i\):

### Mean squared error

\[
\operatorname{MSE}=\frac{1}{ND}\sum_{i,k}(x_{ik}-\hat{x}_{ik})^2.
\]

It heavily penalises larger pointwise errors. Lower is better.

### Mean absolute error

\[
\operatorname{MAE}=\frac{1}{ND}\sum_{i,k}|x_{ik}-\hat{x}_{ik}|.
\]

It is less sensitive than MSE to a small number of large errors. Lower is better.

### Cosine similarity

\[
\cos(x_i,\hat{x}_i)=
\frac{x_i^T\hat{x}_i}{\|x_i\|_2\|\hat{x}_i\|_2}.
\]

This measures similarity of spectral direction/shape. Higher is better.

### Scaled categorical cross-entropy

This is the same reconstruction form used during training and is defined in [VAE model and loss](#vae-model-and-loss). Lower is better.

**Code:** [evaluate_spatial_reconstruction.py](../../code/msi/scripts/evaluate_spatial_reconstruction.py), lines 109–153 and metric descriptions at lines 224–230.  
**Important interpretation:** good reconstruction does not imply good peak selection. A model can reconstruct dominant spectral intensity accurately while failing to rank the smaller set of bins that best follows tissue structure.

## Latent-space evaluation

### Balanced accuracy

For \(C\) expert classes,

\[
\operatorname{BA}=\frac{1}{C}\sum_{c=1}^{C}
\frac{TP_c}{TP_c+FN_c}.
\]

It gives each class equal weight even when class sizes differ. We use it after optimally mapping arbitrary GMM component IDs to expert class IDs.

### ARI and NMI

Adjusted Rand Index (ARI) and Normalised Mutual Information (NMI) compare two partitions while being insensitive to the arbitrary numeric names of clusters. ARI adjusts pair agreement for chance; NMI measures shared information after normalisation.

### Silhouette score

For each latent point, silhouette compares its average distance within its assigned cluster with its average distance to the nearest other cluster. Higher values indicate better-separated latent clusters.

### Moran’s I

Moran’s I measures spatial autocorrelation:

\[
I=\frac{N}{W}
\frac{\sum_i\sum_j w_{ij}(z_i-\bar z)(z_j-\bar z)}
{\sum_i(z_i-\bar z)^2}.
\]

Positive values indicate that neighbouring pixels tend to have similar values. More spatial autocorrelation is not always better: excessive smoothing can erase real boundaries.

**Code:** balanced-accuracy mapping in [evaluate_spatial_msipl_attributed_peaks.py](../../code/msi/scripts/evaluate_spatial_msipl_attributed_peaks.py), lines 143–171; Moran’s I in [evaluation.py](../../code/msi/src/spatial_msipl/evaluation.py), line 58; broader latent evaluation in [evaluate_spatial_msipl_neighbourhoods.py](../../code/msi/scripts/evaluate_spatial_msipl_neighbourhoods.py).  
**Read more:** [metrics note](04%20Metrics%20and%20Statistics.md).

## Deletion faithfulness

Deletion faithfulness checks whether the bins ranked as important actually influence the explained model output. Let \(S_K\) be the top \(K\) bins and \(x_{\setminus S_K}\) be the input after replacing those bins with section-mean values. We measure

\[
\Delta_K=F_c(x)-F_c(x_{\setminus S_K}).
\]

A larger positive drop means deleting the selected bins reduces the target GMM posterior more strongly, which supports the claim that the ranking reflects model behaviour.

Attribution samples and faithfulness samples are disjoint. This avoids evaluating the ranking only on the same pixels used to construct it.

Faithfulness is about the model’s internal dependence, not biological truth. A model can faithfully depend on a scientifically undesirable feature.

**Code:** `deletion_faithfulness` in [run_spatial_msipl_gmm_integrated_gradients.py](../../code/msi/scripts/run_spatial_msipl_gmm_integrated_gradients.py), lines 219–305.  
**Result:** individual `deletion_faithfulness.png` files under [attribution results](../../code/msi/results/experiments/spatial_msipl_attributed_peak_evaluation).

## Statistics and experimental units

### Paired section comparisons

Methods are evaluated on the same tissue sections, so differences must be paired:

\[
d_s=m_{A,s}-m_{B,s}.
\]

The exact two-sided Wilcoxon signed-rank test evaluates whether the signed paired differences are centred around zero without assuming normally distributed differences. With only eight sections, the test has limited resolution; effect sizes, win counts, and the individual section values must accompany the p-value.

### What is independent?

Thousands of pixels within one section do not become thousands of independent biological replicates. The primary collection-level comparison uses the tissue section as the paired unit. The eight sections are also not asserted to be eight independent patients, so results should be described as section-level consistency, not patient-level generalisation.

### Training seeds versus attribution-sampling seeds

- A **training seed** changes model initialisation, batch order, and stochastic training. Repeating it tests whether the learned model conclusion is stable.
- An **attribution-sampling seed** changes which pixels are sampled for IG while keeping one trained model fixed. Repeating it tests estimator stability, not training stability.

The four attribution-sampling runs gave mean mSCF1 about 0.533, SD 0.0137, and range 0.031. The later three-seed study is stronger for model stability because it independently retrained the models.

**Code:** paired summaries in [summarise_publication_results.py](../../code/msi/scripts/summarise_publication_results.py) and [summarise_spatial_msipl_cac_validation.py](../../code/msi/scripts/summarise_spatial_msipl_cac_validation.py); seed aggregation in [summarise_spatial_msipl_training_seed_stability.py](../../code/msi/scripts/summarise_spatial_msipl_training_seed_stability.py), lines 72–292.  
**Result:** [seed summary](../../code/msi/results/experiments/spatial_msipl_training_seed_stability_summary/summary.md).

## Computational measurements

We record at least:

- trainable parameter count;
- wall-clock training and evaluation time;
- peak GPU memory allocated; and
- number of epochs and spectra processed.

On GBM108-positive, the centre-only model used about **2.05 GiB** peak GPU memory, uniform mean about **2.90 GiB**, and corrected attention about **3.20 GiB**. Uniform context therefore has a real resource cost.

S3PL and Spatial-msiPL runtimes are not directly interchangeable. S3PL uses a different convolutional architecture and was run for 10 epochs; the VAE campaign used 100 epochs and requires a separate IG evaluation. Timing also includes different data access and artifact-generation work. A fair efficiency claim would require a deliberately matched benchmark protocol.

**Results:** [seed metrics CSV](../../code/msi/results/experiments/spatial_msipl_training_seed_stability_summary/seed_metrics.csv) and [CAC computational comparison](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_computational_comparison.png).  
**Reproducibility context:** [cluster and reproducibility note](06%20Cluster%20and%20Reproducibility.md).

## How to read the main result figures

1. [Primary peak quality](../../code/msi/results/publication/current_evidence/figure_1_primary_peak_quality.png): compare matched-count mSCF1 across legacy msiPL, centre-only IG, and uniform-context IG.
2. [Context effect by section](../../code/msi/results/publication/current_evidence/figure_2_context_effect_by_section.png): values above zero favour uniform context; values below zero favour centre-only.
3. [Explanation ablation](../../code/msi/results/publication/current_evidence/figure_3_explanation_ablation.png): isolates the weakness of first-layer L2 and the gain from nonlinear IG.
4. [Training-seed stability](../../code/msi/results/publication/current_evidence/figure_4_seed_stability.png): shows the spread over independently trained seeds, not just one favourable run.
5. [Matched CAC S3PL comparison](../../code/msi/results/comparisons/spatial_msipl_cac_validation/cac_peak_selection_comparison.png): includes S3PL at the same section-specific peak budgets.

## A concise explanation of the research

> We tested whether adding local tissue context to an msiPL-style variational autoencoder improves MSI peak selection. To separate the value of context from the value of the explanation method, we compared matched centre-only and contextual VAEs and extracted peaks using a nonlinear Integrated Gradients explanation of latent GMM cluster posteriors. Nonlinear IG consistently improved on the baselines used in the current matched comparisons, while uniform context helped all CAC sections but not GBM consistently. The final GBM figure still needs alignment to the later beta-tuned msiPL counts. A learned attention neighbourhood gave a small repeatable peak-quality gain on one development section, but did not improve our faithfulness measure. Matched-count S3PL remained stronger on CAC. The evidence therefore supports nonlinear attribution and a dataset-dependent role for context, rather than a universal spatial or efficiency advantage.

## Questions to ask when reading any future result

1. What changed: the architecture, training objective, attribution method, peak budget, or dataset?
2. Is the comparison paired on the same sections?
3. Are the selected peak counts equal?
4. Was the model retrained, or only re-evaluated?
5. Does the metric measure reconstruction, clustering, model faithfulness, or spatial peak quality?
6. Are labels used for training, mapping/evaluation, or both?
7. Is the result from one seed, several attribution samples, or several independently trained models?
8. Does the conclusion apply to one section, one collection, or both collections?
9. Is a negative result evidence against this implementation or against the entire idea?
10. Which exact JSON/CSV and script generated the displayed number?

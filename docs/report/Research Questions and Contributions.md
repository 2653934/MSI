# Final Research Questions and Contributions

Last updated: 2026-09-22

Status: **provisional framing for supervisor discussion**. These questions and
contributions organise the current evidence, but they should not be treated as
an approved replacement for the proposal until discussed with Hairong. The
next planned confirmation is the supervision meeting on Monday, 2026-09-28.

## Report title

**Spatial Context and Nonlinear Attribution for Peak Learning in Mass
Spectrometry Imaging**

The title deliberately names the two parts that the experiments ultimately
separated: the neighbourhood supplied to the VAE and the method used to rank
the input mass-to-charge bins after training.

## Research problem

Mass spectrometry imaging (MSI) peak learning must reduce tens of thousands of
mass-to-charge bins to a useful peak set without discarding spatially coherent
but low-intensity signals. Legacy msiPL learns a compact spectrum
representation but is spatially blind and derives peaks from selected network
weights. S3PL exploits spatial patches, but its released implementation is a
substantially different three-dimensional convolutional model. It was therefore
unclear whether a lightweight VAE could benefit from local context, whether a
nonlinear explanation of its learned representation would yield better peaks,
and what accuracy--compute trade-off would result.

## Research aim

To develop and evaluate a lightweight, context-aware VAE peak-learning
framework for MSI, and to determine separately whether neighbourhood context
and nonlinear latent-space attribution improve spatially structured peak
selection over spatially blind and weight-based baselines.

## Final research questions

### RQ1: Neighbourhood value

Under matched architectures and training conditions, how does incorporating an
eight-neighbour Moore context into an msiPL-style VAE affect spectral
reconstruction, label-free latent tissue separation and matched-count mSCF1
relative to a centre-only VAE?

This is answered by the paired centre-only and uniform-mean experiments on all
eight GBM and eight CAC sections. It does not assume that a neighbourhood must
help.

### RQ2: Explanation method

Does nonlinear, GMM-targeted Integrated Gradients produce better spatially
structured peak rankings than legacy msiPL and a simple first-layer L2 ranking
when the number of selected peaks is held constant within each section?

This isolates the main methodological contribution from the input-context
choice. The matched peak budget prevents a method from obtaining a better score
merely by returning more peaks.

### RQ3: Learned context and robustness

What peak-quality, attribution-faithfulness and computational trade-offs arise
when uniform neighbourhood averaging is replaced by corrected learned
attention, and are the observed differences stable across independent model
training seeds?

This is a targeted development-section question. It is not evidence that the
same attention result generalises to all patients or sections.

## Objectives

1. Audit and preprocess the GBM and CAC MSI collections while preserving
   measured-coordinate and mask alignment.
2. Implement controlled centre-only, uniform-mean-context and learned-attention
   VAE variants with otherwise matched training settings.
3. Fit a label-free Gaussian mixture model to frozen latent means and propagate
   its posterior through the complete encoder using Integrated Gradients.
4. Reproduce the legacy msiPL and executable S3PL baselines and evaluate all
   peak lists using section-specific matched peak budgets where comparison
   requires them.
5. Quantify reconstruction, latent separation, mSCF1, explanation
   completeness, deletion faithfulness, runtime and memory.
6. Test broad section-level behaviour on eight GBM and eight CAC sections, and
   test model-training-seed stability for the principal variants on the frozen
   development section.

## Contributions supported by the evidence

1. **A controlled decomposition of spatial peak learning.** The experiments
   separate the effect of neighbourhood input from the effect of the nonlinear
   peak-ranking method by using a matched centre-only VAE and identical
   GMM--Integrated-Gradients evaluation.
2. **A nonlinear, label-free peak-ranking pipeline.** A two-component GMM fitted
   to frozen latent means supplies the target whose posterior is attributed to
   the original m/z bins. This avoids using expert masks during training or
   ranking.
3. **Cross-collection evidence that attribution is the robust gain.** Nonlinear
   Integrated Gradients improves matched-count mSCF1 over legacy msiPL on all
   eight GBM and all eight CAC sections, whereas the first-layer L2 shortcut is
   generally inadequate.
4. **A bounded finding about spatial context.** Uniform context is not
   universally beneficial: it does not consistently improve GBM reconstruction
   or mSCF1, but it improves mSCF1 over the centre-only control on all eight CAC
   sections.
5. **A corrected attention ablation with a stated limitation.** Corrected
   attention improves mSCF1 over uniform averaging in all three training seeds
   on GBM108-positive, but does not improve deletion faithfulness and requires
   more GPU memory. It therefore does not pass the combined promotion rule.
6. **A reproducible evaluation record.** The repository includes data adapters,
   validation audits, restartable Slurm jobs, matched-count evaluation,
   completeness and faithfulness checks, section-level outputs and publication
   figures.

## Claims the report must not make

- Neighbourhood context is universally better than a centre-only VAE.
- Attention has been validated across the complete GBM and CAC collections.
- The S3PL paper result was fully reproduced on GBM.
- Eight tissue sections are equivalent to eight independent patients.
- Better mSCF1 proves biological biomarker validity.
- A ten-epoch S3PL runtime and a one-hundred-epoch VAE runtime are directly
  comparable measures of algorithmic efficiency.

## One-sentence thesis

In these experiments, explaining a frozen VAE nonlinearly is a more reliable
source of peak-selection improvement than adding neighbourhood input alone,
while spatial context remains useful on CAC and corrected attention shows a
small but seed-stable development-section gain at an increased computational
cost.

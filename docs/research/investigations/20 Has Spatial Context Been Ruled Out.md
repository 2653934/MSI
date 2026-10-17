# 20 Has Spatial Context Been Ruled Out? Scope of the Evidence and Untested Spatial Avenues

Date: 17 October 2026 (supervisor note, Cowork). Status: discussion and literature note. No new experiments are run or approved here.

## 1. The question

The proposal (RQ1–RQ3) asked whether integrating local spatial covariance into a 1D VAE, through concatenated neighbourhood input, an explicit spatial penalty and noise augmentation, improves the identification of spatially structured peaks over spatially blind msiPL. After the 28 September meeting, Hairong asked for a stronger investigation before the mixed spatial effect is treated as settled.

Two separate claims must not be merged:

- **(A) "Spatial context does not help."** This is a statement about *spatial information*.
- **(B) "We found a better peak-ranking method than the one we proposed."** Segment-then-correlate on the learned latent segmentation beats IG. This is a statement about *ranking*, and it says nothing about spatial information either way.

## 2. What the evidence actually supports

**Shown (with controls, 16 sections, predeclared rules):** within this architecture class, a dense VAE whose encoder receives the centre spectrum plus neighbourhood information, spatial context gives **no reliable, spatially specific benefit** for peak picking. The tested forms were:
- uniform 3×3 mean, 5×5, 7×7 and 9×9 windows (larger is never better; worse on GBM);
- learned single-head attention (equivalent to uniform), and attention forced by centre masking (stays uniform; slightly worse on GBM);
- depthwise aggregation;
- zero, shuffled and frozen-swap controls (no spatial specificity);
- an explicit adjacent-latent smoothness penalty (smoother latents, worse reconstruction, no consistent probe gain);
- Poisson augmentation (failed its predeclared gate).

**Mechanistic reason:** neighbouring spectra are almost duplicates of the centre (median cosine ≈ 0.98), so averaging or attention mostly denoises an input that the dense encoder and 5-D bottleneck already summarise.

**Not shown:** that spatial information is useless for peak picking in general. Two results in this project point the other way:
1. **S3PL**, a 3D convolutional model on spectral patches, depends strongly on real neighbours during training. Retrained without them, it falls from 0.59 to 0.15–0.18 on CAC, 8/8 sections in both seeds.
2. **Moran's I**, a purely spatial statistic computed per ion image with no model, is a strong label-free ranking. On RCC it is the best label-free method (0.63 vs 0.57–0.60 for correlation with the GMM map; ahead in 5/8 runs per arm). It is level with that correlation on CAC and about 0.06 below it on GBM.

**Correct scope of the claim:** "Spatial context **as encoder input to a dense VAE** adds no measurable, spatially specific value. Spatial structure is useful when it enters through the ranking statistic (Moran's I) or a convolutional architecture (S3PL)."

That answers Hairong's concern more precisely than "spatial doesn't help". It also explains why the proposal's mechanism failed without overgeneralising.

## 3. Where spatial information has not been tested

The pipeline has four places where spatial structure could enter: **(i) model input**, **(ii) training objective**, **(iii) segmentation**, **(iv) ranking**. We tested (i) extensively and (ii) once (the latent penalty). (iv) was tested only as a baseline (Moran's I). **(iii) was never tested**, even though the segmentation is the component that carries the result.

| Avenue | Stage | Prior work | Cost here | Why it matters |
|---|---|---|---|---|
| **Spatially regularised segmentation**: a hidden Markov random field (Potts) prior on the GMM labels, or spatially-aware clustering of the latent means | (iii) | Alexandrov & Kobarg 2011 (spatially aware clustering, with structure-adaptive edge-preserving weights); Bemis et al. 2016 (spatial shrunken centroids, adaptive neighbour weights); Capitoli et al. 2023 (Bayesian mixtures with HMRF for MSI) | CPU on saved latents; no retraining | Spatial smoothing applied where the signal lives. The most direct test of "does spatial help the part that works" |
| **Spatially smoothed posterior or ion images before correlation** (Gaussian, or edge-preserving as in Alexandrov et al. 2010) | (iii)/(iv) | Alexandrov et al. 2010 (edge-preserving denoising, then clustering) | CPU, minutes | Cheap check of whether pixel noise limits correlation ranking |
| **Combined ranking**: segmentation correlation × spatial coherence (rank fusion with Moran's I or the spatial-chaos measure) | (iv) | Alexandrov & Bartels 2013 (spatial chaos); Palmer et al. 2017 (MSM score uses spatial chaos); Cassese et al. 2016 (spatial autocorrelation in MSI) | CPU, minutes | Moran's I wins on RCC and posterior wins on GBM, so the two may be complementary. Post-hoc risk: must be predeclared |
| **Graph-based encoders**: graph attention over similarity-weighted pixel graphs | (i) | GraphMSI (Guo et al. 2025); STAGATE (Dong & Zhang 2022); SpaGCN (Hu et al. 2021) | New model; days | The modern version of "neighbourhood input". Similarity-weighted edges differ from our uniform or attention windows mainly in operating over a learned graph |
| **Ion-image-level spatial learning**: embed and cluster ion images, not pixel spectra | separate paradigm | Zhang et al. 2021 (spatially aware ion-image clustering); Guo et al. 2023 (noise-robust deep ion clustering); IonMorphNet (Weigand et al. 2026); DeepION (Guo et al. 2024) | New pipeline | Spatial structure is the object being modelled; the closest relatives of a Moran's-I-style ranking |
| **Local spatial statistics** (local Moran / Moran quadrant maps) | (iv) | bioRxiv 2025 (Moran quadrant maps for molecular imaging; authors to verify) | CPU | Refines the global Moran's I baseline |

## 4. Recommendation (for discussion with Hairong, Monday 19 October)

1. **Report the scoped claim from Section 2**, not "spatial context does not help".
2. **If one more experiment is justified, it is the spatially regularised segmentation (row 1).** It is CPU-only on saved latents, it tests spatial information at the stage that matters, and it has a direct literature lineage (Alexandrov & Kobarg 2011; Bemis et al. 2016). Predeclare it before running: the same K, the same scoring and budgets, and a comparison against plain posterior correlation and Moran's I on all 24 sections/runs, with the +0.02 / ≥ 6 of 8 rule.
3. **Rows 2–3 are cheap but add multiple-comparison risk.** At most one of them, predeclared.
4. **Rows 4–5 are future work.** Name them in the Discussion as the natural next step for "spatial input".

The experiment window closes Tuesday 20 October. Anything above row 1 needs Hairong's explicit approval on Monday.

## 5. Result of Test S (17 October; protocol 18 Section 6.2; jobs 69631/69658)

**Predeclared verdicts, spatially regularised segmentation (S1) vs plain posterior correlation:**

| Collection / arm | Rule result | Mean change (bin), positive sections |
|---|---|---|
| GBM centre-only | equivalent | +0.013, 5/8 |
| GBM uniform | mixed (does not meet "helps") | +0.029, 3/8 (median 0.000) |
| CAC centre-only | equivalent | −0.001, 4/8 |
| CAC uniform | equivalent | +0.004, 5/8 |
| RCC centre-only | equivalent | −0.012, 5/8 |
| RCC uniform | incomplete; no verdict (7/8) | −0.023, 4/7 |

All validity gates passed: the refit gave ARI 1.0, and 158/158 saved scores were reproduced to 1e-12.

**Reading:**
- **Spatial regularisation of the segmentation does not reliably improve peak ranking on any collection.** It is "helps" nowhere; equivalent in 4 of 5 decided cells; mixed in 1.
- The averages hide large, opposite-signed changes in single sections: GBM12_1 +0.205, GBM22_2 −0.143 and +0.147 (a development section), RCC UH9912_01 −0.143, UH9812_03 −0.166. Smoothing changes the segmentation a lot (ARI vs production 0.69–0.83), and the peak score follows whether that change happens to suit the annotation.
- **It moves segmentation accuracy in opposite directions by dataset** (descriptive). On GBM, balanced accuracy against the expert mask rises (0.87 → 0.93; 0.91 → 0.95). On CAC and RCC it falls (0.68 → 0.67, 0.67 → 0.64; 0.77 → 0.71, 0.82 → 0.78). One possible reason is that GBM's annotated regions are large and contiguous, while CAC and RCC are finer or three-class; the morphology was not analysed.
- **Predeclared descriptive analysis (S2b, no verdict):** fusing correlation and Moran's I rankings is about level with plain correlation on GBM (+0.001 to +0.003). It is higher on RCC (+0.055, 7/8; +0.047, 6/7) and at CAC P1 (+0.037, 8/8; +0.034, 7/8). Moran's I alone is still the best single method on RCC. Treat it as a lead for future work, not a confirmed result.

**Updated scoped claim:** in this pipeline, neither neighbourhood input to the encoder (windows, attention, masking, latent penalty) nor structure-adaptive smoothing of the segmentation gave a consistent, spatially specific peak-picking gain across the tested collections. Spatial structure is informative as a ranking statistic (Moran's I), and S3PL depends on real neighbours under its patch-level objective; architecture and objective are not separated. The project has now tested three of the four entry points; graph and ion-image models remain future work.

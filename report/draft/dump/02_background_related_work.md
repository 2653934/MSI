# Background and related work

### C147 Abdelmoula et al. 2021 — msiPL
- Statement: Introduced VAE-based MSI peak learning and the legacy baseline/design origin used here.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `abdelmoula2021peak`.
- Verified by supervisor: no
- Caveats: Cite for msiPL, not for claims that learned weights automatically identify biomarkers.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C148 Weigand et al. 2026 — S3PL
- Statement: Introduced spatial self-supervised peak learning, mSCF1, the reference rule, released counts and CAC/GBM protocol reproduced here.
- Numbers: arXiv:2603.10487v1.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `weigand2026spatial`; investigation 19.
- Verified by supervisor: yes: investigation 19 accepted
- Caveats: Public supplements S1–S14 were unavailable.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C149 Weigand et al. 2026 — IonMorphNet
- Statement: Provides a related learned ion-image morphology pipeline and a public script containing published S3PL per-section scores.
- Numbers: arXiv:2604.19369; audited HEAD 640406a.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `weigand2026ionmorphnet`; investigation 19.
- Verified by supervisor: yes: investigation 19 accepted
- Caveats: Related work, not an evaluated baseline.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C150 Abdelmoula et al. 2022 — massNet
- Statement: Describes massNet and is the source citation for the GBM dataset.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `abdelmoula2022massnet`.
- Verified by supervisor: no
- Caveats: Separate dataset provenance from S3PL evaluation claims.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C151 Sundararajan, Taly and Yan 2017
- Statement: Defines Integrated Gradients and its attribution axioms.
- Numbers: ICML 2017.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `sundararajan2017axiomatic`.
- Verified by supervisor: no
- Caveats: The project evaluates one IG configuration.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C152 Kingma and Welling 2014
- Statement: Introduces variational autoencoders used as the representation-learning foundation.
- Numbers: ICLR 2014.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `kingma2014autoencoding`.
- Verified by supervisor: no
- Caveats: General method reference.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C153 Alexandrov et al. 2010
- Statement: Classic edge-preserving denoise-then-segment MSI pipeline; supports the segment-then-correlate lineage.
- Numbers: J. Proteome Res. 9(12):6535–6546; doi:10.1021/pr100734z.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker correction 2026-10-17
- Caveats: To add to bibliography.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C154 Alexandrov and Kobarg 2011
- Statement: Introduces efficient spatially aware MSI clustering with structure-adaptive edge-preserving neighbour weights; basis for Test S's framing.
- Numbers: Bioinformatics 27(13):i230–i238.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct); investigation 20.
- Verified by supervisor: yes: references tracker correction 2026-10-17
- Caveats: Do not confuse with the 2010 paper.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C155 Bemis et al. 2016
- Statement: Probabilistic/spatial shrunken-centroid segmentation with ion selection; closest prior method to segment-then-select.
- Numbers: Mol. Cell. Proteomics 15(5):1761–1772; doi:10.1074/mcp.O115.053918.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: To add to bibliography.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C156 Bemis et al. 2015 — Cardinal
- Statement: Describes the Cardinal MSI analysis package and source context for the RCC dataset/workflow.
- Numbers: Bioinformatics 2015.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: Bibliographic details marked “verify.”
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C157 Moran 1950
- Statement: Original reference for Moran's I spatial autocorrelation statistic used as a model-free ranking.
- Numbers: Biometrika 1950.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: Bibliographic details marked “verify.”
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C158 Alexandrov and Bartels 2013
- Statement: Introduces a measure of spatial chaos for ion images, supporting label-free spatial-informativeness ranking.
- Numbers: Bioinformatics 29(18):2335–2342; doi:10.1093/bioinformatics/btt388.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: To add to bibliography.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C159 Palmer et al. 2017
- Statement: METASPACE's MSM score uses spatial chaos and illustrates spatial-coherence scoring in practice.
- Numbers: Nat. Methods 14:57–60.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `palmer2017fdr`.
- Verified by supervisor: no
- Caveats: Also motivates avoiding molecular-identity claims without annotation.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C160 Cassese et al. 2016
- Statement: Demonstrates spatial autocorrelation in MSI ion images and motivates Moran's I as meaningful.
- Numbers: Anal. Chem. 88(11):5871–5878; doi:10.1021/acs.analchem.6b00672.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: To add to bibliography.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C161 Capitoli et al. 2023
- Statement: Uses Bayesian mixtures with an HMRF/Potts prior for spatial MSI segmentation; an untested future avenue.
- Numbers: SIS 2023 short papers, pp.1127–1132.
- Label: descriptive
- Source: `docs/meetings/references.md`; investigation 20.
- Verified by supervisor: no
- Caveats: Optional conference reference.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C162 Dong and Zhang 2022 — STAGATE
- Statement: Graph-attention autoencoder for spatial domains; a graph analogue of local attention windows.
- Numbers: Nat. Commun. 13:1739.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: Spatial transcriptomics, not MSI.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C163 Hu et al. 2021 — SpaGCN
- Statement: Graph convolution combines expression, location and histology, followed by domain-guided feature selection.
- Numbers: Nat. Methods 18:1342–1351; doi:10.1038/s41592-021-01255-8.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: Spatial transcriptomics, not MSI.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C164 Guo et al. 2025 — GraphMSI
- Statement: Applies graph neural networks to MSI segmentation using spectra and spatial relationships.
- Numbers: Adv. Sci. 12(8):2410840; doi:10.1002/advs.202410840.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: Future-work comparator, not evaluated.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C165 Zhang et al. 2021
- Statement: Learns and clusters ion-image representations, moving spatial modelling to the ion-image level.
- Numbers: Anal. Bioanal. Chem. 413(10):2803–2819.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: Future-work paradigm.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C166 Guo et al. 2023
- Statement: Denoises ion images with a convolutional autoencoder and clusters ions by spatial pattern.
- Numbers: Bioinformatics 39(2):btad067.
- Label: descriptive
- Source: `docs/meetings/references.md` (checked 17 Oct).
- Verified by supervisor: yes: references tracker 2026-10-17
- Caveats: Related ion-image method, not evaluated.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C167 Moran quadrant maps 2025
- Statement: Uses local Moran statistics for molecular-imaging segmentation and colocalisation; possible extension beyond global Moran's I.
- Numbers: bioRxiv doi:10.1101/2025.10.27.684518.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: Authors/details explicitly marked “verify.”
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C168 Mazarura, Jarvis and Bau 2025
- Statement: Shows reconstruction, clustering and downstream classification can rank AE/CNN-AE/PCA/NMF differently, supporting the reconstruction-versus-use distinction.
- Numbers: Silhouette CNN-AE 0.515 > AE 0.460 > NMF 0.417 > PCA 0.271; AUC AE 0.874 > CNN-AE 0.820 > PCA 0.789 > NMF 0.768.
- Label: descriptive
- Source: `docs/meetings/references.md`; local paper read 17 Oct.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Unpublished Wits report; citation form and inconsistent MSE text/table require verification; quote ranks, not ratios.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C169 Schwarz 1978
- Statement: Introduces BIC, used for the component-count sensitivity.
- Numbers: Annals of Statistics 1978.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: Bibliographic details marked “verify.”
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C170 Pedregosa et al. 2011
- Statement: Documents scikit-learn implementations used for GMM, scaling, ARI and NMI.
- Numbers: JMLR 2011.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: To add/verify.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C171 Hubert and Arabie 1985
- Statement: Defines the adjusted Rand index used in segmentation consistency checks.
- Numbers: Journal of Classification 1985.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: To add/verify.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C172 Vaswani et al. 2017
- Statement: Source for scaled dot-product attention and the √d scaling in the corrected aggregator.
- Numbers: NeurIPS 2017.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: To add/verify.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C173 Caprioli et al. 1997
- Statement: Foundational MALDI imaging reference.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `caprioli1997maldi`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C174 Schwamborn et al. 2010
- Statement: MSI review/application background.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `schwamborn2010molecular`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C175 Buchberger et al. 2018
- Statement: General mass-spectrometry-imaging review and application context.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `buchberger2018mass`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C176 Korber et al. 2025
- Statement: Contemporary MSI review/application context.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `korber2025mass`.
- Verified by supervisor: no
- Caveats: Verify scope when cited.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C177 Ye et al. 2013
- Statement: MSI application/review background for molecular mapping.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `ye2013msi`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C178 Zhang et al. 2025 infectious MSI review
- Statement: Recent MSI applications reference.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `zhang2025msi_infectious`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C179 Aspect Analytics MSI primer
- Statement: Web primer for MSI data-analysis background.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `aspect2026msi_intro`.
- Verified by supervisor: no
- Caveats: Prefer peer-reviewed sources for substantive claims.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C180 Deininger et al. 2011
- Statement: Reference for TIC normalisation in MSI.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `deininger2011normalization`.
- Verified by supervisor: no
- Caveats: Distinguish true TIC from S3PL's released helper.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C181 Gibb and Strimmer 2012 — MALDIquant
- Statement: Classical MALDI preprocessing/peak-picking package proposed as a comparator but not completed.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `gibb2012maldiquant`; proposal-to-outcome row 8.
- Verified by supervisor: yes: proposal-to-outcome accepted 2026-10-20 10:25
- Caveats: No superiority claim over classical peak picking.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C182 Lieb et al. 2020
- Statement: Sparse-frame peak-detection related work.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `lieb2020sparse`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C183 Winderbaum et al. 2015
- Statement: Feature extraction for imaging mass spectrometry.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `winderbaum2015feature`.
- Verified by supervisor: no
- Caveats: Background only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C184 Li et al. 2022
- Statement: Machine-learning peak picking in NMR, a cross-domain comparator.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `li2022machinelearningpeakpicking`.
- Verified by supervisor: no
- Caveats: NMR, not MSI.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C185 Cordes et al. 2021 — M²aia
- Statement: MSI tooling used in related preprocessing/data paths.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `cordes2021m2aia`.
- Verified by supervisor: no
- Caveats: Software/methods context.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C186 Inglese et al. 2017
- Statement: Deep-learning application with 3D-DESI, positioning neural MSI analysis.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `inglese2017deep`.
- Verified by supervisor: no
- Caveats: Related work only.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C187 Guo et al. 2024 — DeepION
- Statement: Learns low-dimensional ion-image representations with MSI-specific augmentations.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `guo2024deepion`.
- Verified by supervisor: no
- Caveats: Related ion-image paradigm, not evaluated.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C188 Huber et al. 2021 — Spec2Vec
- Statement: Learned spectral-similarity related work for molecular annotation.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `huber2021spec2vec`.
- Verified by supervisor: no
- Caveats: Tandem spectral similarity, not MSI peak selection.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C189 Huber et al. 2021 — MS2DeepScore
- Statement: Deep learned similarity for MS/MS spectra, positioning downstream annotation.
- Numbers: Not applicable.
- Label: descriptive
- Source: `docs/meetings/references.md`; bib key `huber2021ms2deepscore`.
- Verified by supervisor: no
- Caveats: Not an evaluated method.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C190 Dill et al. 2011 — RCC
- Statement: Dataset/source reference for DESI imaging of renal cell carcinoma distributed through Cardinal workflows.
- Numbers: 8 runs used here.
- Label: descriptive
- Source: `docs/meetings/references.md`.
- Verified by supervisor: no
- Caveats: Citation details and exact dataset lineage marked “verify.”
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

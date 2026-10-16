# 19 Upstream Repository and Paper Audit

Date: 16 October 2026 (supervisor review, Cowork).
Scope: check our msiPL and S3PL baselines against (1) the S3PL paper itself, (2) the live upstream repositories, and (3) the authors' follow-up repository (IonMorphNet), before the report is written.

## Sources checked

| Source | Version checked | Notes |
|---|---|---|
| Weigand et al., *Spatial self-supervised Peak Learning and correlation-based Evaluation of peak picking in MSI*, arXiv:2603.10487v1 (11 Mar 2026) | local PDF in `Papers/` | Only version on arXiv. No supplementary tables (S1–S14) or ancillary files are public, so the per-dataset hyperparameter table S1 and peak-count table S3 could not be checked. |
| `github.com/CeMOS-IS/S3PL` | HEAD `660e3d9` (29 Apr 2026) | Tagged "paper-submission" v1.0.0. |
| `github.com/wabdelmoula/msiPL` | HEAD `1e8d5cf` (11 Jul 2021) | Identical to our recorded import commit (`baselines/msipl/UPSTREAM.md`). Nothing to update. |
| `github.com/CeMOS-IS/IonMorphNet` (Weigand et al. follow-up, arXiv:2604.19369) | HEAD `640406a` (3 Jun 2026) | Contains a copy of the S3PL evaluator and a script with the **per-section published scores** (`msianalyzer/external/s3pl/sota_comparison.py`). |

## 1. Our S3PL code is the current upstream code

- Upstream S3PL history after the initial commit (Oct 2024): README/figure/licence edits, and a `main.py` command-line parser (Dec 2025). `model/`, `train.py` logic, `utils/PeakEvaluation.py`, `utils/create_pearson_labels.py`, `helpers.py` and `data_configs.py` are unchanged since the initial commit.
- Our first import (`1fa881c`, 20 Aug 2026) differs from upstream HEAD only in plumbing: absolute data paths, an `artifact_root`, package-style imports, and parser defaults of `None`. The model, training loop, normalisation helper, label creation, evaluation and `data_configs.py` are byte-identical (CRLF-normalised sha256).
- IonMorphNet's copy of the S3PL evaluator (`peak_evaluation.py`, `create_pearson_labels.py`, `data_configs.py`) is a formatting refactor with identical logic and identical `num_GT_peaks`.
- **Conclusion:** there is no later upstream fix that we are missing, and the authors' own later work uses the same evaluator.
- **Upstream quirk (does not affect us):** in upstream `main.py` (Dec 2025 onwards) every parser default is non-`None` (`--peaks_per_spectral_patch 512`, `--spectral_patch_size 3`, …), so command-line defaults silently override `config.json`. The 2024 code used for the paper read `config.json` directly, and our `main.py` sets the defaults to `None`, so `config.json` wins.

## 2. What the paper specifies that we must match

- **Budget (number of peaks n):** set per collection from the reference set at PCC **0.4 (GBM), 0.5 (RCC), 0.3 (CAC)** (Section 3.2). The released `num_GT_peaks` reproduce our GBM |R@0.4| exactly and our RCC |R@0.5| exactly in 5/8 runs (within 13 bins otherwise).
  - **Action taken:** the RCC budget was wrongly |R@0.4|. It is corrected to the released targets (supervisor chat, 16 Oct 19:47).
  - **Still open:** the CAC released targets match none of our reference sizes, including 0.3. The paper text says 0.3, and the derivation in the released data is unknown.
- **Best S3PL hyperparameters per collection (Section 3.3):**

  | Collection | Patch size p | Peaks per patch z | Ours |
  |---|---|---|---|
  | GBM | 3 | 256 | matches |
  | CAC | 9 | 256 | matches |
  | RCC | 5 | 1024 | not run |

  Kernel depths d1 = 51 and d2 = 1, 10 epochs, batch 16, lr 1e-2 for all.
- **The "best values" were chosen by ablation on the same evaluation sections** (Section 3.3: "We set the hyperparameters … to the best values being determined by the corresponding experiment"). The published Table 3 is therefore a tuned-on-test figure. This is worth one sentence in the report when discussing the GBM gap.
- **The normalisation text says TIC, but the released helper is named `tic_norm_spectra` and divides by the per-spectrum maximum.** This was already known (`massnet_gbm_reproduction/README.md`) and is confirmed upstream.

## 3. Published vs our scores, per section

Published per-section values: IonMorphNet `sota_comparison.py`. Their means equal the paper's Table 3: S3PL GBM 0.496, CAC 0.601, RCC 0.470; msiPL GBM 0.403, CAC 0.431, RCC 0.159.
Ours: S3PL GBM from `comparisons/s3pl_gbm_stability_runtime/s3pl_gbm_seed_screen.csv` (initialisation seeds 1–3, 10 epochs, p = 3); S3PL CAC from the native-count runs (p = 9, 10 epochs, seed 1); legacy msiPL from `comparisons/msipl_weigand_2026_tuned/section_metrics.csv`.

### S3PL

| GBM section | Published | Ours, seeds 1 / 2 / 3 |
|---|---:|---|
| GBM12_1 | 0.27 | 0.131 / 0.075 / 0.099 |
| GBM12_2 | 0.55 | 0.508 / 0.273 / 0.488 |
| GBM22_1 | 0.47 | 0.292 / 0.171 / 0.257 |
| GBM22_2 | 0.61 | 0.349 / 0.290 / 0.332 |
| GBM39_1 | 0.38 | 0.277 / 0.137 / 0.206 |
| GBM39_2 | 0.56 | 0.464 / 0.487 / 0.595 |
| GBM108_positive | 0.47 | 0.026 / 0.444 / 0.079 |
| GBM108_negative | 0.66 | 0.357 / 0.570 / 0.659 |

| CAC section | Published | Ours |
|---|---:|---:|
| 40TopL | 0.68 | 0.687 |
| 160TopL | 0.53 | 0.508 |
| 200TopL | 0.61 | 0.672 |
| 240TopL | 0.67 | 0.669 |
| 280TopL | 0.63 | 0.386 |
| 360TopL | 0.64 | 0.644 |
| 400TopL | 0.35 | 0.456 |
| 520TopL | 0.70 | 0.704 |

- **CAC:** the reproduction holds at collection level (0.591 vs 0.601, inside their 95% CI 0.506–0.697) and per section in 5/8 within 0.025. Two sections differ substantially in opposite directions (280TopL −0.24, 400TopL +0.11). One seed only, so we cannot tell whether these are initialisation effects; the GBM seed screen suggests they could be.
- **GBM:** 23 of our 24 seed-runs are below the published value; the only exception is GBM39_2 seed 3 (0.595 vs 0.56). GBM108_negative seed 3 is level (0.659 vs 0.66). In 7/8 sections the published value lies above all three of our seeds (every section except GBM39_2). **The gap is therefore systematic, not seed luck.** It points to a difference in data, preprocessing or configuration that the paper and the released code do not document, consistent with the conclusion in the GBM reproduction README.

### Legacy msiPL (budget-tuned, as in the paper)

| GBM | 12_1 | 12_2 | 22_1 | 22_2 | 39_1 | 39_2 | 108+ | 108− |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Published | 0.25 | 0.38 | 0.41 | 0.44 | 0.33 | 0.49 | 0.40 | 0.52 |
| Ours | 0.245 | 0.478 | 0.381 | 0.469 | 0.315 | 0.469 | 0.410 | 0.548 |

| CAC | 40 | 160 | 200 | 240 | 280 | 360 | 400 | 520 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Published | 0.44 | 0.43 | 0.38 | 0.48 | 0.46 | 0.41 | 0.36 | 0.52 |
| Ours | 0.478 | 0.358 | 0.426 | 0.398 | 0.319 | 0.401 | 0.326 | 0.512 |

- **GBM:** close per section (|diff| ≤ 0.03 in 7/8; GBM12_2 +0.10).
- **CAC:** noisier per section (|diff| up to 0.14, at 280TopL), but the mean is inside their CI. msiPL's peak count is grid-searched to within ±50 of the target (paper Section 3.2), so per-section counts, and hence scores, are not expected to match exactly.

## 4. A further observation (descriptive, weak)

The same IonMorphNet script also holds a stale collection-level summary array: S3PL GBM / RCC / CAC = 0.534 / 0.568 / 0.622 and msiPL RCC = 0.101. These differ from the per-section values directly below them and from the paper (0.496 / 0.470 / 0.601; 0.159). The authors' own reported S3PL numbers therefore changed between versions (the paper went through two revisions, Dec 2025 and Apr 2026), while the released code did not. This is consistent with the published GBM figure depending on runs or settings not captured by the release. **Do not overstate this:** it is an unexplained plotting array, not a documented result.

## 5. What this changes

1. **Report, RQ1 section:** add the per-section reproduction tables (or a compact figure) and state: msiPL reproduces on both collections; S3PL reproduces on CAC (collection level, 5/8 sections); S3PL on GBM is systematically below the published values in every section and seed.
2. **Report, limitations:** the published hyperparameters were selected on the evaluation sections, and the supplementary tables are not public.
3. **RCC:** the budget is corrected to the released targets. If S3PL is ever run on RCC, use p = 5 and z = 1024 (paper Section 3.3), not the GBM/CAC values.
4. **Open, low priority:** derive the CAC released targets (`num_GT_peaks`); they match no reference size. Only relevant if the CAC budget is questioned.

## Provenance

- Upstream clones were taken in the Cowork cloud workspace on 16 Oct 2026 (not committed).
- Per-section published values were transcribed from `IonMorphNet/msianalyzer/external/s3pl/sota_comparison.py` at `640406a`.
- Our values were read from the local result files named above.

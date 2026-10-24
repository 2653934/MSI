# Verification of the report dump (C001–C238)

Verifier: Claude Code, 24 October 2026 (SAST). Sequential pass, no subagents, no cluster access. Dump items and sources were not edited.

**Method.** Numbers were recomputed from the cited CSV/JSON files with small pandas scripts (local `tmp/test-venv`). Cited paths were checked mechanically for every `Source:` line (all exist except where marked). Labels were compared with protocol 18 (Sections 6–7.1) and the cited chat rulings.

**Status key.** OK; MISMATCH (a number is wrong); PATH MISSING; LABEL WRONG (the label, or a required disclosure in the caveats, does not match protocol 18 / the ruling); UNVERIFIABLE (no saved artifact holds the number, or it is a literature/process claim outside the result files); NEEDS SUPERVISOR (a judgement call, not a plain error).

**Recurring abbreviations.** `tests.csv` = `code/msi/results/diagnostics/statistics_6_6/tests.csv`; `collection_summary` = `code/msi/results/publication/current_evidence/fair_scoring_collection_summary.csv`; `rcc/…1017` = `code/msi/results/diagnostics/fair_scoring_baselines/rcc/decisions_20261017_local/decisions.json`; `test_r` = `code/msi/results/diagnostics/fair_scoring_baselines/test_r/decisions_20261017_local/decisions.json`.

## 09 Main ranking

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C044 | LABEL WRONG | collection_summary: GBM −0.2251/−0.2333, CAC −0.0779/−0.0471, 0/8 positive each; rcc/…1017: centre −0.1556 (8, 0 positive), uniform −0.1853 (7, 0 positive); 8+8+8+8+8+7 = 47 ✓. All numbers OK. | The single label is wrong for the set. Protocol 18 §7.1(1) requires the reporting wording "Neither predeclared verdict applies, because IG scored below posterior-\|PCC\| in every section" (the summariser's "mixed / not resolved by the predeclared rule" is a fall-through, not a mixed result). RCC uniform_mean is labelled "incomplete; no verdict (7/8 runs)" in rcc/…1017 and must keep that label. Add "bin level, seed 1" to the statement. |
| C045 | OK | test_r decision_1: bin level, seeds 1–3, 140 section comparisons (47 reference + 93 replication), 136 negative ✓. CAC seed 2: centre P1 6/8, uniform bin 6/8 and P1 6/8 ✓. Incomplete seed-arms: RCC centre s2, RCC uniform s1 and s3, GBM uniform s3 = 4 ✓. Label matches protocol 18 §10 and chat 2026-10-20 ("does not hold overall"). | Minor: say "at bin level" beside 136/140 (the count is bin-only). |
| C046 | MISMATCH | tests.csv F1 bin rows: all six Holm p = 0.046875, n_positive 0, r = −1 ✓; GBM centre −0.2445 ✓; CAC centre −0.07735 ✓; CAC uniform P1 Holm 0.078, 7/8 negative ✓. | RCC centre seed-mean difference is −0.1516 (n = 7), not "about −0.14" (−0.136 is RCC uniform, n = 6). Caveat should also give the seed-mean n: GBM uniform 7, RCC centre 7, RCC uniform 6 (sections with all three seeds). "Holm values sit at the smallest attainable p" is loose: the raw p-values are at the minimum attainable for each n; the Holm-adjusted values are 0.047. |
| C047 | LABEL WRONG | aggregate_method_results.csv: legacy 0.4142/0.4024; IG GBM 0.5178/0.5111, CAC 0.5285/0.5595; collection_summary legacy wins 8/8 in all four arms ✓. Numbers OK. | Missing disclosures: seed 1 only; and protocol 18 §7.1(2): the "IG beats legacy" rule has 2 of 3 clauses met, budget-stability clause not assessable, so do not call the rule met. |
| C048 | OK | tests.csv F2 rows 7–10: Holm 0.03125 each, 8/8 positive, seed 1 bin ✓. | — |
| C049 | OK | gate_d_pixel_counts.csv: centre n = 192 +0.0174 GBM108_positive, +0.0243 40TopL; rule ≥ +0.02 on both (protocol 18 §7) not met; verdict "production n=12 stands" ✓. | — |
| C050 | OK | tests.csv PDX rows (n = 4): all negative in both arms and both scales; p_exact = min attainable = 0.125 ✓. | — |

## 13 S3PL

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C069 | OK | `section_level_results.csv` (CAC): S3PL 0.5915 vs uniform IG 0.5595, mean diff +0.0320, S3PL higher in 6/8; `s3pl_peaks` = matched count in 8/8 ✓. Seed 1 stated. | — |
| C070 | OK | Investigation 12 table: +0.0476/+0.0460/+0.0294/+0.0048 at PCC 0.3–0.6; shared m/z mean 79.4% (range 69.9–84.6%) ✓. No CSV behind the table; the doc is the cited record. | — |
| C071 | OK | `s3pl_cac_seed_rule.json`: real 0.5915/0.5907, tile-centre 0.1788/0.1531, ≥0.02 in 8/8 both seeds, outcome "supported" ✓; caveat matches the JSON caveat. | — |
| C072 | OK | `s3pl_cac_shuffle_control/decisions_20261017_local`: real−shuffled +0.0392 (4/8 ≥0.02), +0.0400 (3/8); shuffled 0.552/0.551, real 0.591; verdict "mixed" ✓; tests.csv F5 Holm 0.625/0.641 ✓. | — |
| C073 | MISMATCH | Recomputed from `code/msi/reproducibility/s3pl_e100/seed1_released/results/baselines/s3pl/*/metrics.json`: CAC 0.5906/0.413/0.382/**0.3348**; GBM 0.3155/0.212/0.209/0.212; epoch 10 best in 15/16, exception GBM108_positive (0.033 → 0.168/0.155/0.165) ✓. | CAC epoch-100 mean is 0.335 (0.33475), not 0.336 (protocol 18 §10 also says 0.336). The cited `training_curves_s3pl.csv` holds last-batch loss only, not mSCF1: cite the `s3pl_e100/seed1_released` metrics. Add "S3PL seed 1, S3PL in-job evaluator". |
| C074 | OK | Recomputed from `part_b/sections.csv`: seed-level collection means GBM 0.3193 ± 0.0419 (0.2260–0.3735), CAC 0.5470 ± 0.0377 (0.4960–0.5910); published 0.496/0.601; summary labels "outside our seed distribution", "not explained by seed selection alone" (best-of-10 expectation 0.434 and 0.600) ✓; short list (CAC 240TopL seed 7, 256/257) ✓; evaluator stated ✓. | — |
| C075 | LABEL WRONG | `part_d`: TIC 0.3028 vs released 0.3241, −0.0213, 5 up/3 down, p = 0.742, HL −0.0118 [−0.154, 0.099], r = −0.167 ✓; label equals `label_with_disclosure` ✓. | Missing evaluator disclosure: "S3PL in-job mSCF1 (metrics.json), not the fair-scoring evaluator" (part_d/summary.json); these values sit beside the published 0.496. Also state seeds 1–3. |
| C076 | OK | `part_c`: init/order SD 0.2220/0.00056, 0.2264/0.1463, 0.1278/0.0103; init ≥2× order 2/3; repeats bit-identical 3/3; labels "initialisation dominant", "not dominated by nondeterminism" ✓. | Suggest adding the summary's own disclosure: the nondeterminism aggregation "≥ 2 of 3 sections" is Code's reading (§6.7 does not specify); and "S3PL in-job mSCF1". |
| C077 | OK | `part_c` init scores: GBM108_positive 0.023–0.448; GBM12_2 0.272–0.519; GBM108_negative order outcomes 0.357/0.414 vs 0.647–0.654; ratio 0.2264/0.1463 = 1.55 ✓. | — |

## 14 RCC

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C078 | LABEL WRONG | rcc/…1017 `mean_mSCF1_bin` centre/uniform: IG 0.412/0.410, posterior 0.568/0.596, Moran 0.631/0.635, oracle 0.756/0.755, random 0.171/0.173 ✓; verdicts "mixed / not resolved…" (fall-through) and "incomplete; no verdict (7/8 runs)" ✓; verdict scale "bin level only" ✓. | Caveats lack the required RCC disclosures carried in the decisions JSON: the NA caveat ("unannotated class, 45–78% of pixels; the dataset's own Cardinal workflow treats these pixels as background (`rcc_nobg`), but this was not independently verified") and "GMM K = 3 equals the number of label classes: label-free in training and ranking, class-informed in its component count". Centre label should use the §7.1 wording. |
| C079 | OK | `paired_differences.csv`: centre −0.156 (8, 0 positive), uniform −0.185 (7, 0 positive) ✓; `mixed_models.csv` RCC centre −0.1437 [−0.1722, −0.1152], n_obs 46 ✓. | Suggest: the mixed model is flagged singular/boundary (`singular_or_boundary` True) and RCC uniform did not converge; give the full NA caveat rather than only "(C082)". |
| C080 | OK | Protocol 18 §10: S3PL-RCC 69529 seed means 0.441/0.427/0.406 vs published 0.470 ✓; legacy 8/8 mean 0.157 vs 0.159 (dump rounds to 0.16), count not reached 6/8 ✓. | Write 0.159 (published value), not 0.16. |
| C081 | LABEL WRONG | tests.csv row 13: RCC uniform−centre n = 6, +0.0256, 5/6 positive, Holm 0.75 ✓; Test R section table (bin): Moran − posterior +0.039 to +0.108 across seed×arm, positive in all six ✓. | Missing NA caveat and the K = 3 class-informed disclosure (as C078). |
| C082 | MISMATCH | `rcc_cancer_normal_sensitivity/…1017`: centre IG − posterior −0.0447, IG ahead 3/8 ✓; centre posterior 0.380 < mean intensity 0.397, variance 0.444, Moran 0.443 ✓. | True for `central_only` only; the statement gives no arm. In `uniform_mean` (7 runs) IG − posterior is −0.077 with IG ahead 1/7, and posterior 0.427 is **above** mean intensity 0.414 (below variance 0.444 and Moran 0.439). Name the arm and give both. |
| C083 | MISMATCH | `gate_d_bic_rcc`: `bic_selected_k` = 6 in 15/15 summaries (8 central_only, 7 uniform_mean; UH0505_12 uniform not done); bin spacing (1000−150)/10200 = 0.0833 Da ✓; 1016 vs 1017 tables flagged ✓. | "8/8" should read "15/15 run-arms (8/8 central_only, 7/7 uniform_mean; UH0505_12 uniform_mean not done)". Use the BIC wording rule from CLAUDE.md ("does not support the production K; selects the largest candidate, with no minimum within the predeclared range; descriptive only"). |

## 08 Reproductions

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C039 | OK | `aggregate_method_results.csv` tuned legacy GBM 0.4142, CAC 0.4024 ✓; Investigation 19 line 42 published msiPL GBM 0.403, CAC 0.431, RCC 0.159 ✓; protocol 18 §10 RCC legacy 8/8 mean 0.157, count not reached 6/8 ✓. | Write the published RCC value as 0.159, not 0.16. Add "native msiPL evaluator, counts tuned toward the released target, not the fair-scoring budget" for GBM/CAC too. |
| C040 | LABEL WRONG | `part_b` CAC: 0.5470 ± 0.0377, 0.4960–0.5910; section seed SD median 0.0456 (0.0346–0.2094) ✓; seed-1 0.5915 (`section_level_results.csv`) vs 0.601 ✓; short list disclosed; evaluator stated ✓. | Numbers OK, but "close to the published collection mean" with label "descriptive" omits the predeclared Part B result for CAC: `part_b/summary.json` labels CAC "outside our seed distribution" and "not explained by seed selection alone" (0.601 is above the highest seed-level mean 0.591; best-of-10 expectation 0.600). Seed 1 is close; the ten-seed distribution is not. Carry both labels (as C074) with the 2026-10-20 20:57 ruling's qualifier: the margin is within the published 2-decimal rounding (per-section mean 0.60125), so CAC is "consistent with a favourable seed or best-of-several selection, but not shown to be". |
| C041 | OK | Protocol 18 §10 (S3PL-RCC 69529): 0.441/0.427/0.406 vs 0.470 ✓. | — |
| C042 | LABEL WRONG | `part_b` GBM: 0.3193 ± 0.0419, 0.2260–0.3735, best-of-10 expectation 0.4343, labels ✓; Investigation 19/21: published above all three controlled seeds in 7/8 sections ✓. | Caveat must name the evaluator ("S3PL in-job mSCF1, not the fair-scoring evaluator") because the values are set against the published 0.496. |
| C043 | OK | Investigation 19 lines 10–12: arXiv:2603.10487v1, S3PL HEAD 660e3d9 (29 Apr 2026, v1.0.0 "paper-submission"), msiPL HEAD 1e8d5cf (11 Jul 2021) ✓. | — |

## 10 Simple baselines and metric

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C051 | NEEDS SUPERVISOR | collection_summary (seed 1, bin): GBM posterior 0.7428/0.7443, Moran 0.6840, oracle 0.8086; CAC mean intensity 0.6124, posterior 0.6064/0.6067, Moran 0.6051, variance 0.5932, oracle 0.6538; RCC (rcc/…1017) Moran 0.631/0.635, posterior 0.568/0.596, oracle 0.756/0.755 ✓. | Numbers OK, but "mean intensity is the strongest label-free ranking on CAC" holds only against the *balanced* posterior: the `posterior_abs_pcc_max` variant scores 0.6257/0.6292 on CAC, above mean intensity 0.6124 (same file). Likewise GBM uniform `hard_assignment_abs_pcc_balanced` 0.7462 > balanced 0.7443. Decide whether the statement is restricted to the predeclared primary variant (then say so) or reworded. Add "seed 1". |
| C052 | OK | `budget_sensitivity_means.csv` CAC central_only: 0.5×: Moran 0.623, mean 0.600, posterior 0.557, oracle 0.736; K_bin oracle 0.654; 2×: 0.400–0.407 for all scored methods ✓. | State the arm (central_only) and seed 1. |
| C053 | OK | `segmentation_vs_score.json`: Spearman BA vs posterior GBM 0.768, RCC 0.796, CAC 0.238; vs oracle gap −0.897, −0.843, −0.274 (n = 16/15/16 section-arms) ✓. | Give n per collection (RCC 15). |
| C054 | UNVERIFIABLE | "20–25% of IG bin-level TPs were extra bins of an already-counted peak" appears only in `results_chapter_draft.md` §4.4 prose; no saved CSV/JSON holds this fraction (partition summaries hold TP counts but not the duplicate share). P1 ordering unchanged on GBM ✓ (tests.csv P1 rows all negative). | Point to the artifact that computed 20–25%, or recompute from `with_approved_partitions/*/summary.json` before quoting it. |

## 11 Spatial context

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C055 | LABEL WRONG | `section_level_results.csv` seed 1 uniform−centre IG: CAC +0.0310, 8/8; GBM −0.0067, 5/8 ✓. tests.csv row 12: CAC 3-seed +0.0226 bin / +0.0268 P1, 8/8 ✓; row 11: GBM 7 sections +0.0002 ✓. | Protocol 18 §10 (Test R Decision 2): "GBM incomplete (7/8) (seed-1 'equivalent' superseded)". The GBM seed-1 "equivalent" must be marked SUPERSEDED, not listed as a current label. Per the reporting rule, put the §6.6 statistics beside CAC "helps": Holm 0.133 (bin) / 0.125 (P1), not statistically supported. |
| C056 | OK | Investigation 14 line 12: CAC 0.5419/0.5352/0.5235/0.5425; GBM 0.4460/0.4334/0.4594/0.4430; seven confirmation sections ✓. Caveat discloses seed 1, older GBM counts. | — |
| C057 | OK | tests.csv rows 24–27: GBM p7 −0.0351 (2/8) / P1 −0.0317 (2/8); p9 −0.0348 (2/8) / −0.0340 (2/8); CAC p7 −0.0065 / P1 −0.0184 (1/8); p9 −0.0067 / −0.0052 ✓. p5 (protocol 18 §10): GBM −0.018, CAC −0.006 ✓. Required wording present. | — |
| C058 | OK | tests.csv row 14/15: GBM +0.0105, 6/8 (P1 +0.0103, 6/8); CAC −0.0059, 4/8 (P1 −0.0054, 2/8) ✓; label "equivalent" ✓. | Add "seed 1" and the P1 values. |
| C059 | MISMATCH | Investigation 13 line 22 (64-centre audit): real half-L1 0.0027–0.0046 (160TopL) and 0.021–0.023 (GBM22_2); shuffled 0.309–0.315 and 0.185–0.197. Entropy 0.98–0.999 and masked 0.998–0.999 ✓; real neighbour–centre median cosine 0.984 (`spatial_attention_context_shift/160TopL`) ✓. | The quoted ranges mix two audits: real 0.003–0.028 and shuffled 0.16–0.32 include the boundary-audit values (0.028 GBM boundary, 0.161 GBM interior; C238). Use real 0.003–0.023 vs shuffled 0.185–0.315 for the typical-pixel audit, or cite both audits separately. |
| C060 | OK | tests.csv row 16: G1−attention GBM −0.0392 / −0.0402, 1/8 positive ✓; rows 17–19: CAC and G1 vs G2 within ±0.02 ✓; G3 (protocol 18 §10): +0.021 160TopL, −0.011 GBM22_2 ✓. | — |
| C061 | OK | Recomputed from `spatial_attention_input_swap/*/summary.json`: MSE ratio 1.36–3.38, >1 in 16/16; mean label flips CAC 4.27%, GBM 8.48% ✓; frozen ranking swap CAC mean +0.0049 ✓ (GBM +0.0183 per Investigation 13). | Add "seed 1, frozen same-checkpoint". |
| C062 | OK | `spatial_attention_context_shift`: below real 5th pct 81.05% (160TopL), half-L1 above 95th 92.0% ✓ (GBM22_2 66.2%/70.9% per Investigation 13); `spatial_attention_shuffle_topology` Jaccard means 0.2398–0.2405 ✓. | Unverified by supervisor (as flagged). |
| C063 | LABEL WRONG | `spatial_segmentation_S/decisions_20261017_local`: all six means and sign counts ✓; verdicts equivalent ×4, "mixed (does not meet the 'helps' rule)", "incomplete; no verdict (7/8 sections)" ✓. | Use the exact label for GBM uniform_mean: "does not meet the 'helps' rule (labelled mixed); +0.029, 3/8 positive, median 0.000" (the mean is driven by two sections). Add the RCC NA caveat and K = 3 class-informed note carried in the decisions JSON. |
| C236 | OK | `spatial_ig_component_ablation`: 160TopL 0.4662/0.4593/0.4507 at K = 210; GBM22_2 0.4364/0.4306/0.4252 at K = 464 ✓. | K = 464 for GBM22_2 is the older outcome-known budget, not production K_bin 1028; say so. |
| C237 | OK | `spatial_attention_uniform_weight_ablation`: +0.0099 (160TopL), +0.0038 (GBM22_2); matched overlap 202/210 and 452/464 ✓. | Same K = 464 note as C236. |
| C238 | OK | Investigation 13 line 24: CAC boundary 0.011–0.014 vs interior 0.003–0.005 (48 centres), GBM 0.020–0.028 vs 0.003–0.011 (32) ✓. Same-label percentages taken from the cited alignment summary (not recomputed). | — |

## 12 Segmentation and encoder

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C064 | MISMATCH | tests.csv rows 34–36 and `segmentation_control_V/decisions_20261017_local` (verdicts GBM "mixed", CAC "mixed", RCC "equivalent" ✓). Seed-1 values: GBM +0.0229 (5/8 positive), CAC −0.0131 (4/8), RCC +0.0145 (3/8); three-seed descriptive GBM +0.0423 (5/8), CAC −0.0118 bin / −0.0225 P1 (2/8), RCC −0.0114 (3/7) ✓. | The seed-1 differences are **VAE − PCA-5**, not "PCA−VAE": tests.csv row label is "VAE central_only posterior − PCA-5 posterior". GBM +0.023 means the VAE scored higher. Fix the direction. Add the RCC NA caveat and class-informed K = 3 (decisions JSON note). |
| C065 | OK | Test R section table (bin), VAE central_only mean GMM balanced accuracy: GBM 0.868/0.957/0.931; RCC 0.771/0.621/0.768 ✓. | RCC seed 2 is over 7 runs; give n. |
| C066 | OK | `pca_reconstruction_V/summary_local/section_table.csv`: PCA-5 MSE below VAE central_only in 8/8 GBM, above in 7/8 CAC ✓; fixed wording matches `summary.json` ✓. | Add RCC: PCA-5 MSE above the VAE in 8/8 runs (omitted). |
| C067 | OK | `gate_d_bic.csv`: K = 6 in 4/4 section-arms, candidates K = 1–6; RCC 15/15 run-arms (C083) ✓. Wording rule followed. | Say "all 15 RCC run-arms" rather than "all RCC runs". |
| C068 | OK | `gate_d_bic.csv`: GBM108_positive 0.692/0.705 → 0.391/0.406 (−0.300/−0.299); 40TopL +0.0014/−0.0208 ✓; label ✓. | — |
| C223 | OK | `spatial_latent_separability`: GBM22_2 real GMM class ARI 0.165, probe BA 0.985; 160TopL ARI 0.474, probe 0.752 ✓ (shuffled-arm values taken from the Results Record, not recomputed). | — |
| C224 | OK | `spatial_unsupervised_clusterers/GBM22_2.json`: tied-covariance ARI 0.899 vs saved full 0.165 ✓. | — |

## 06 Design and statistics

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C021 | OK | 8 + 8 + 8 sections/runs (decision tables) ✓; class-informed K and budgets disclosed. | — |
| C022 | OK | Protocol 18 §6.1 item D (CLAUDE.md summary): both arms, all 8 runs, seed 1, 100 epochs, 8 subjects ✓. | Give the NA caveat in full, not only by reference to C082. |
| C023 | OK | Protocol 18 §7: ≥ +0.02 mean and > 0 in ≥ 6/8 at bin level and under every approved partition; equivalent ±0.02; §7.1 no new category ✓. | — |
| C024 | OK | Required wording matches §7.1(1) verbatim; seed-1 bin 0/8 in four GBM/CAC arms, RCC 0/8 and 0/7 ✓. | — |
| C025 | OK | Protocol 18 §6.3: 96 trainings ✓. Test R section table, IG missing: RCC UH0505_12 (centre s2, uniform s1), RCC UH9912_01 (uniform s3), GBM39_2 (uniform s3) ✓. Reporting rule matches CLAUDE.md ✓. | — |
| C026 | OK | tests.csv/summary.json: 38 rule rows; F1 6, F2 4, F3 17, F4 9, F5 2 ✓; methods match §6.6 ✓. | — |
| C027 | MISMATCH | summary.json families: min p 0.0078125 at n = 8 ✓; PDX 0.125 ✓; F3 bin k = 17 and F4 bin k = 9 not attainable ✓. | The caveat holds for the primary (bin) families only. Holm is applied separately by scale, and F4 at P1 has k = 6 (attainable): row 30 (CAC central_only S1 − plain, P1) has Holm p = 0.047. It is not "statistically supported" only because its practical label is "equivalent" (§6.6 rule). Reword: "F3 (bin k = 17, P1 k = 16) and F4 bin (k = 9) cannot attain…; F4 P1 (k = 6) can". |
| C028 | OK | §6.6 units: seed mean within section; GBM PDX n = 4 outside Holm; CAC one biopsy; RCC 8 subjects ✓. | — |
| C029 | OK | `mixed_models.csv`: CAC both arms and RCC uniform "not converged"; GBM centre −0.2445 [−0.2731, −0.2159]; RCC centre −0.1437 [−0.1722, −0.1152]; boundary flags present ✓. | — |
| C030 | OK | `mann_whitney.csv`: one row, item 3 "not done", reason as stated; IG vs L2 not substituted (chat 10:46 Q6) ✓. | "0 result rows" = 0 test rows (the file holds one not-done row). |

## 07 Computational

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C031 | OK | Investigation 10 lines 135–136: 40,178.6 → 1,309.0 s (30.69×), 40,608.9 → 1,355.4 s (29.96×), cache 14.17/12.80 s; ratios recomputed ✓. | — |
| C032 | OK | Investigation 10: eight-batch mean 24.580 → 0.721 s; transfer 0.163, forward 0.0018, loss 0.0085, backward 0.0126 s ✓. | — |
| C033 | OK | `runtime_all_sections_v2.csv` (cached loader) medians: GBM VAE centre 31.72/34.00, uniform 32.48/34.63 min (seeds 2/3); S3PL 13.70; CAC 1.31–1.34 / 1.37–1.39 vs 0.93–0.95; RCC 2.18–2.22 vs 1.62–1.67 ✓. | Say "seeds 2–3" for the GBM/CAC VAE times: seed-1 GBM/CAC VAE runs used the streaming loader and are not in the cached medians. |
| C034 | OK | Investigation 16 table (jobs 65630/65854/65855) and memory text ✓. | — |
| C035 | MISMATCH | Recomputed medians from `ranking_stage_runtime/*/*/summary.json` (GBM/CAC, 8 each): posterior 1.12/0.028, Moran 8.39/0.18, mean 0.10/0.003, oracle 1.50/0.08, IG 770/6.0 ✓. | RCC values (0.12/0.80/0.014/0.27/417) are the 7-run table written before the UH0710_33 retry. The saved 8-run artifact `ranking_stage_runtime_rcc_bigbatch_shared` gives posterior 0.11, Moran 0.75, mean 0.013, oracle 0.25 (0.255), IG 372 s (the 7-run subset reproduces the old values exactly). Hash check 28/28 comparable rankings identical ✓ (UH0505_12 has no saved ranking). CLAUDE.md records the RCC timing as 8/8. |
| C036 | OK | Investigation 10 (cached audits exact in losses and final state, both arms); `part_c` repeats bit-identical 3/3, repeat SD 0 ✓. | — |
| C037 | OK | Protocol 18 §10 line 1221: chunk 2 (72190) 6 FAILED with `FileExistsError` on shared folders, then targeted retries ✓; other lessons match CLAUDE.md ✓. | — |
| C038 | OK | CLAUDE.md cluster Python 3.11.5, NumPy 2.4.6, sklearn 1.9.0 ✓; chat: `test_statistics_6_6` 14/14 ✓. | — |

## 04 Data

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C001 | MISMATCH | 8 sections, PDX lines 108/12/22/39, 2 per line ✓ (tests.csv `sections_per_line`). | "The inferential unit is the PDX line" contradicts protocol 18 §6.6 and C028: the Holm-family tests use the 8 sections (seed-averaged); PDX-line tests (n = 4, min p 0.125) are reported **beside** them, outside Holm. Reword: "sections are not independent; PDX-line summaries (n = 4) are reported beside every GBM test". |
| C002 | OK | §6.6: CAC one biopsy, within-specimen ✓. | — |
| C003 | OK | `results/validation/rcc_feasibility/export_report.json`: 8 runs, 972–3,564 pixels, 10,200 bins, m/z 150.08–1000, unannotated 45.4–77.5% ✓; caveats match the 16 Oct 18:34 ruling ✓. | — |
| C004 | OK | CLAUDE.md and protocol 18: GBM108_positive, GBM22_2, 160TopL, 40TopL ✓. | — |
| C005 | OK | `model.py` latent_dim = 5; S3PL runs: 10 epochs, z = 256, GBM patch 3, CAC patch 9 (run folder names) ✓; part D compares `reference_spatial_max` vs `paper_tic` ✓. | — |
| C006 | OK | `budget_sensitivity_means.csv` multipliers 0.5/0.75/1/1.5/2 ✓; RCC released-target budget per CLAUDE.md/§6.1 ✓; superseded |R@0.4| flagged ✓. | — |
| C007 | OK | SUPERSEDED status and replacement C006 stated ✓. | — |
| C008 | OK | Test S decisions note "CAC P1 is singleton groups (1,481 for 1,481 bins)" ✓; RCC spacing 0.0833 Da ✓; RCC P1 = budget sensitivity (§6.1 amendment) ✓. | — |
| C009 | OK | `gate_d_bic.csv` production K 2 (GBM), 3 (CAC); RCC BIC summaries production_k 3 ✓. | — |
| C221 | OK | Protocol 18 §0: GBM 8/8 equal at PCC 0.4; CAC matches none of four thresholds; tolerance 50 ✓; "do not call CAC targets mask-derived" ✓. | — |
| C222 | OK | `gbm_imzml_h5/comparison.json`: coordinate sets equal 8/8; masks not byte-exact but every measured label maps official 1→0, 2→1 in 8/8 (semantic match) ✓; 03 Datasets: 280TopL 4,160 spectra, 89.98% ✓. | — |
| C234 | OK | `references.md` line 85/93: CAC original citation still "Verify" ✓. | — |

## 05 Methods and models

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C010 | OK | `model.py` latent_dim 5; 100 epochs (production script default/runtime CSV) ✓. | — |
| C011 | OK | Investigation 11 line 17: D = 85,062; 87,199,312 (centre) and 130,751,056 (uniform); hidden 512, latent 5 ✓. | Mark "not supervisor-verified" as stated. |
| C012 | OK | +680,504 = 8 × 85,062 + 8 and +11,856 = 8 × 1,481 + 8 (one score weight per bin per neighbour slot + bias); ≈0.52% of the uniform VAE in both collections ✓. 50% masking and G3 n = 2 per §6.1 G ✓. | — |
| C013 | OK | `attribution.py` steps = 64; production 12 pixels/component; gate (d) 48/192 (`gate_d_pixel_counts.csv`) ✓. | — |
| C014 | OK | Protocol 18 §4 description; paired GMM and K_bin ✓. | — |
| C015 | OK | `fair_scoring_bin_level_sections.csv` holds all listed rankings at K_bin ✓. | — |
| C016 | OK | Test S decisions: 6 collection-arms, 24 sections/runs, seed 1 ✓. | — |
| C017 | OK | Test V section table has PCA-5 primary and PCA-20 columns for all 24 ✓. | — |
| C018 | OK | Investigation 11 line 16–17: 470 parameters at p = 3, Adam 1e-2, batch 16, 10 epochs; metrics JSON lr 0.01, batch 16 ✓. | — |
| C019 | OK | Legacy `msiPL_Run.py`: intermediate 512, latent 5, 100 epochs ✓. | The cited 87,199,312 (Investigation 11) is our centre-only VAE; legacy msiPL has the same dense 512/5 architecture, hence "about 87 million". Say so, or cite `Computational_Model.py`. |
| C020 | OK | PCC thresholds 0.3–0.6 (Investigation 12 table; partition summaries) ✓; bounded wording ✓. | — |
| C225 | OK | `attribution.py` lines 51–108: `steps` = 64 trapezoidal intervals, `steps + 1` points including both endpoints, endpoint weights 0.5 ✓. | Wording: "64 intervals (65 evaluation points, both endpoints included)"; the dump's "64 intervals including both endpoints" conflates the two. |
| C226 | OK | Protocol 18 §3.3: "nearest-threshold rank rule per class, then the union" ✓. | — |
| C227 | OK | Protocol 18 §3.1–3.2: 50 ppm hard break; merge if relative depth < 0.05 and merged width ≤ 100 ppm; S1 max width < 0.5 Da, only rejection rule; S2 descriptive, S3 informational; apex rule ✓. | — |

## 15 Discussion points

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C084 | OK | 3 datasets, 24 sections/runs ✓; framing per chat 2026-10-20 10:25. | — |
| C085 | OK | 47/47 (C044) and 136/140 (C045) ✓. | Say "bin level" for 136/140. |
| C086 | OK | Test S never "helps" (C063); Test N +0.039/+0.040 "mixed" (C072); Moran's I highest label-free ranking on RCC in both arms, seed 1 (0.631/0.635) ✓. | — |
| C087 | OK | Same as C066 ✓. | Add RCC (PCA-5 MSE higher in 8/8). |
| C088 | OK | `segmentation_vs_score.json` −0.897 GBM, −0.843 RCC ✓. | — |
| C089 | OK | K = 2/3/3 (C009); BIC K = 6 (C067, C083) ✓. | Prefer the BIC wording rule ("largest candidate, no minimum within the predeclared range") over "boundary K = 6". |
| C090 | OK | §6.6 units ✓. | — |
| C091 | MISMATCH | Same source as C082: centre-only arm IG−posterior −0.0447, posterior ahead 5/8 ✓; unannotated 45–78% ✓. | As C082: true for `central_only` only. In `uniform_mean` (7 runs) posterior is ahead 6/7, gap −0.077, and mean intensity does not lead (0.414 < posterior 0.427). Name the arm. |
| C092 | OK | `meeting_walkthrough.md` line 51: 10-epoch VAE endpoint not scored; S3PL scored at 10/25/50/100 ✓. | — |
| C093 | OK | `gate_d_pixel_counts.csv`: +0.0174 GBM108_positive, +0.0243 40TopL ✓. | Name the sections (development sections, not collections). |
| C094 | OK | `part_b`/`part_c` values as in C074/C076 ✓. | Add "S3PL in-job evaluator" (as C042). |
| C228 | OK | Protocol 18 line 110 "Stated asymmetry" ✓; IG 12 pixels/component, 64 intervals ✓. | — |

## 16 Conclusion and future work

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C203 | OK | Chat 2026-10-20 11:31: F1 "statistically supported" in all 6 bin-level comparisons, Holm ≤ 0.047 ✓; 47/47 and 136/140 ✓. | Add "at bin level" and the ruling's companion statement that CAC uniform P1 is not supported (p = 0.078, 7/8). |
| C204 | OK | Attention "equivalent" (C058), p7/p9 not "helps" (C057), Test S never "helps" (C063), Test N "mixed" (C072) ✓. | — |
| C205 | OK | Test V verdicts (C064) ✓. | — |
| C206 | MISMATCH | GBM 0.3193 ± 0.0419 vs 0.496, "outside our seed distribution" ✓. | "S3PL is close on CAC/RCC but its GBM result remains outside the ten-seed distribution" implies CAC is inside. `part_b/summary.json` labels CAC "outside our seed distribution" too (0.601 vs max seed mean 0.591). Use the 20:57 ruling: CAC is just outside, within the published rounding, consistent with but not shown to be seed selection; GBM is far outside. (The chat entry gives GBM as 0.3194; the artifact value 0.31934 rounds to 0.3193, so the dump is right.) |
| C207 | OK | K = 2/3/3; 4 PDX lines, 1 biopsy, 8 subjects ✓. Future work, no evidence claim. | — |
| C208 | OK | Path exists; future-work list matches Investigation 20 scope. Not a numerical claim. | — |

## 19 Dropped and negative

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C095 | OK | CAC +0.031, GBM −0.007 (C055); shuffled ties real (C056); Test S (C063) ✓. | — |
| C096 | OK | collection_summary: IG below posterior 47/47 (C044); mean intensity 0.483 vs legacy 0.414 (GBM), 0.612 vs 0.402 (CAC) ✓. | Add "seed 1, bin level". |
| C097 | OK | C034 (VAE faster on 160TopL repeats) and C033 (S3PL faster on collection medians) ✓. | Source line cites `11 S3PL …` and `14 Primary …` without the `docs/research/investigations/` prefix; give full paths. |
| C098 | OK | Test N: +0.039/+0.040, 4/8 and 3/8 ≥ 0.02, "mixed" ✓. | — |
| C099 | OK | Test V verdicts ✓. | — |
| C100 | OK | K = 2/3/3; budgets from released targets/legacy tuning (§0) ✓. | — |
| C101 | OK | Both `rcc/decisions_20261016_local` and `…20261017_local` exist; CLAUDE.md: "tables in decisions_20261017_local (the 16 Oct ones superseded; verdicts unchanged)" ✓. SUPERSEDED flagged with replacement. | — |
| C102 | OK | SUPERSEDED |R@0.4| with replacement C006 ✓. | — |
| C103 | OK | 8/8 legacy wins in four arms; IG below posterior in 32/32 GBM/CAC seed-1 section-arms ✓; README note dated 15 October ✓. SUPERSEDED IN PART flagged. | — |
| C104 | MISMATCH | Same evidence as C083/C067. | "8/8 RCC runs" → "15/15 RCC run-arms (UH0505_12 uniform_mean not done)". Use "largest candidate" rather than "the boundary". |
| C105 | OK | `gate_d_pixel_counts.csv` +0.0174/+0.0243 ✓. | — |
| C106 | OK | `mann_whitney.csv` "not done"; C3 not run (CLAUDE.md, accepted 15 Oct); 4 Test R seed-arms missing (C025); RCC uniform seed-1 "incomplete; no verdict (7/8 runs)" ✓. | — |
| C229 | OK | Protocol 18 §5: matched-K re-rank "Not implemented in this round" ✓. | — |
| C230 | OK | `previous_version/sections/results.tex` lines 6, 34, 53–54: 0.414 and 0.3643/0.4562 both present (historical CONFLICT as described) ✓; replacement 0.4142/0.5111 from `aggregate_method_results.csv` ✓. SUPERSEDED flagged. | — |

## 03 Problem, research questions and proposal-to-outcome

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C191 | OK | `proposal/proposal.tex` line 381 (RQ1) paraphrased faithfully; 8-pixel Moore neighbourhood (proposal_to_outcome row 1) ✓. | Quote verbatim if presented as the original RQ. |
| C192 | OK | Line 382 (RQ2); proposal_to_outcome rows 2–3: λ = 0, 0.01, 0.1, 1; noisy-input gain about 0.022% vs ≥ 1% gate ✓. | The paraphrase "isolate spatial signals" differs from the original "isolate true biomolecular signals from stochastic matrix noise"; quote verbatim. |
| C193 | OK | Line 383 (RQ3) ✓; legacy beaten 8/8 in all four arms (C047) ✓. | — |
| C194 | OK | Framing per chat 2026-10-20 10:25 (not re-read in full). | — |
| C195 | OK | proposal_to_outcome row 2 ✓. | — |
| C196 | OK | Row 3: ≥ 1% gate, observed ≈ 0.022% ✓. | — |
| C197 | OK | Row 5 cited; consistent with rows 2–3 (no formulation passed). | — |
| C198 | OK | Row 6: "0.21 vs 0.46 mSCF1 on GBM (20 Sep)"; "Replaced (12 Sep decision)" ✓. | The early 0.46 is the older-count pipeline value (cf. C230), not today's 0.518; label it "early (September) comparison". |
| C199 | OK | Row 8: msiPL and S3PL on 3 datasets, MALDIquant omitted, simple baselines/random/oracle added ✓. | — |
| C200 | OK | Row 9: GBM 2-section imzML pilot, CAC adapters, RCC added 16 Oct ✓ (also C222). | — |
| C201 | OK | 4 thresholds, 5 multipliers (C006), 38 comparisons (C026) ✓. | — |
| C202 | OK | Test V 24 (C017), Test R 96 (C025), Test N 8 sections × 2 seeds = 16 ✓. | — |

## 17 Figures and tables inventory

Figure items were checked for path existence, the numbers in their entries, and the caption status (rebuild or SUPERSEDED). Image content was not inspected.

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C107 | OK | Path exists; 40,609 → 1,355 s, 29.96× (C031) ✓. | — |
| C108 | OK | Path exists; 7 confirmation sections, seed 1, older GBM budgets (C056) ✓. | — |
| C109 | OK | Path exists; rebuild to mean ± SD flagged ✓. | — |
| C110 | OK | PNG and `03_s3pl_cac_controls.csv` both exist (the source line writes the CSV as `.csv` only; the path checker flags it). Rebuild for Test N flagged ✓. | Write the full CSV path. |
| C111 | OK | Path exists; rebuild with seed mean ± SD and RCC n flagged ✓. | Rebuilt caption must carry the RCC NA caveat and the RCC uniform "incomplete; no verdict". |
| C112 | OK | Path exists; rebuild flagged ✓. | — |
| C113 | OK | Path exists; 2 × 2 × 3 matches `gate_d_pixel_counts.csv` (12 rows) ✓. | — |
| C114 | OK | Path exists. | — |
| C115 | OK | Path exists; 4 × 2 ✓. Curation note (check seed rule) applies. | — |
| C116 | OK | Path exists; 16 sections (C061) ✓. | — |
| C117 | OK | Path exists. | — |
| C118 | OK | Path exists; 512 centres per section (Investigation 13 line 19) ✓. | — |
| C119 | OK | Path exists; thresholds 0.3–0.6 (C070) ✓. | — |
| C120 | OK | Path exists; 79% (C070) ✓. | — |
| C121 | OK | Path exists; SUPERSEDED for the primary seed distribution, flagged ✓. Replaced by the new Investigation 21 figure built below. | — |
| C122 | OK | Path exists; 3 repeats (C034) ✓. | — |
| C123 | OK | Path exists; K = 1–6, 4 section-arms ✓; wording rule in caveat ✓. | — |
| C124 | OK | Path exists; seed-1 caveat ✓. | — |
| C125 | OK | Path exists; 15/16 (C073) ✓. | Caption must use CAC epoch-100 mean 0.335 (C073). |
| C126 | OK | Path exists; 4 equivalent / 1 mixed / 1 incomplete (C063) ✓. | Caption: GBM uniform as "does not meet the 'helps' rule (labelled mixed)" (C063). |
| C127 | OK | Path exists; rebuild for ten seeds flagged ✓. | Rebuilt caption must not imply CAC is inside the seed distribution (C040/C206). |
| C128 | OK | Both paths exist. | — |
| C129 | OK | Path exists; 47 section-arms (`segmentation_vs_score.json`) ✓. | — |
| C130 | OK | Path exists; labels match Test V ✓. | Check the plotted direction: tests.csv defines the difference as VAE − PCA-5 (C064). |
| C131 | OK | Path exists; "mixed", 8 × 2 ✓. | — |
| C132 | OK | All six PNGs exist in `current_evidence/`; SUPERSEDED IN PART flagged ✓. | — |
| C133 | OK | Row counts: bin-level 32 ✓ (partition 48, collection summary 44, not stated). | — |
| C134 | OK | All four CSVs exist; v1 SUPERSEDED by v2 ✓; S3PL last-batch MSE ✓. | `training_curves_s3pl.csv` holds loss only, so it cannot be the source for C073's mSCF1 values. |
| C135 | OK | All four files exist ✓. | — |
| C136 | OK | `aggregate_method_results.csv` 6 rows ✓. | — |
| C137 | OK | 38 rule rows, 9 mixed models, Mann–Whitney "not done" ✓. | — |
| C138 | OK | Both cited docs exist. | — |
| C139 | OK | Path exists; last-batch MSE caveat ✓. | — |
| C140 | OK | Both paths exist; check-before-reuse caveat ✓. | — |
| C231 | OK | All cited `.tex` panels exist. | — |
| C232 | OK | Cited PNGs exist (`results/datasets/…`, `gbm_imzml_comparison/…`). | — |
| C233 | OK | Results Record table: uniform-mean MSE lower in 4/8 (GBM108_negative, GBM12_1, GBM22_1, GBM22_2), higher in 4/8 ✓. | — |

## 18 Appendix candidates

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C209 | OK | VAE 3 seeds (Test R), S3PL 10 released seeds GBM/CAC (part_b), Test N 2 seeds ✓. | — |
| C210 | OK | Family sizes 6/4/17/9/2 = 38 (summary.json) ✓. | — |
| C211 | OK | 8 sections per collection, 4 PDX lines; patient table path exists ✓. | — |
| C212 | MISMATCH | Dump count recomputed: 238 items (C001–C238), not 220. | "220 dump items when complete" → 238. |
| C213 | OK | `proposal_to_outcome.md` has 14 numbered rows ✓. | — |
| C214 | OK | Cross-references resolve to existing items. | — |

## 20 Process, AI use and reproducibility

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C215 | OK | Chat "How this works" + CLAUDE.md append-only rule (from 17 Oct) ✓. | Note that entries before 17 Oct 09:28 may show edited status lines (CLAUDE.md); "earlier entries are not rewritten" holds from that date. |
| C216 | OK | Chat 2026-10-20 (line 3723): fresh Section 6.6 run reproduced `tests.csv`, `mann_whitney.csv`, `mixed_models.csv`, `summary.json` byte for byte (4/4) ✓; fail-closed stale outputs (exit 3) per CLAUDE.md ✓. | "Numerous decision tables" is unquantified; give a count or drop. |
| C217 | OK | Chat 2026-10-21 10:52: job 72625 main suite 259 tests OK, 3 skipped; S3PL 25 OK; seed-flag 4 OK ✓; 6.6 14/14 ✓. | Name the job (72625); the first attempt 72595 failed on a test-code bug, which the record keeps. |
| C218 | UNVERIFIABLE | Process statement; both declaration PDFs exist. No artifact records which tools did which tasks. | Zayd must confirm tools and roles before this becomes declaration text. |
| C219 | UNVERIFIABLE | Process statement; no public repository/archive URL exists to check. | — |
| C220 | OK | C036 (cached VAE exact 2 arms; S3PL 3/3 on RTX 3090) and C035 (RCC 28/28 comparable rankings) ✓. | — |
| C235 | OK | `pdftotext` of the RP form: tool list, purposes (tick boxes) and the methodology-chapter clause for "integral part of the experimental design or … direct execution" ✓. | — |

## 01 Introduction and motivation

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C141 | MISMATCH | Bins: GBM 85,062, RCC 10,200, CAC 1,481; measured pixels per section/run about 1,000–4,800 (RCC 972–3,564; CAC 280TopL 4,160). | "Tens of thousands of spectral bins" is true for GBM only (RCC ≈10k, CAC 1,481), and RCC UH0710_33 has 972 pixels. Reword: "about a thousand to several thousand locations and 1,481–85,062 spectral bins, depending on the dataset". |
| C142 | UNVERIFIABLE | Conceptual motivation; no project number. Needs literature citations (02). | — |
| C143 | OK | msiPL and S3PL reproduced on 3 datasets (C039–C041) ✓. | — |
| C144 | OK | Proposal RQ1 and proposal_to_outcome row 1 (8-pixel Moore neighbourhood) ✓. | — |
| C145 | OK | 47/47 and 136/140 ✓. | "136/140 at bin level". |
| C146 | OK | 3 datasets, 24 sections/runs, 38 comparisons ✓. | — |

## 02 Background and related work

Literature items were checked for internal consistency only: the bib key exists in `report/draft/references.bib`, and the year, venue, volume/pages and DOI in the item match the bib entry or the `docs/meetings/references.md` tracker. Publisher records were not checked online.

| ID | Status | What was checked | Correction |
|---|---|---|---|
| C147 | OK | Bib `abdelmoula2021peak` present; year/venue consistent ✓. | — |
| C148 | OK | Bib `weigand2026spatial` (arXiv:2603.10487, 2026) ✓; Investigation 19: v1 only, no public supplement ✓. | — |
| C149 | OK | Bib `weigand2026ionmorphnet` (arXiv:2604.19369) ✓; Investigation 19 line 13: HEAD 640406a ✓. | — |
| C150 | OK | Bib `abdelmoula2022massnet` present; year/venue consistent ✓. | — |
| C151 | OK | Bib `sundararajan2017axiomatic` present; year/venue consistent with "ICML 2017." ✓. | — |
| C152 | OK | Bib `kingma2014autoencoding` present; year/venue consistent with "ICLR 2014." ✓. | — |
| C153 | OK | Not in `references.bib`; "J. Proteome Res. 9(12):6535–6546; doi:10.1021/pr100734z." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C154 | OK | Not in `references.bib`; "Bioinformatics 27(13):i230–i238." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C155 | OK | Not in `references.bib`; "Mol. Cell. Proteomics 15(5):1761–1772; doi:10.1074/mcp.O115.053918." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C156 | OK | Not in `references.bib`; "Bioinformatics 2015." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C157 | OK | Not in `references.bib`; "Biometrika 1950." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C158 | OK | Not in `references.bib`; "Bioinformatics 29(18):2335–2342; doi:10.1093/bioinformatics/btt388." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C159 | OK | Bib `palmer2017fdr` present; year/venue consistent with "Nat. Methods 14:57–60." ✓. | — |
| C160 | OK | Not in `references.bib`; "Anal. Chem. 88(11):5871–5878; doi:10.1021/acs.analchem.6b00672." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C161 | OK | Not in `references.bib`; "SIS 2023 short papers, pp.1127–1132." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C162 | OK | Not in `references.bib`; "Nat. Commun. 13:1739." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C163 | OK | Not in `references.bib`; "Nat. Methods 18:1342–1351; doi:10.1038/s41592-021-01255-8." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C164 | OK | Not in `references.bib`; "Adv. Sci. 12(8):2410840; doi:10.1002/advs.202410840." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C165 | OK | Not in `references.bib`; "Anal. Bioanal. Chem. 413(10):2803–2819." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C166 | OK | Not in `references.bib`; "Bioinformatics 39(2):btad067." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C167 | UNVERIFIABLE | Not in bib; tracker lists the bioRxiv DOI but authors are marked "verify". | Confirm authors before citing (curation proposes X). |
| C168 | NEEDS SUPERVISOR | Not in bib; silhouette 0.515/0.460/0.417/0.271 and AUC 0.874/0.820/0.789/0.768 match the tracker (Tables II–III) ✓. | Unpublished Wits report: citation form needs the supervisor's ruling (tracker says "check the citation form with the supervisor"). |
| C169 | OK | Not in `references.bib`; "Annals of Statistics 1978." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C170 | OK | Not in `references.bib`; "JMLR 2011." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C171 | OK | Not in `references.bib`; "Journal of Classification 1985." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C172 | OK | Not in `references.bib`; "NeurIPS 2017." matches the references.md tracker ✓. | Add a bib entry before citing. |
| C173 | OK | Bib `caprioli1997maldi` present; year/venue consistent ✓. | — |
| C174 | OK | Bib `schwamborn2010molecular` present; year/venue consistent ✓. | — |
| C175 | OK | Bib `buchberger2018mass` present; year/venue consistent ✓. | — |
| C176 | OK | Bib `korber2025mass` present; year/venue consistent ✓. | — |
| C177 | OK | Bib `ye2013msi` present; year/venue consistent ✓. | — |
| C178 | OK | Bib `zhang2025msi_infectious` present; year/venue consistent ✓. | — |
| C179 | OK | Bib `aspect2026msi_intro` present; year/venue consistent ✓. | — |
| C180 | OK | Bib `deininger2011normalization` present; year/venue consistent ✓. | — |
| C181 | OK | Bib `gibb2012maldiquant` present; year/venue consistent ✓. | — |
| C182 | OK | Bib `lieb2020sparse` present; year/venue consistent ✓. | — |
| C183 | OK | Bib `winderbaum2015feature` present; year/venue consistent ✓. | — |
| C184 | OK | Bib `li2022machinelearningpeakpicking` present; year/venue consistent ✓. | — |
| C185 | OK | Bib `cordes2021m2aia` present; year/venue consistent ✓. | — |
| C186 | OK | Bib `inglese2017deep` present; year/venue consistent ✓. | — |
| C187 | OK | Bib `guo2024deepion` present; year/venue consistent ✓. | — |
| C188 | OK | Bib `huber2021spec2vec` present; year/venue consistent ✓. | — |
| C189 | OK | Bib `huber2021ms2deepscore` present; year/venue consistent ✓. | — |
| C190 | OK | Not in bib; tracker entry present; 8 RCC runs used (C003) ✓. | Add a bib entry before citing. |

## Summary

238/238 items verified, each ID once: **OK 208, MISMATCH 14, LABEL WRONG 9, UNVERIFIABLE 5, NEEDS SUPERVISOR 2, PATH MISSING 0.** Every cited path exists (C110's `.csv` and C097's two short investigation names are shorthand for files that exist).

Recurring themes:
1. **Missing required disclosures:** the RCC NA caveat and class-informed K = 3 (C078, C081, C063, C064); the S3PL in-job evaluator (C042, C075); seed mode (C044, C047).
2. **CAC S3PL is also "outside our seed distribution"** (C040, C206). The 20:57 ruling qualifies it as within the published rounding.
3. **Arm-specific statements given without an arm:** the cancer/normal sensitivity holds for central_only only (C082, C091).
4. **Counts:** RCC BIC is 15/15 run-arms (C083, C104); the dump has 238 items (C212).
5. **Superseded values still quoted:** RCC ranking-stage times from the 7-run table (C035); GBM seed-1 context "equivalent" (C055).

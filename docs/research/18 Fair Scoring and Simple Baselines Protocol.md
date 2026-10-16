# Fair-scoring and simple-baseline protocol (v3.2, 9 October 2026)

Status (updated 9 October): **protocol v3.2; gates (a) and (b) complete on all 16 sections, at bin level (decision table 66097) and under the approved partitions (66238). Neither predeclared IG-versus-posterior verdict applies, because IG scored below posterior-|PCC| in every section at bin level (Sections 7.1 and 10). Gate (d) is not yet run.** No existing evidence, figure, table or report claim is replaced by anything here. This document supersedes the protocol parts of `docs/meetings/supervisor_review_2026-10-09_response_to_codex.md` wherever the two differ.

v3 incorporates Codex's operational and provenance corrections (Sections 0, 4, 8, 9 and 10). **v3.1 makes S2 descriptive rather than a rejection rule (Section 3.2).** This decision was made before any real partition-audit output existed. Every execution on real data so far is listed in Section 10.

## 0. Budget provenance: what is and is not established

Checked against our saved evaluation summaries for all 16 sections:

- **GBM.** The released S3PL constant `num_GT_peaks` (`baselines/s3pl/data_configs.py`) equals our mixed reference-set size at PCC 0.4 in **8/8** sections (581, 937, 691, 981, 845, 1014, 696, 917). This strongly suggests the constants were derived from the masks at PCC 0.4, but that derivation has not been verified from the paper or the upstream repository.
- **CAC.** The released targets (342, 199, 214, 257, 238, 246, 137, 257) match **none** of our reference sizes at any of the four thresholds. The earlier CAC reference-set audit found that S3PL's stored labels give exactly our reference sets, so the mismatch is not explained by a different S3PL reference path. Their derivation is unknown.
- **Evaluated budgets.** K_bin is the legacy msiPL `unique_nearest_bins`: Beta was tuned toward the released target with a tolerance of 50 (`tune_msipl_massnet_beta.py`; CAC targets are in `slurm_jobs/run_msipl_cac_section.sh`).

**Wording to use until the derivation is verified:**

> The bin budget K_bin is each section's legacy msiPL peak count, tuned toward the released S3PL target counts and shared by every method. On GBM those released targets equal the size of our PCC ≥ 0.4 reference set in every section, so the budget maximises the achievable F1 ceiling at PCC 0.4. On CAC the released targets do not correspond to our reference-set sizes, and their derivation is unverified. The budget-sensitivity curves test whether observed performance or method ordering depends on the budget.

Do not call the CAC targets mask-derived.

## 1. Budgets

| Symbol | Definition | Used for |
|---|---|---|
| K_bin | Existing evaluated bin count: legacy msiPL `unique_nearest_bins`, unchanged | All bin-level results, including the paper-aligned primary result |
| K_peak(P) | Number of reference **peak groups** at PCC 0.4 under approved partition P (Section 3.3) | Matched peak-level evaluation under P |

- **Collapse diagnostic:** take each method's first K_bin ranked bins and report how many distinct groups they occupy under P. The selection-side, partition-free version is rule A: runs of consecutive bin indices. Report this for every method, including legacy msiPL.
- **Matched peak-level evaluation:** walk down each ranking until it covers K_peak(P) distinct groups, then score at group level.
- **K_bin is never used as a number of peaks.**
- **Legacy msiPL has no ranking beyond its fixed list.** It is reported for the collapse diagnostic only. A K_peak-matched legacy list would need a separate Beta re-tune toward K_peak (no retraining, CPU-only); that is a follow-up and not implemented here.
- **Until that re-tune is done, IG versus legacy is not a matched peak-level comparison.** The collapse diagnostic answers a narrower question: how many distinct peaks each method's existing K_bin list covers, and how those groups score. Outputs and the decision table say so explicitly.

## 2. Bin-level results and budget sensitivity (gate a, part 1; no retraining, CPU-only)

- Bin-level mSCF1 at K_bin with the existing scorer (`score_indices`) is unchanged and remains primary.
- Before scoring anything new, the script stops unless the following reproduce:
  - **IG and L2:** the same bins as the saved lists at K_bin, in the same order except for swaps between bins with **exactly equal** scores, and their saved mSCF1 to 1e-12. (v3.2: the historical lists were built with `np.argsort(scores)[::-1]`, whose order among exact ties depends on the NumPy version and CPU sort kernel. New rankings break exact ties by lower bin index, so they are platform-independent. Any difference other than an exact-tie swap still stops the run.)
  - **Legacy msiPL:** the snapped unique-bin count equals K_bin and the saved `unique_nearest_bins`; per-threshold mixed TP, FP and FN equal the saved integers exactly; and mSCF1 agrees to 1e-12.
- **Why that tolerance:** the rescore uses the same data, rule and scorer functions that produced the saved values. Only floating-point summation order can differ, and that cannot change an integer count unless a PCC lies within about 1e-12 of a decision boundary. Any mismatch therefore stops the run, so that the scorer difference is documented rather than silently carried forward.
- **Budget sensitivity:** every ranked method is scored at round(K_bin × m) for m ∈ {0.5, 0.75, 1.0, 1.5, 2.0}. Legacy is scored at m = 1 only.
- **Reported ceiling per threshold:** the maximum attainable F1 at budget K given |R_t|, which is 2·min(K, |R_t|)/(K + |R_t|). This also bounds any `normalise_results` effect (gate c).

## 3. Peak partitions (gate a, part 2)

### 3.1 Definitions (method-independent; no masks, labels or scores)

Input for both partitions: the m/z axis and the section's mean TIC-normalised spectrum over measured pixels. A zero-TIC pixel stays zero and is included in the mean.

**P1 — mean-spectrum basins**

1. **Hard breaks.** Bin i > 0 starts a new segment if 10⁶·(mz[i] − mz[i−1])/mz[i−1] > 50 ppm.
2. **Smoothing.** Within each segment separately, apply a centred moving average of width 3 bins. The segment's end values are replicated as padding, and no smoothing crosses a hard break.
3. **Local minima.** An interior bin i of a segment (neither its first nor its last bin) is a boundary if s[i] < s[i−1] and s[i] ≤ s[i+1]. On a flat minimum this selects the first bin of the plateau. The boundary bin starts the right-hand group. Segment endpoints are never boundaries.
4. **Prominence merge.** Do a single left-to-right pass per segment. Let C be the current group and N the next, separated at boundary bin b. Let a = min(max s over C, max s over N), depth = a − s[b], and relative depth = depth/a (0 if a = 0). Merge N into C if relative depth < 0.05 **and** the merged group's width (mz[last] − mz[first])/mz[first] is ≤ 100 ppm. Otherwise finalise C and continue from N. After a merge, C's maximum is the maximum of both groups.
5. **Width cap.** The cap applies only to merges. A raw basin wider than 100 ppm is never split artificially; it is reported by the audit and judged by the sanity rules.
6. **Apex.** The bin with the largest **unsmoothed** mean intensity in the group. Ties go to the lowest index.

**P3 — 20 ppm connectivity**

A new group starts at bin i whenever the gap to bin i−1 exceeds 20 ppm. Groups are the connected chains of gaps ≤ 20 ppm, so chaining is possible by construction and is exactly what the audit must detect. The apex rule is the same as P1.

### 3.2 Structural audit (run and reviewed before any method is scored)

**Reported per section and partition:**

- bin count, group count and group/bin ratio;
- singleton fraction;
- group size in bins (median, 99th percentile, maximum);
- width in Da and ppm (median, 99th percentile, maximum);
- the 10 widest and the 10 largest groups, with their m/z ranges;
- a SHA-256 of the group assignment.

**Predeclared sanity rules.** These are structural only. mSCF1, masks and method outputs are never consulted.

| Rule | Criterion | Rationale |
|---|---|---|
| S1 | Maximum group width < 0.5 Da | A group spanning half of the ¹³C isotope spacing (1.00335 Da at z = 1) can merge distinct isotopologues or neighbouring ions |
| S2 (descriptive, **not** a rejection rule) | Report the largest group's bin count and share of all bins, plus the 99th-percentile group size | A group's bin count depends on axis resolution, not only on physical peak width: on CAC, 0.5% of the axis is about 7 bins. Chaining is guarded physically by S1. S2 values are shown for review |
| S3 (informational) | Singleton fraction > 0.95 is labelled "near bin-level" | The partition would then barely differ from bin-level scoring; it is not a failure |

**S1 is the only hard anti-chaining rule.** A partition that fails S1 in **any** section is rejected for that collection. S2 and S3 are reported alongside it, together with group bin counts, proportions and the extreme groups, but they never reject a partition by themselves. It is not tuned against outcomes. If both partitions fail, peak-level evaluation is reported as "not established" and any revision needs a new, separately predeclared rule.

**Approval.** A reviewer writes `partition_approval.json` with `status` set to `approved`, listing the approved partitions, their parameters and the per-section hashes. The scoring script refuses to run the peak-level analysis without it, refuses draft or otherwise unsigned approval files, and refuses again if any hash differs.

### 3.3 Peak-level scoring under an approved partition

- **Reference.** For each threshold t, the bin-level mixed reference set is computed exactly as now (the nearest-threshold rank rule per class, then the union). A group is reference-positive at t if **its apex bin** is in that set.
- **Prediction.** A group is selected if at least one selected bin falls in it, and it counts once.
- **Metrics.** TP, FP and FN are counted over groups, with the group count as the universe; F1 is computed per threshold, and mSCF1 is their mean.
- **Matching.** Matching is one-to-one by construction, because predictions and references share one fixed partition. No tolerance and no matching step are involved.
- **Decision use.** A claim is "robust to peak-level scoring" only if its direction holds under every approved partition.

## 4. Simple saved-artifact baselines (gate b; no retraining, CPU-only)

All label-free baselines use the **TIC-normalised** spectra, which is the representation the VAE sees. Evaluation stays on the existing raw-intensity PCC references. Each IG arm (centre-only and uniform-context) gets its own posterior baselines from its own GMM.

| Ranking | Definition | Role |
|---|---|---|
| IG (production) | Per-component \|IG\| (`component_c_combined_absolute_mean`), then balanced round-robin | Reproduced exactly |
| **Posterior \|PCC\|, balanced** | p_c is recomputed from the saved latent means and GMM parameters (checked against the saved assignments). Score s_{k,c} = \|PCC(ion_k, p_c)\| over all measured pixels; per-component order is `argsort(s)[::-1]` (the IG tie convention), then the same round-robin | **Primary isolation of IG** |
| Posterior \|PCC\|, max | max over c of s_{k,c}, single ranking | Secondary |
| Posterior signed PCC, balanced | Per component, rank by signed PCC (positive markers first), then round-robin | Secondary |
| Hard-assignment \|PCC\|, balanced | As the primary, with p_c replaced by the one-hot assignment map | Secondary |
| Mean intensity, variance | Per-bin over measured pixels | Simple label-free |
| Moran's I | Global Moran's I of each ion image over measured Moore-neighbour edges, the same definition as `evaluation.morans_i`. Constant images rank last | Label-free spatial coherence; **not** a MALDIquant substitute |
| Random | 100 seeded permutations (seed 20261009) | Floor: mean and 5th–95th percentiles |
| **Oracle** | Rank by the maximum **signed** PCC over expert classes. This matches the reference convention, which ranks positive PCC per class and takes the union. It is **not** max \|PCC\|: on three-class CAC a strongly negative correlation with one class does not make a bin reference-positive. On two-class GBM the masks are complementary, so the two coincide. A three-class test covers this | **Supervised oracle ceiling, not deployable**; shown separately |

**Stated asymmetry:** the PCC baselines use all pixels, whereas IG uses 12 sampled pixels per component.

## 5. Gate (c): S3PL

- **Normalisation audit.** A documentary check in this order: the paper text, the upstream repository at the commit the paper cites, then CAC consistency. The maximum-F1 bound from Section 2 limits how much normalisation could change mSCF1.
- **Matched-K re-rank.** Only if S3PL GBM is placed in the main table; a small effect is expected. Not implemented in this round.

## 6. Gate (d): bounded GPU tests on development sections (pixel-count patch applied 9 October as an opt-in flag; production behaviour unchanged when it is omitted)

**BIC-selected K** (CPU on saved latents; IG then needs GPU):

- Candidates K ∈ {1, …, 6}. StandardScaler, full covariance, `n_init` 20, `random_state` = the production seed, otherwise sklearn defaults identical to production.
- If ΔBIC < 10, choose the smaller K.
- **Failure rule (amended during implementation):** sklearn reports convergence only for the best of its `n_init` initialisations. A K whose best fit has not converged, or whose fit raises an error, is excluded and recorded. Per-initialisation convergence counts would need refits with `n_init` = 1 and different seeds, which would no longer reproduce the production fit, so they are not collected.
- **Provenance check:** refitting the production K on the saved latents must reproduce the saved assignments (ARI ≥ 0.999), or the script stops. On GBM108_positive/uniform_mean this check gave ARI 1.0. That is code validation only; the BIC outcome was not inspected.
- **If BIC selects K = 1, that is the primary result:** "no supported multi-cluster latent structure under BIC". A forced best-K ≥ 2 IG run may be reported only as a separately labelled sensitivity analysis and is never called BIC-selected IG.
- Balanced accuracy is not computed when K differs from the class count; ARI and NMI only.

**BIC run specification (drafted 9 October after the 40TopL pixel-count result; approved by the supervisor on 9 October, 22:55, with changes a–c below; nothing run). The BIC outcome has not been seen. The only earlier execution is the quarantined smoke run in Section 10, whose output was never read.**

- **Question answered:** is the production K supported by BIC, or arbitrary? The result is descriptive, per section and arm. **There is no arm or collection verdict for BIC**, and production K stays the reported setting whatever BIC shows.
- **Order:** only after the GBM108_positive pixel-count decision table has been posted to the supervisor and reviewed. The BIC job script is written at that point. It does not change the pixel-count runs.
- **Sections and arms:** GBM108_positive and 40TopL (the same development sections as the pixel-count test, not confirmation evidence), each in central_only and uniform_mean, so 4 BIC selections. Production K is 2 for GBM108_positive and 3 for 40TopL in both arms.
- **Input:** the saved production `latent_mean.npy` and `coordinates_and_gmm.npz` in each production attribution folder. CPU only, no labels read, `select_gmm_k_bic.py` (selection version 2) with `--production-k` set as above, `--seed 1`, `--n-init 20`. Outputs go to `results/diagnostics/gate_d_bic/<section>_seed1/<arm>/bic_selection.json`, never to production folders.
- **Candidates and rule (already coded in `gate_d_helpers.select_gmm_k_by_bic`, unchanged):** K ∈ {1, …, 6}. Only K whose best fit converged are compared. Among them, the smallest K within ΔBIC < 10 of the minimum is selected. A K that fails or does not converge is excluded and recorded.
- **Provenance check first:** refitting the production K must reproduce the saved assignment (ARI ≥ 0.999), or the script stops for that section-arm, and it gets no BIC result.
- **(a) No GPU IG run at any BIC-selected or forced K.** Reasons: IG is no longer the likely headline, the pixel-count label alignment cannot apply when the segmentation changes, and a new IG run would need a new reproduction baseline.
- **(c) K = 1 handling:** if K = 1 is selected, the primary result for that section-arm is "no supported multi-cluster latent structure under BIC". The script also records the best K ≥ 2 under the same tie rule. No IG is run on it.
- **(b) Optional CPU follow-up, descriptive only: "BIC-K segmentation sensitivity, descriptive".** Applies only to a section-arm where the BIC-selected K (or, after K = 1, the recorded best K ≥ 2) differs from production K.
  - Refit the GMM at that K on the saved latent (production settings: StandardScaler, full covariance, `n_init` 20, seed 1).
  - Compute the soft posterior maps, then the posterior-|PCC| balanced ranking with the existing `simple_baselines.posterior_pcc_rankings`.
  - Score mSCF1 at K_bin with the existing scorer, and compare it with the saved posterior-|PCC| at production K (gate (a)/(b) bin-level summary, m = 1).
  - ARI and NMI of the refitted hard assignment against labels are descriptive; no balanced accuracy.
  - **No trigger and no verdict.** The label "BIC-K segmentation sensitivity, descriptive" is used everywhere it appears.
  - If this needs more than a small script reusing existing functions, it is dropped and the supervisor is told instead.
- **Reporting (per section and arm):** the BIC value and status for every candidate K, the selected K, whether it equals production K, the refit ARI, the primary-result sentence, and, where (b) ran, its labelled descriptive comparison. Selected K = production K is reported as "BIC supports the production K", with no further computation.
- **Resources:** `batch`, 1–2 CPUs, small memory (to be set from a first `sacct` reading, not `bigbatch`). The job script follows the cluster rules: one array task per section-arm, `sbatch --parsable`, and shared output folders created before submission.

**Attribution-pixel count** (the only variable changed):

- The production sample is preserved exactly. The same seeded generator (`sampling_seed + 700`, shared sequentially across components in label order) produces one permutation per component.
- Attribution pixels are positions 0–11, as in production; faithfulness pixels are positions 12–43, unchanged.
- The 48- and 192-pixel arms add positions 44 onward, so the sets are nested: 12 ⊂ 48 ⊂ 192.
- If a component has too few pixels, n = 12 + min(target − 12, available − 44), and the actual n is recorded. An arm whose capped n equals the next smaller arm's n is marked "not distinct". Fewer than 44 pixels in a component is an error, as in production.
- Aggregation stays |IG| as in production. **Signed versus absolute aggregation is a separate later ablation at n = 12.** Extra sampling seeds are a separately labelled replication, because changing the seed changes the production 12-pixel sample.

**Pixel-count run specification (fixed 9 October, before any gate (d) run; gate (a)/(b) results had already been seen):**

- **Sections:** GBM108_positive and 40TopL, one development section per collection. These are the development sections named in the Results Record for the window campaign. They are not confirmation evidence.
- **Arms:** central_only and uniform_mean, each scored with its own GMM as in gates (a)/(b). The decision rule is applied **per arm**.
- **Runs:** n ∈ {12, 48, 192} per section and arm, all through the patched `--attribution-total` path. That is 12 GPU runs. Outputs go to `results/diagnostics/gate_d_pixel_counts/<section>_seed1/<arm>/n<N>/` and never to the production directories.
- **Reproduction gate (n = 12; amended 9 October after supervisor review, before any gate (d) output existed):**
  - **PASS** requires two things: the n = 12 rerun selects the **identical bin set** at K_bin as the saved production IG list, **and** it reproduces the saved mSCF1 to 1e-12.
  - **Recorded but not gating:** the number of positions within the top K_bin whose order differs from the saved list, and the maximum relative difference between the new and saved attribution arrays. For each array this is max |new − saved| / max |saved|; the largest over arrays is reported.
  - **Reason for the amendment:** GPU nondeterminism can swap near-equal bins that are not exactly tied, and mSCF1 at K_bin depends only on the set. The earlier draft of this gate required the same order up to exact ties. Budget-multiplier results depend on order, so they remain descriptive only.
  - **On failure:** the comparison for that section and arm stops, the failure is documented, and the arm gets no verdict. The criterion is not loosened after the fact.
- **Run-validity checks (added 9 October, before any gate (d) output existed).** The evaluator checks each of the n = 12, 48 and 192 runs before scoring anything. If any check fails, it refuses, and that section-arm gets **no verdict**:
  - The IG run status must be `valid`. A run that fails the IG completeness check (`needs_more_ig_steps`) is not scored. A larger pixel count does not relax this.
  - The run configuration must match the n = 12 run exactly: attribution version, arm, dataset, model hash and configuration, input specification, pixel and bin counts, GMM settings and component counts, and IG settings including the sampling and selection seeds. The pixel count must be the only variable that changes.
  - **Excluded from that comparison but recorded per run:** `differentiable_posterior_max_absolute_difference`. It is a floating-point diagnostic computed on the GPU in each run, and it can differ in the last digits between runs and nodes with no configuration change. The GMM assignment is compared separately, label for label, against production.
- **GMM label alignment (amendment, 9 October).**
  - **Why it was adopted.** It was adopted after the 40TopL central_only n = 12 reproduction failure (Section 10). That failure was caused only by component order: the identical segmentation was numbered differently. It was adopted **before any central_only gate (d) scores existed** (none were computed) and **before any uniform_mean gate (d) values were read**.
  - **Rule.** Every gate (d) IG run uses `--align-gmm-labels-to-production <production attribution folder>`. After the GMM refit, the script looks for the permutation of component labels that makes the refitted hard assignment identical, pixel for pixel, to the saved production assignment.
    - If exactly one permutation works, it is applied.
    - If none works, the run stops with **exit code 5** and writes no attribution outputs.
    - The mapping is never chosen from attributions, scores or F1.
  - **Applied consistently.** The permutation is applied to the mixture weights, means, covariances, precisions and precision Cholesky factors of the fitted GMM. So the posterior target, the attribution sample, every `component_k_*` output and the saved GMM parameters all use production's numbering.
  - **Posterior check.** The relabelled posterior must then reproduce the production assignment and assigned posterior (`check_posterior_against_saved`, tolerance 1e-4). The maximum difference is recorded.
  - **Component count.** If the refit K differs from the number of components in the production assignment, or the refit leaves a component empty, this is an alignment failure (exit 5). It is never a partial match.
  - **Reference hash.** Each run records the SHA-256 of the production `coordinates_and_gmm.npz` it aligned to, and the hash is part of the run signature. The evaluator refuses any run whose reference hash differs from the production `coordinates_and_gmm.npz` it compares against. The job script and the evaluation script point at the same production folder for each section and arm.
  - **Recorded per run** in `summary.json` as `gmm_label_alignment`: whether it was enabled, the permutation, whether it is the identity (an identity mapping is a recorded no-op), the maximum posterior difference, and the refit environment (NumPy, sklearn and torch versions, GPU, thread settings, node). The production environment was not recorded, and the summary says so. Why sklearn listed the components in a different order is not investigated further.
  - **One code version for all of gate (d).** Both 40TopL arms (n ∈ {12, 48, 192}) are rerun with the flag, and GBM108_positive uses it too. The evaluator refuses any run made without it.
  - **Consistency check (uniform_mean, 40TopL).** The mapping should be the identity, and the rerun evaluation should match the superseded uniform_mean evaluation to 1e-12: mSCF1 at every n and budget multiplier, and the change at K_bin. If it does not match, stop and report before anything else. The check is `scripts/check_gate_d_uniform_consistency.py`. It reads the superseded evaluation from `superseded_label_order/40TopL_seed1/uniform_mean/evaluation/summary.json` and writes `40TopL_seed1/uniform_mean/consistency_vs_superseded.json`.
  - **Evidence is kept.** The superseded 40TopL outputs (the failed central_only runs and the earlier uniform_mean runs and evaluation) are moved, not deleted, to `results/diagnostics/gate_d_pixel_counts/superseded_label_order/`, and logged in Section 10 as superseded attempts, with the reason.
- **GBM108_positive / uniform_mean reproduction risk (decided 9 October, before any gate (d) output):** the saved production IG for this arm is the 16 September pilot (attribution version 1), and the data-loading code has changed since. The rule above stays as written, with **no fallback**. If this arm fails the gate, uniform_mean gets no verdict, and the reason is documented.
- **Resources (decided 9 October):** `batch`, not `bigbatch`, with `--exclusive`. 40TopL uses 8G; GBM108_positive uses 24G. Move to `bigbatch` only if `sacct` MaxRSS or an out-of-memory failure shows it is needed.
- **Metric:** bin-level mSCF1 at K_bin with the existing scorer, plus the Section 2 budget multipliers for description. The change is mSCF1(n) − mSCF1(n = 12, saved production).
- **Decision (direction fixed here):** a 16-section rerun of a setting n is triggered only if that change is **≥ +0.02 on both** sections, for that arm. Any other outcome, including a decrease of 0.02 or more, means the production n = 12 stands and the result is reported descriptively. IG(n) − posterior-|PCC| is also reported descriptively. It is not a new verdict.

### 6.1 Final experiment round (supervisor chat, 15 October 13:00 and 13:30; experiments end Tuesday 20 October)

**Item A: learned attention through the fair-scoring test** (chat 15 October 13:00; fix for the GBM count mismatch approved in the chat of 15 October 15:35, point 1; written 15 October before any attention score at K_bin existed).

- **Inputs:** the frozen seed-1 `real_attention` models of `results/experiments/spatial_attention_context/` (all 16 sections). Their GMM and IG settings match the production arms (Section 10).
- **CAC:** the saved attention peak evaluations are already at K_bin and are used as they are.
- **GBM** (the attention evaluations used pre-tuning counts):
  - **A(b), first:** `scripts/check_saved_list_reproduction.py` rebuilds the IG and L2 rankings from the saved attributions and must reproduce the saved old-count lists (same bins, order differing only by exact ties) and their mSCF1 to 1e-12. On failure it exits 4 and the section stops.
  - **A(a):** the unchanged `evaluate_spatial_msipl_attributed_peaks.py` re-evaluates the frozen attributions at production K_bin (legacy `massnet_paper_aligned`, the same options as the production tuned-count job) into the new folder `real_attention/peak_evaluation_tuned_count/`. Nothing is overwritten.
- **A(c):** the **unchanged** `evaluate_fair_scoring_baselines.py` scores the attention arm at bin level and under the approved partitions. On 15 October all seven hashed code files were confirmed identical to the hashes recorded by the existing campaign.
  - Job: `slurm_jobs/run_fair_scoring_extra_arm.sh attention` and `submit_fair_scoring_extra_arm.sh attention pilot|all`, with GBM22_2 as the pilot.
  - Output: `results/diagnostics/fair_scoring_baselines/extra_arms/{bin_level_only,with_approved_partitions}/<section>_seed1/attention/`.
- **Decision table:** `scripts/summarise_fair_scoring_arms.py`, a new script. It refuses to combine summaries whose evaluator code, parameters or approval differ.
- **Rule (fixed in the chat):** "attention improves on uniform" if mean attention − uniform IG mSCF1 is ≥ +0.02 **and** positive in ≥ 6/8 sections, at bin level **and** under P1. It is "equivalent" if within ±0.02 at both scales, and "mixed" otherwise. Attention IG vs posterior-|PCC| is reported under the Section 7 rules and the Section 7.1 wording.
- **Tests:** `test_fair_scoring_arms.py` (7 tests: the verdicts, no verdict below 8 sections, refusal on mixed code, the G3 and mechanism rules, and the A(b) pass on an exact tie and failure with exit 4). The new modules were added to `run_fair_scoring_tests.sh`.
- **G fair scoring uses the same job and summariser** with the arms `attention_centremask_p50`, `uniform_centremask_p50` and `shuffled_attention_centremask_p50` (G3: indices 5 and 9 only).

The rules below are copied from the chat entries, which fixed them before any output existed. Where Code had to read an ambiguity, the reading is marked; both G readings were confirmed in the chat of 15 October 15:35. It was written down before any run and is not changed after results.

**Item G: train attention with random centre masking** (written 15 October, before any G code ran on the cluster; nothing submitted).

- **Change:** during training only, each sample's centre spectrum given to the model is replaced by zeros with probability **p = 0.5**, drawn from a separate CPU generator seeded with seed + 2,000,003 = 2,000,004 and logged (masked count per epoch in `training_history.json`, totals in `metadata.json`). Neighbours are unchanged. The reconstruction target is always the unmasked centre. Architecture, decoder, output size, 100 epochs, seed 1, Adam (lr 1e-3, batch 128, cosine schedule), GMM K, budget and scoring are unchanged. Patch-level reconstruction is not used.
- **(reading confirmed by the supervisor, chat 15 October 15:35, point 2a)** "The centre fed to the encoder" is applied to the **whole model input**: the zeroed centre replaces the real centre both in the encoder concatenation and as the attention query. This is what the predeclared test "masked rows give no gradient through the centre input" requires; keeping the real centre as the query would pass centre information through the attention weights.
  - **Consequence (recorded as the supervisor asked):** `AttentionNeighbourhood.projection` has a bias, so a masked row's query is `tanh(b)`, a learned constant that acts like a mask token. Masked-row weights are chosen by neighbour content against that constant and are **not** forced to be uniform.
  - Test: `test_masked_row_attention_depends_only_on_neighbours_and_bias`, under which the weights are unchanged when the true centre changes and differ from uniform.
  - No other mechanism is added: no separate mask token and no context-derived query.
- **(reading confirmed, point 2b)** The metric for rules 2 and 4 is IG mSCF1 at production K_bin from the fair-scoring summaries, at bin level and under P1.
- **Code:** `train_vae(centre_mask_probability, centre_mask_seed)` and `apply_centre_mask` in `src/spatial_msipl/training.py`; `--centre-mask-probability`/`--centre-mask-seed` in `scripts/train_spatial_msipl_production.py`. At p = 0 nothing is drawn. Checked on 15 October: p = 0 reproduces the committed `HEAD` `train_vae` bit for bit (history, weights and global RNG state) for attention and uniform on the synthetic set.
- **Tests (`test_centre_masking.py`, 8, including the masked-query test above):** whole-row masking that leaves the input untouched; p = 0 step-for-step equality with the default path; the target is always the unmasked centre; masked rows get zero gradient through the centre input; masking lives only in the training loop (no model state, evaluation uses the real centre); seeded and requires an explicit seed; an interrupted masked run resumes exactly, and a different mask seed is refused on resume.
- **Arms** (root `results/experiments/spatial_centremask_p50/<section>_seed1/<arm>/`; checkpoints `/datasets/zsuliman/msi_checkpoints/spatial_msipl/centremask_p50/`; nothing existing is overwritten):
  - G1 `attention_centremask_p50`: corrected 3×3 attention (`sqrt_bins`), 16 sections.
  - G2 `uniform_centremask_p50`: uniform 3×3, 16 sections.
  - G3 `shuffled_attention_centremask_p50`: shuffled-context attention, 160TopL and GBM22_2, shuffle seed 1701.
  - All use the cached loader (equivalent to streaming, validated on GBM108_positive; only the timer differs).
- **Evaluation, unmasked input:** reconstruction; GMM (K 2 GBM, 3 CAC; `n_init` 20, seed 1) and IG (12 pixels per component, 64 steps, sampling seed 1); matched peak evaluation at the **production K_bin** (GBM 584/940/691/986/834/1028/695/911 in section order; CAC as the existing arms), checked in-job against the legacy `unique_nearest_bins`. Then fair scoring of G1 and G2 with the **unchanged** `evaluate_fair_scoring_baselines.py` (bin level, and the approved partitions), which applies the strict IG/L2 reproduction before scoring.
- **Job:** `slurm_jobs/run_centremask_campaign.sh` (34 array tasks: 0–15 G1, 16–31 G2, 32–33 G3), `submit_centremask_campaign.sh` (pilot task 9 = 160TopL G1, then the other 33 `afterok`; CUDA quarantine excluded; `--parsable`), `check_centremask_campaign.sh` (status only). The CUDA warm-up and the masking tests run before training. Scientific scripts write their output to logs inside the result folder, so the Slurm `.out` holds status lines only.
- **Rules (fixed in the chat; unchanged here):**
  1. **Mechanism:** "masking made attention selective" if the median normalised attention entropy of G1 falls below 0.95 on **both** 160TopL and GBM22_2; otherwise "attention stayed near-uniform". Measured with the existing diagnostic on the same 128 centres (sample seed 20261007) by `scripts/audit_centremask_attention_weights.py`, which also re-measures the unmasked seed-1 checkpoint on the same centres. No peak scores are involved.
  2. **Peak quality, per collection, bin level and P1:** G1 vs the item A attention arm, and G1 vs G2. "Improves" if mean gain ≥ +0.02 **and** positive in ≥ 6/8 sections (at both scales); within ±0.02 "equivalent"; otherwise "mixed". Metric (confirmed): IG mSCF1 at production K_bin from the fair-scoring summaries.
  3. G1 and G2 IG vs posterior-|PCC| under the Section 7 rules, reported with the Section 7.1 wording.
  4. **Spatial specificity (G3):** real-context masked attention (G1) must beat shuffled-context masked attention (G3) by ≥ 0.02 on both exploratory sections. Descriptive, two sections. Metric (confirmed): bin-level IG mSCF1 at production K_bin.
  5. p is not retuned after results; any sensitivity is a separately labelled analysis.

**Item C2: S3PL for 100 epochs on all 16 sections, seed 1** (chat 15 October 13:00, plus 15:35 point 5; written 15 October before any run).

- **Settings:** the released RNG path (`random_seed` 1, no controlled seeds) and every other setting of the existing 10-epoch baselines: patch 9 on CAC and 3 on GBM, batch 16, lr 0.01, `reference_spatial_max`, 256 peaks per patch, CAC from imzML and GBM from HDF5.
- **Root:** `reproducibility/s3pl_e100/seed1_released/`. Training names contain `100epochs`, and the 10-epoch artifacts are never touched.
- **Logging only** (`baselines/s3pl/train.py`, opt-in config key `checkpoint_epochs`, CLI `--checkpoint_epochs`):
  - state-dict copies at epochs 10, 25, 50 and 100 (`<name>_epochE.pt`);
  - per epoch: the last-batch loss (equal to `train_history`, which is unchanged), the **epoch-mean loss** (the mean of the per-batch `loss.item()` values already computed for the progress bar), epoch wall time, peak GPU memory so far and peak host RSS so far;
  - in `runtime_metrics.json`: total training seconds (training loop only), peak GPU memory, peak host RSS and the GPU model; GNU `time -v` per step when available.
- **Logging check, 15 October:** on a synthetic set (CPU), the modified `train()` gives the committed `HEAD` version's `train_history` and final weights bit for bit.
- **Evaluation after training** (`scripts/evaluate_s3pl_epoch_checkpoints.py`): each checkpoint is scored with the released `test()` at the training-default count (as the existing baselines) and, on CAC, at the matched count (as the existing `_matched_` evaluations). It runs only after training, because `test()` draws from the global torch RNG and evaluating mid-training would change later epochs.
- **Validation:** the epoch-10 checkpoint is compared with the existing 10-epoch mSCF1 (default count; and matched count on CAC). The difference is reported, and if it does not reproduce, the reason is given before the curve is interpreted. The 240TopL drift (0.672 vs 0.670) shows that GPU nondeterminism can move this.
- **Reporting** (descriptive, no verdict): the mSCF1 curve by epoch per section and collection, and whether 10 epochs falls before, at or after the best of the four points. S3PL is reported at 10 epochs (its published protocol) and at 100 epochs (the VAE's length); **the best epoch is never picked per section**.
- **Jobs:** `run_s3pl_e100.sh` (16 tasks, GPU, `bigbatch`, CUDA warm-up, quarantine excluded) and `submit_s3pl_e100.sh` (pilot 160TopL, then the other 15 `afterok`).

**Item E, step 1: data-contract audit for 7×7 and 9×9 windows** (chat 15 October 15:35, point 3; must pass before any E training job).

- `audit_spatial_msipl_data_contract.py` takes `--windows` (default 3 5, unchanged).
- For every listed window it checks:
  - the production neighbour slots equal the independent reference at every pixel;
  - the production loader's neighbour mask and TIC-normalised neighbour spectra at the sampled pixels **plus that window's most partially covered pixel** (edges, holes, partial grids);
  - coverage (full, partial and no-neighbour pixel counts; min/median/max valid neighbours).
- Tests: 3 new (edges and holes at 7×7/9×9 on a partial grid; RCC labels; 3 must be included), 6/6 pass locally under h5py 3.16.0 and NumPy 2.4.6.
- Run: the existing `audit_spatial_msipl_data_contract.sh` array (40TopL, 280TopL with its partial coverage, GBM108_positive, GBM22_2) with `AUDIT_WINDOWS="3 5 7 9"` and `AUDIT_OUTPUT_ROOT=results/diagnostics/spatial_msipl_data_contract_windows`.
- The E training specification (`uniform_p7`, `uniform_p9`) is written here after this audit passes and before any E training job.

**Item E, step 2: training and scoring specification** (written 15 October, about 17:30 SAST, after audit 68632 passed on all four sections and before any E training job; nothing submitted).

- **Arms:** `uniform_p7` and `uniform_p9` on all 16 sections, trained exactly like `uniform_p5`: `uniform_mean`, 100 epochs, seed 1, batch 128, lr 1e-3, cosine schedule, cached loader on GBM (checked against streaming by `validate_spatial_window_cache.py`, extended to 7 and 9) and streaming on CAC. The only code change is that 7 and 9 are allowed as `--window-size` values.
- **Root:** `results/experiments/spatial_window_e79/<section>_seed1/<arm>/`; checkpoints in `.../window_e79/`.
- **Evaluation:** GMM K 2 (GBM) and 3 (CAC), IG with 12 pixels per component, then matched peak evaluation at the **production K_bin**, then the unchanged fair-scoring evaluator (`run_fair_scoring_extra_arm.sh uniform_p7|uniform_p9`).
- **p5 found at the old counts (15 October, before any p5 score at K_bin was computed or read):** the existing `uniform_p5` GBM evaluations used the pre-tuning counts, as attention did. So p5 goes through the same approved A(a)/(b) route (reproduce the saved old-count list, then re-evaluate at K_bin into `peak_evaluation_tuned_count/`) via `run_fair_scoring_extra_arm.sh uniform_p5`. CAC p5 is already at K_bin. **Approved by the supervisor on 15 October 19:37.**
- **Rule (13:00 item E; confirmed and extended by the supervisor on 15 October 19:37, before any E output existed):** a larger window "helps" only if its IG mSCF1 at K_bin beats real 3×3 (`uniform_mean`) by ≥ 0.02 in mean **and** is positive in ≥ 6/8 sections of a collection, **at bin level and under P1**.
  - If |mean| < 0.02 at both scales, it is "equivalent". Anything else is "mixed", meaning it does not meet the "helps" rule. This is the same structure as items A and G.
  - The verdict uses all 8 sections of a collection. The 7 confirmation sections and the window campaign's development section (40TopL, GBM108_positive) are reported separately beside it, at both scales.
  - p7 and p9 get the verdict; p5 is reported descriptively.
  - Implementation: `window_rule()` in `scripts/summarise_fair_scoring_arms.py`. Tests: `test_window_rule_verdict_and_separate_development_report` and `test_window_rule_requires_p1_as_well_as_bin_level` in `test_fair_scoring_arms.py`. All 9 tests in that module pass.
- **Jobs:**
  - `run_window_e79_campaign.sh`: 32 tasks (0–15 p7, 16–31 p9). It refuses to run unless the four audit summaries are `valid`.
  - `submit_window_e79_campaign.sh`: the pilot (task 8, 40TopL p7) alone, then the rest via `--indices` (`bigbatch` cap of 48 submitted jobs per user).
  - Estimated cost from p5 (24 slots, GBM22_2 1.7 h, 3.85 GB GPU): GBM p9 (80 slots) about 5–6 h and about 12 GB; about 65 GPU-hours for all of E.

**Item D: RCC feasibility** (chat 15 October 13:00, plus 15:35 point 4; go/no-go by the end of Friday 16 October).

- **Environment:** a separate `rcc_env` (conda-forge and bioconda: R 4.5.3, Cardinal 3.12.1, CardinalIO 1.8.0, rhdf5 2.56.1), created on 15 October with Zayd's OK. `s3pl_env` is untouched.
- **Job:** `run_rcc_feasibility.sh` (CPU). It checks the archive SHA-256, extracts `rcc.rda` to job-local scratch, then runs `scripts/rcc_feasibility_export.R` (`rcc_env`), which loads it through Cardinal or, failing that, the legacy slots. It records runs and per-pixel labels, and exports each fully labelled run as an HDF5 in the project layout to `/datasets/zsuliman/msi_data/rcc_cardinal/`, with labels 0..K−1 by sorted level. Each export is audited with the data-contract audit (collection `rcc`).
- **Decision** (`results/validation/rcc_feasibility/go_no_go.json`): go only if all four criteria hold. **(reading)** Criterion 4 counts as met only if at least 4 labelled sections pass the audit, since otherwise criterion 3 has no usable sections.
- **Unlabelled (NA) pixels: option (a), predeclared on 15 October 19:37 (supervisor chat), before any RCC export or score.**
  - NA is kept as a third class, `unannotated`. K = 3, and every pixel is kept so the spatial grid stays intact. This mirrors CAC, where background is a scored class.
  - Encoding: the sorted annotated levels first, then `unannotated` last (cancer 0, normal 1, unannotated 2 if the levels are those two). The encoding is written to the report.
  - Criterion 3 means "≥ 4 runs with pixel-level cancer **and** normal labels". NA pixels don't disqualify a run. Every run with all annotated levels present (and finite, non-negative spectra) is exported.
  - **The nature of NA is reported descriptively,** never used to change the design. The report gives per-class TIC (median, mean, 10th/90th percentiles) for each run. It also gives where NA pixels lie: the fraction on the run's bounding-box edge, the fraction touching unmeasured grid, and the fraction touching an annotated pixel. Together with the audit spot-check, these say whether NA is mainly off-tissue border or unannotated tissue. If it is tissue, the report says so beside every RCC number.
  - The budget is K_bin = |R@0.4| over all three classes, as specified.
  - Implementation: `scripts/rcc_feasibility_export.R` and `slurm_jobs/run_rcc_feasibility.sh`. Test: `test_rcc_labels_must_be_consecutive_classes` now also checks that a K = 3 export passes the audit.
  - The first outputs (68633) are moved aside, not deleted, before the rerun; the rerun needs Zayd's OK.
- **Outcome, rerun 68805 (read 16 October after Zayd's sync): GO.** `results/validation/rcc_feasibility/go_no_go.json`.
  - All four criteria are met: Cardinal 3.12.1 in `rcc_env`; `rcc.rda` loads (Cardinal `MSImagingExperiment`, 16,000 pixels × 10,200 m/z, m/z 150.08–1000); 8/8 runs have pixel-level cancer **and** normal labels; and 8/8 exported HDF5s pass the data-contract audit (`valid`).
  - The 8 runs are MH0204_33, UH0505_12, UH0710_33, UH9610_15, UH9812_03, UH9905_18, UH9911_05 and UH9912_01. They have 972–3,564 pixels each, with cancer 81–608, normal 190–793 and unannotated 609–2,763.
  - **Nature of NA (descriptive; `export_report.json` plus the 8 audit spot-checks):**
    - Every run is a fully measured rectangular grid: no unmeasured holes, so "touching unmeasured grid" equals "on the image edge".
    - Cancer and normal are each one compact region, the two separated by a gap. NA fills everything else.
    - NA is the largest class in every run (45–78% of pixels). Only 10–25% of NA pixels lie on the image edge, and only 8–22% touch an annotated pixel. So NA is mostly a large surrounding and separating region, not a thin edge strip or a margin around the annotations.
    - The per-pixel TIC of NA is not near zero: its median is 82–94% of the annotated classes' medians (about 4,500–5,500 vs 5,200–6,300). The intensities are small integers, with TIC about 5,000 in every class, which suggests the released data may already be processed. In that case TIC cannot separate glass from tissue.
    - **Reading:** the layout is consistent with off-tissue background around two tissue pieces, but the signal level does not show that NA is empty. **Whether NA is off-tissue or unannotated tissue is not established from these descriptors.** Following the 19:37 rule, every RCC number is reported with the note "the third class (unannotated, the largest class: 45–78% of pixels) may include tissue; not established".
  - **Next:** the RCC run specification is drafted for the supervisor in the chat entry of 16 October. No RCC training job has been prepared or submitted.
- The RCC run specification (if go) is written here before any RCC training job.

**Item D, step 2: RCC run specification** (proposed by Code on 16 October 17:28; approved with conditions by the supervisor on 16 October 17:36; written here on 16 October at about 18:10 SAST / 16:10 UTC, before any RCC code, training job or score existed). If it cannot finish by Tuesday 20 October, RCC is reported as incomplete; the window is not extended.

- **Sections:** the 8 exported runs, in this fixed order: `RCC_MH0204_33`, `RCC_UH0505_12`, `RCC_UH0710_33`, `RCC_UH9610_15`, `RCC_UH9812_03`, `RCC_UH9905_18`, `RCC_UH9911_05`, `RCC_UH9912_01` (`slurm_jobs/rcc_sections.sh`). All 8 are **confirmation** sections, because no RCC run was used for development. Inputs: `/datasets/zsuliman/msi_data/rcc_cardinal/RCC_<run>.h5` (labels cancer 0, normal 1, unannotated 2).
- **Patients (condition 5), checked 16 October before any RCC code or score:** the Cardinal pixel metadata has only `x`, `y`, `run` and `diagnosis`, so it holds no patient field. The dataset documentation in the verified archive (`CardinalWorkflows_1.44.0.tar.gz`) settles it. `man/rcc-data.Rd` says "Eight matched pairs … with each matched pair as a separate sample on a separate slide", and `vignettes/MSI-classification.Rmd` says "each matched pair of tissues belonging to the same subject are on the same slide (i.e., the same run)". So there are **8 runs from 8 subjects, one run per subject**, and no grouping is needed. The mapping and its source are fixed in `RCC_PATIENT` in `scripts/summarise_rcc_fair_scoring.py`.
- **Documentary note on NA (descriptive; it changes nothing in the design):** the same vignette removes the NA pixels with `subsetPixels(rcc_peaks, !is.na(diagnosis))` and names the result `rcc_nobg`, which suggests the dataset author regards NA as background. The vignette also notes that runs UH0505_12 and UH9905_18 "have very heterogenous tumor tissues, with what appear to be large sections of normal tissue". Neither statement establishes what NA pixels contain, so the predeclared NA caveat stands unchanged.
- **Disclosures on every RCC number:**
  - (extended by the supervisor, chat 16 October 18:34) "unannotated class, 45–78% of pixels; the dataset's own Cardinal workflow treats these pixels as background (`rcc_nobg`), but this was not independently verified";
  - limitation, beside the RCC results: "per the dataset documentation, UH0505_12 and UH9905_18 contain heterogeneous tumour with large normal-looking areas". Descriptive only: no exclusion and no separate analysis;
  - the GMM uses K = 3, the number of label classes, so the segmentation is label-free in training and ranking but class-informed in its component count.
- **Step 1, preparation (CPU, one task per run, before training):**
  - **Budget:** K_bin = |R@0.4|, the size of the mixed reference set at PCC 0.4 over **all three classes**, computed with the existing nearest-threshold rule (`true_indices_at_threshold`) on the raw-intensity class PCCs (`scripts/compute_reference_budget.py`, output `results/experiments/rcc_spatial_msipl/<section>_seed1/reference_budget.json`). |R_t| at every threshold is recorded. The cancer/normal-only sizes are recorded descriptively and are **never** used as a budget.
  - **Structural audit:** the unchanged `audit_peak_partitions.py` (P1 and P3) into `results/diagnostics/peak_partition_audit_rcc/<section>/`.
- **Partition approval (condition 3):** P1 is used on RCC only if it passes S1 in all 8 runs. A reviewer then writes `results/diagnostics/peak_partition_audit_rcc/partition_approval.json` listing P1 alone with the audited hashes. If P1 fails S1 in any run, RCC is scored at bin level only and the record says so. **P3 is never used on RCC,** whatever its audit shows.
- **Step 2, training (GPU, one task per run-arm; 0–7 `central_only`, 8–15 `uniform_mean`):** `train_spatial_msipl_production.py` exactly as the CAC production arms: 3×3 window, 100 epochs, batch 128, hidden 512, latent 5, lr 1e-3, `spatial_lambda` 0, seed 1, checkpoint every 5 epochs, streaming loader (the runs are small). The real CUDA warm-up runs first and the quarantined nodes are excluded. Root `results/experiments/rcc_spatial_msipl/<section>_seed1/<arm>/`; checkpoints `/datasets/zsuliman/msi_checkpoints/spatial_msipl/rcc/<section>_seed1/<arm>/`.
- **Step 3, GMM and IG:** `run_spatial_msipl_gmm_integrated_gradients.py` with the CAC settings: K = 3, `n_init` 20, 12 attribution and 32 faithfulness pixels per component, 64 steps, seed 1, sampling seed 1.
  - **Predeclared failure handling:** if a GMM component has fewer than 44 pixels (12 + 32), the IG script stops by design. That run-arm is then reported "not done: GMM component below 44 pixels", and no setting is changed. If the IG status is not `valid`, the run-arm is likewise reported as not done. Confirmed by the supervisor (16 October 18:34): no fallback, and no change of K, pixels or seed for any run. An arm with fewer than 8 runs gets "incomplete; no verdict", and its per-run differences are still reported descriptively, with n.
- **Step 4, matched evaluation:** the unchanged-by-default `evaluate_spatial_msipl_attributed_peaks.py` at `--matched-count` K_bin, with the new opt-in flag `--no-legacy` (legacy files are neither required nor read, and legacy rows are omitted). Without the flag, behaviour is unchanged.
- **Step 5, fair scoring (CPU, one task per run, both arms):** the fair-scoring evaluator, with all baselines and the oracle, at bin level and, only if approved, under P1.
  - New opt-in flags (each omitted on GBM/CAC, where the default path is unchanged):
    - `--no-legacy` with `--reference-budget FILE`: no legacy reproduction or legacy rows. K_bin taken from the saved matched evaluation must equal the budget file's K_bin, otherwise the run stops. The summary records "legacy msiPL not run on RCC (requires count tuning)".
    - `--class-subset 0 1`, used **only** for the secondary analysis below.
  - Output: `results/diagnostics/fair_scoring_baselines/rcc/{bin_level_only,with_approved_partitions}/<section>_seed1/<arm>/`.
- **Primary test:** posterior-|PCC| (balanced) vs IG under the Section 7 rules, per arm, over the 8 runs, at bin level and under P1 if approved. It is reported with the Section 7.1 wording and the 16 October wording rule (result as labelled, numbers beside it). A verdict needs all 8 runs of an arm; otherwise "incomplete; no verdict". The IG-vs-legacy rule is not applicable on RCC.
- **Secondary, descriptive (condition 2): "sensitivity, cancer/normal classes only".**
  - Same rankings and the same K_bin as the primary, with no re-budgeting.
  - With `--class-subset 0 1`, the reference sets, mSCF1, per-class metrics, the F1 ceilings, the oracle and (under P1) the reference groups use only the cancer and normal PCCs. Every pixel is kept and each class PCC is unchanged (class vs rest over all pixels).
  - The IG/L2/posterior reproduction checks still use all three classes, because they reproduce the saved all-class matched evaluation.
  - Output: `results/diagnostics/fair_scoring_baselines/rcc_cancer_normal_sensitivity/{bin_level_only,with_approved_partitions}/...`. It gets no verdict. Its table caption states that the oracle, the ceilings and the P1 reference groups follow the subset (confirmed by the supervisor, 16 October 18:34).
  - **Default path bit-identical:** a test shows that the evaluator without the flag gives the same summary as before the change, apart from runtime and code hashes, and that the subset equal to all classes reproduces the default scores.
- **Out of scope on RCC (condition 6):** attention, larger windows, centre masking and S3PL. Legacy msiPL is not run (condition 4).
- **Decision table:** `scripts/summarise_rcc_fair_scoring.py`. It refuses mixed provenance, reports per-run and per-patient values and the two disclosures, and gives no verdict for the sensitivity analysis.
- **Order (condition 7):** this specification → code and tests → Zayd sees the diff → cluster test job → preparation (8 CPU tasks), then the partition approval → 2-run pilot (UH9610_15, the largest at 3,564 px, and UH0710_33, the smallest at 972 px; both arms, 4 tasks) → the other 12 tasks → fair scoring → summary. Each `sbatch` needs Zayd's OK.

## 7. Decision thresholds

Unchanged from the previous response: 0.02 mSCF1 practical signal, per collection, seed 1.

- **IG adds value beyond its segmentation target:** IG − posterior-|PCC| (balanced) ≥ 0.02 in mean and > 0 in at least 6 of 8 sections, at bin level and under every approved partition.
- **Equivalent:** the mean difference is within ±0.02.
- **IG beats legacy, robust to scoring:** at least 7 of 8 sections at bin level, with the same direction in the K_bin collapse diagnostic, and the ordering stable across the budget multipliers. The collapse diagnostic is **not** a matched peak-level comparison; a matched one needs the Beta re-tune in Section 1.
- **Development-section GPU tests:** a change below 0.02 means the production setting stands. A change of 0.02 or more on both development sections triggers a predeclared 16-section rerun of that one setting only.

### 7.1 Rule gaps found after the results (note added 9 October; the rules above are unchanged)

These gaps were noticed only after the gate (a)/(b) results had been seen. They are recorded here so that the reported wording is accurate. **No new verdict category is added, and the rules above are not changed.**

1. **No outcome for "IG clearly worse".** The IG-versus-posterior rule defines only "adds value" (≥ +0.02 and positive in ≥ 6/8 sections) and "equivalent" (within ±0.02). A difference beyond −0.02 fits neither. The summariser labels it "mixed / not resolved by the predeclared rule". That label is a fall-through, not a mixed result. **Reporting wording:** "Neither predeclared verdict applies, because IG scored below posterior-|PCC| in every section (bin level: 0/8 sections positive in each of the four collection-arms)." The size and consistency of the gap are given as effect sizes and per-section results, not as a verdict.
2. **The budget-stability clause of "IG beats legacy" cannot be evaluated as written.** Legacy msiPL is scored at m = 1 only (Section 2), so there is no legacy ordering across budget multipliers to compare. The summariser does not compute this clause. Report the two clauses that can be evaluated (bin level, and the K_bin collapse diagnostic) and state that the third was not assessable. Do not call the rule met.
3. **"Under every approved partition" means per-collection partitions.** GBM has P1 only; CAC has P1 and P3 (Section 10).

Any future rule that covers these cases needs its own predeclaration and must be reported as a separate, labelled analysis.

## 8. Provenance, restart and reconstruction (new in v3)

**Provenance block.** Every result's `summary.json` carries a `provenance` block containing:

- evaluator and protocol versions;
- all parameters (thresholds, budget multipliers, random seed and draw count, tolerance, approved partition parameters);
- the input HDF5 path, size and SHA-256;
- path, size and SHA-256 of every source artifact (attribution arrays, GMM parameters, latent means, attribution summary, saved evaluation summary and both saved lists, legacy peaks and metrics, and partition arrays and audit summary when used);
- the approval file's SHA-256;
- the approved per-section partition hashes;
- the SHA-256 of every code file involved.

**Restart rule.** An existing result is reused only if its status is `complete` **and** its provenance block is identical to the one the current run would produce. Anything else exits with code 3 ("STALE") and is never overwritten. A person must move it aside. A bare `{"status": "complete"}` is therefore never reused. The partition audit and the BIC script follow the same rule. `summary.json` is written atomically as the last file.

**Reconstruction.** Every reported peak-level number can be rebuilt from the saved files:

- `peak_level_selections.npz` holds, per partition and method:
  - the ordered K_peak-matched group IDs;
  - their apex bins;
  - the groups covered by the first K_bin bins;
  - the reference groups at PCC 0.4.
- `rankings_prefix.npz` holds each ranking up to max(2·K_bin, the largest number of bins any method consumed to reach K_peak), plus the legacy list.
- The summary records each full ranking's SHA-256, the bins consumed per method, and the hash of each set of selected groups.
- Random draws are reconstructed from the seed. The summary records the hash of all draws and the maximum number of bins consumed.

A test rebuilds the IG matched groups from these files.

## 9. Cluster operation (new in v3)

- **No scientific computation on the login node.** The Python entry points refuse to run without `SLURM_JOB_ID`; `--allow-outside-slurm` exists for tests only. Submit scripts do file checks and `sbatch` only. The status checker reads status strings only; provenance validity is decided inside the jobs.
- **Partition and resources.** All jobs use `batch`, not `bigbatch`.
  - The partition audit requests 4 GB, 2 CPUs and 15 min, reduced after the pilot: every section peaked at 204–220 MB and was I/O bound (about 21% CPU); GBM sections took about 1 min and CAC about 5 s.
  - The fair-scoring array task requests 4 GB, 2 CPUs and 1 h for both arms of one section. Confirm with its own pilot (GBM22_2) before submitting all sections.
  - Each task records GNU-time elapsed time and peak RSS when `/usr/bin/time` exists.
  - **Run the pilot index first (GBM22_2, the largest section)** and read `sacct --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode` before submitting the rest and before lowering or raising the requests.
- **Arrays.**
  - One task per section, scoring both arms as one independently auditable unit.
  - Concurrency is set at submission with `--max-concurrent N`. If omitted, Slurm and QOS limits apply.
  - The decision table is a separate job (`run_fair_scoring_summary.sh`). It refuses to mix results with different code, parameters or approvals, and gives no verdict for a collection with fewer than 8 sections.
- **Output roots.** Bin-level-only runs go to `fair_scoring_baselines/bin_level_only/`; runs with an approved partition go to `fair_scoring_baselines/with_approved_partitions/`.
- **No CUDA.** These jobs are CPU-only and use no CUDA preflight or GPU quarantine. Any later IG job (gate d) must use the real CUDA warm-up and read exclusions from `slurm_jobs/gpu_cuda_quarantine.txt`.
- **Environment compatibility.** `run_fair_scoring_tests.sh` runs the new test modules plus `test_peak_selection` and `test_evaluation` under `s3pl_env`. It records package versions in `results/validation/fair_scoring_env_tests/`. **It must pass before any real section is processed.** Cluster job 66006 passed all 47 tests under Python 3.11.5, NumPy 2.4.6, SciPy 1.17.1, scikit-learn 1.9.0, h5py 3.16.0 and Matplotlib 3.11.1. The saved version record and full unit-test log are the compatibility evidence.

**Submission order (after approval of this protocol and code):**

1. `sbatch slurm_jobs/run_fair_scoring_tests.sh`.
2. **Only after step 1 passes under the real `s3pl_env`:** `bash slurm_jobs/submit_peak_partition_audit.sh pilot`; check `sacct`, then submit `all`, optionally with `--max-concurrent N`.
3. Review the S1 verdict and the S2/S3 diagnostics, then write `partition_approval.json` or record a rejection.
4. `bash slurm_jobs/submit_fair_scoring.sh pilot`, then `all`. Add `--approval FILE` only for the approved-partition run.
5. `sbatch slurm_jobs/run_fair_scoring_summary.sh bin_level_only` (or `with_approved_partitions`).
6. Only then consider gate (d).

**Resolved before the audit (v3.1): S2 on CAC.** S2 is now descriptive and S1 (width < 0.5 Da) is the only hard rule. The decision was made on structural grounds (bin count depends on axis resolution), without seeing any real audit output. Code: `check_partition_sanity` returns S2 values under `diagnostics`; audit version 3. Tests: the chained-axis case still fails S1 but not S2, and a new test shows a many-bin group narrower than 0.5 Da passes.

## 10. Executions on real data so far (record)

- **9 October, cluster: fair-scoring pilot job 66037 (GBM22_2) stopped correctly before scoring.** The reconstructed centre-only L2 ranking matched the saved 1,028-bin set exactly, but two bins with identical float32 scores (0.77442014; bins 57438 and 61083) were in swapped order at positions 965–966. The cause is platform-dependent tie order in `np.argsort` (NumPy 2.4.6 on the cluster), not a scoring difference. The set, and therefore mSCF1, is unaffected. **Fix (v3.2, evaluator version 4):** a deterministic tie-break and a tie-aware reproduction check, with unit tests. A read-only check of all 32 saved IG and L2 lists (16 sections × 2 arms) under the new rule found **0 failures**; with the index tie-break, the reconstructed order matches every saved list exactly. No output from job 66037 was kept except its resource record.

- **9 October, cluster: fair-scoring runs after the tie-break fix.**
  - Bin level: pilot 66045 (GBM22_2), then array 66053 (all 16 sections; GBM22_2 reused the pilot after a provenance match). Decision table 66097 completed.
  - Approved partitions: array 66114. Task 1 (GBM108_negative) failed before scoring with `mkdir: Already exists`; all 16 tasks started at once and `with_approved_partitions/` did not exist yet, so this looks like a race on creating the parent directory. Nothing was written for that section. It was resubmitted alone as 66179 and completed. All 32 arm summaries are complete.
  - Decision table 66181 refused to run ("refusing to mix"). **Cause, a summariser bug:** each section records only its own approved partitions, and the approval file approves P3 for CAC only, so GBM and CAC differ in `approved_partition_parameters` by design. **Fix (summariser only; no rule, threshold or result changed):** that field must agree within each collection; versions, every other parameter, the approval hash and the code hashes must still agree across all sections. Test: `test_fair_scoring_summary.py`. The summariser is not among the hashed code files, so no section provenance changes.
  - After the fix: cluster test job 66237 passed 56/56. Decision table 66238 (`with_approved_partitions/summary_66238/`) then ran, as a Slurm `afterok` dependency of 66237. Its bin-level entries are identical to 66097.
  - **Outcome, recorded as given by the rules (Section 7.1):**
    - IG versus posterior-|PCC|: neither predeclared verdict applies in any collection-arm. IG − posterior-|PCC| is positive in 0/8 sections at bin level in all four arms (means: GBM −0.225 and −0.233; CAC −0.078 and −0.047), and under P1 (GBM −0.201 and −0.213; CAC −0.092 and −0.039, with CAC/uniform_mean 280TopL the only positive section, +0.058). On CAC, P3 equals P1. All four GBM patient means are negative.
    - IG versus legacy: positive in 8/8 sections at bin level in every arm (+0.097 to +0.157) and in the K_bin collapse diagnostic (+0.066 to +0.157). The budget-stability clause is not assessable (Section 7.1, item 2), so the rule is reported as two of three clauses satisfied, not as met. The collapse diagnostic is not a matched peak-level comparison.

- **9 October, cluster: gate (d) pilot attempt 1 (40TopL, jobs 66286–66291) stopped before IG.** Test job 66273 had passed 71/71 on commit `3cc562b`. In all six pilot jobs the CUDA warm-up passed (NVIDIA GeForce RTX 3060, `batch`). The full unit-test discovery step that runs before IG then failed with 10 import errors, because the job's `PYTHONPATH` held `src/` but not `scripts/`. No IG ran and no gate (d) output was written. **Fix:** `scripts/` added to `PYTHONPATH` in `run_gate_d_pixel_count_ig.sh`. Nothing else changed.

- **9 October, cluster: gate (d) pilot attempt 2 (40TopL).**
  - CPU check 66292 ran the full test-discovery suite with `scripts/` on the path: 170 tests, OK.
  - IG jobs 66293–66298 all completed on `batch` RTX 3060 nodes. The CUDA warm-up passed and the test suite passed in each. The IG process took 7–15 s, with peak RSS ≤ 1.26 GB of the 8G requested.
  - Evaluation 66300 (uniform_mean) completed with exit 0, so its n = 12 reproduction gate passed. Its values were not read before this record was written.
  - Evaluation 66299 (central_only) stopped before scoring: "n=12: GMM assignment differs from production". No summary was written.
  - **Diagnosis, from the synced artifacts:** a pure relabelling. All three reruns (n = 12, 48, 192) found the identical segmentation: the same weights 0.419/0.350/0.231, and 0 of 4,686 pixels disagreeing after mapping production components {0, 1, 2} to rerun {0, 2, 1}. The latent means differ from production by at most 4.8e-7, from GPU floating-point differences, which was enough to change the order sklearn lists the components in. The attribution sampler walks the components in label order, sharing one seeded generator, so the swapped components drew each other's permutations. Their attribution pixels therefore differ from production. Component 0 kept its label, and its IG matches production to 6e-8 relative; components 1 and 2 differ by 15% and 25%.
  - **Status under the predeclared rules:** a run-validity check failed, so 40TopL central_only gets **no verdict**. The rule needs both sections, so the central_only arm cannot trigger a rerun. The check was not loosened.

- **9 October, cluster: gate (d) 40TopL with GMM label alignment (commit `3a9599d`).**
  - Test job 66324: 83/83 passed, none skipped. This includes the five script-level alignment tests and both evaluator refusal tests.
  - IG reruns 66325–66330 (both arms, n = 12/48/192, with `--align-gmm-labels-to-production`) all completed with exit 0 on `batch`. In each, the CUDA warm-up and the test suite passed and no alignment failure occurred. Peak RSS was ≤ 1.25 GB.
  - Evaluations 66331 (central_only) and 66332 (uniform_mean) both completed with exit 0. So both arms passed the run-validity checks and the n = 12 reproduction gate.
  - Values and the alignment permutations had not been read when this entry was written. The uniform_mean consistency check against `superseded_label_order/` is run after the local sync.

- **9 October, 14:56 UTC, cluster: superseded gate (d) attempt moved, not deleted.**
  - **Moved:** `results/diagnostics/gate_d_pixel_counts/40TopL_seed1/` (55 files) to `results/diagnostics/gate_d_pixel_counts/superseded_label_order/40TopL_seed1/`. The sorted file list is identical before and after the move.
  - **Contents:**
    - the central_only runs n = 12/48/192 (IG jobs 66293–66295) and the empty `evaluation/` folder left by the stopped evaluation 66299;
    - the uniform_mean runs n = 12/48/192 (IG jobs 66296–66298) and evaluation 66300.
  - **Reason superseded:** these runs were made without `--align-gmm-labels-to-production` (Section 6 amendment). The central_only reruns had swapped component labels and so a different attribution sample. The uniform_mean outputs are kept as the reference for the consistency check.
  - **Local copy:** already at the superseded path, and committed there in `88e6216` (55 files, the same sorted file list as the cluster). Nothing remains at the old local path.

- **9 October, local (after Zayd's sync): gate (d) 40TopL values read** from `results/diagnostics/gate_d_pixel_counts/40TopL_seed1/<arm>/evaluation/summary.json` (jobs 66331/66332). K_bin = 315 in both arms.
  - **Run validity:** n = 12 reproduction passed in both arms (identical bin set, 0 order differences, mSCF1 difference 0.0; saved mSCF1 0.6804 central_only, 0.6827 uniform_mean). Every component received exactly n attribution pixels, and each count's sample is distinct from the next smaller one.
  - **Label alignment:** central_only permutation {0→0, 1→2, 2→1} at every n (as diagnosed in attempt 2); uniform_mean identity. Production reference SHA-256 matched in all six runs.
  - **Uniform_mean consistency check** (`uniform_mean/consistency_vs_superseded.json`, `check_gate_d_uniform_consistency.py`): **passed**, maximum difference 0.0 over all 18 compared values (tolerance 1e-12). The aligned rerun reproduces the superseded unaligned uniform_mean evaluation exactly, as expected for an identity mapping.
  - **Change in mSCF1 at K_bin versus saved n = 12** (trigger: ≥ +0.02 on both sections for that arm):

    | Arm | n = 48 | n = 192 | Jaccard vs n = 12 (48 / 192) |
    |---|---|---|---|
    | central_only | −0.001 | **+0.024** | 0.795 / 0.805 |
    | uniform_mean | −0.008 | +0.003 | 0.853 / 0.848 |

  - **Descriptive, not gating:** IG − posterior-|PCC| at K_bin stays negative at every n (central_only −0.047/−0.048/−0.023; uniform_mean −0.062/−0.071/−0.059 for n = 12/48/192). IG runtime was 4–8 s per run.
  - **Descriptive, not gating (added after supervisor review, 9 October; no rule changed):**
    - The central_only n = 192 gain over n = 12 has the same sign and a similar size across budgets: +0.023 / +0.017 / +0.024 at 0.5 / 0.75 / 1.0 × K_bin. These budget-multiplier values depend on order, so they are descriptive only (this section, above).
    - IG − posterior-|PCC| is negative at 0.75 and 1.0 × K_bin in both arms at every n. At 1.5 and 2.0 × K_bin it lies between −0.004 and 0.000 (uniform_mean at 2.0 × is exactly 0.000). At 0.5 × K_bin it is **positive for central_only** (+0.033 / +0.050 / +0.056 for n = 12/48/192) and negative for uniform_mean (−0.019 / −0.032 / −0.031).
    - Bin-set change between counts: the Jaccard values correspond to 25–36 of the 315 selected bins (8–11%) differing from the n = 12 set.
  - **Consequence under the rule:** uniform_mean cannot trigger, whatever GBM108_positive shows. central_only n = 192 meets the threshold on 40TopL only, so that arm's outcome depends on GBM108_positive central_only. This is one development section, one seed, 0.004 above the threshold.

- **9 October, supervisor review of the 40TopL gate (d) result** (report `docs/meetings/supervisor_report_2026-10-09_gate_d_40TopL.md`; that folder is not versioned, so this entry is the record). The supervisor checked the report against the evaluation summaries, the 66324 test log and the consistency report, and approved it. Decisions:
  1. **GBM108_positive is approved, in stages, with Zayd's OK at each step.**
     - **Stage 1:** n = 12 for both arms. Check the run-validity checks and the reproduction gate, plus `sacct` runtime and memory, and report yes/no per arm. No gate (d) scores are read at this stage.
     - **Stage 2:** if central_only n = 12 reproduces, run central_only n = 48 and 192. Run uniform_mean n = 48 and 192 only if uniform_mean n = 12 reproduces. If it does not, that arm gets no verdict, as decided in Section 6 (no fallback).
     - **Then:** both evaluations, `run_gate_d_summary.sh`, and the decision table exactly as the rule gives it. Report back before anything else.
     - A timeout counts as a failed run. It is reported, not silently resubmitted. GBM IG runtime at n = 192 is untested under this code path (limits 4h / 4h / 8h).
     - **Staging needs a code change (proposed 9 October, for supervisor review; not committed or run).** The submitter always submitted all six runs, and the evaluator needs all three counts. Proposed change: `submit_gate_d_pixel_counts.sh --counts/--arms`, which refuses a count above 12 unless the arm's n = 12 record has status `passed`; and `run_gate_d_evaluation.sh SECTION ARM n12-only`, which runs a new `check_gate_d_n12_reproduction.py` that applies the evaluator's n = 12 run-validity checks and reproduction gate alone and writes `<arm>/n12_reproduction/summary.json`. The evaluator file is not modified, so its code hash, which is part of the campaign provenance the summariser compares, stays identical to the 40TopL evaluations. No rule, threshold or check changes. An arm stopped at stage 1 has no `evaluation/` summary and appears in the decision table as "missing", which gives no verdict.
  2. **Not stopping:** gate (d) is not reported as "central_only not resolved".
  3. **BIC is kept,** after the pixel-count result. The plan is drafted in Section 6 ("BIC run plan, draft") for supervisor review before any run.

- **9 October, 22:55, supervisor answer to the staging change and BIC plan** (chat `docs/supervision/supervisor_chat.md`; this entry is the record).
  - **Staging change approved as drafted.** Sequence: Zayd commits and syncs; `sha256sum` check against the commit; the cluster test job, in which the three new stage-1 tests must show as run and passed; stage 1; post yes/no per arm with `sacct` Elapsed and MaxRSS, no scores read; then stage 2.
  - **Watch-points:** the submitter's `grep '"status": "passed"'` depends on the `atomic_write_json` formatting, so switch to a `json.load` check if that format changes. A validity failure before scoring writes no `n12_reproduction/summary.json`, so stage 2 is refused for that arm, and the error text is posted to the supervisor.
  - **Staging code committed and checked (9 October):** commits `6ee2b1e` and `945836a`. All 59 tracked gate (d), pipeline, source and test files on the cluster match `HEAD` by `sha256sum`. Cluster test job 66389 (`batch`, mscluster121, 2 min 18 s) ran 86 tests, all passed, none skipped. That includes the three new stage-1 tests (pass without n = 48/192, fail with exit 4 then exit 3, refuse an unaligned run). No GBM108_positive gate (d) output existed before stage 1.
  - **Stage 1, cluster (9 October): both arms pass the n = 12 gate.**
    - IG n = 12: jobs 66390 (central_only) and 66391 (uniform_mean) completed with exit 0 on `batch` RTX 3060 nodes. Elapsed 7:09 and 7:15; IG process 252 s and 258 s.
    - In each job, the CUDA warm-up and the 185-test pre-run suite passed, and IG status was `valid`. Label alignment was the identity in both arms (max posterior difference 1.8e-6 and 3.0e-6).
    - Checks 66392 and 66393 exited 0 with status `passed`: the run-validity checks and the reproduction gate passed in both arms. **So the uniform_mean attribution-version-1 risk did not occur.**
    - `sacct` MaxRSS is not recorded for these jobs, and `seff` is unavailable, so peak memory is unknown; neither job exceeded 24G.
    - No gate (d) scores were read. Stage 2 is allowed for both arms.
  - **Stage 2, cluster (9 October, 23:10 SAST / 21:10 UTC):** IG jobs submitted with Zayd's OK via `submit_gate_d_pixel_counts.sh gbm --counts 48,192`: 66399 (central_only n = 48), 66400 (central_only n = 192), 66401 (uniform_mean n = 48), 66402 (uniform_mean n = 192). All four passed the CUDA warm-up.
    - At 23:17 SAST, also with Zayd's OK, the remaining steps were queued as `afterok` dependencies: evaluation 66404 (central_only, after 66399 and 66400), evaluation 66405 (uniform_mean, after 66401 and 66402), and summary 66406 (after 66404 and 66405).
    - A failure leaves the downstream jobs unrun; nothing is resubmitted automatically.
  - **Stage 2 and the chain completed (9 October, by 23:18 SAST / 21:18 UTC):** all exits 0. IG elapsed 5:56 (66399), 6:43 (66400), 6:27 (66401), 7:08 (66402). Evaluations 66404 (central_only) and 66405 (uniform_mean) took 25 s and 17 s, with status `complete` and empty `.err` files. Summary 66406 wrote `summary_66406/decisions.json`. No values have been read; they are read locally after Zayd's sync.
  - **Gate (d) decision table (read locally on 10 October after Zayd's sync; `results/diagnostics/gate_d_pixel_counts/summary_66406/decisions.json`): production n = 12 stands in every arm and count. No 16-section rerun is triggered.**
    - **Early exposure:** during the log check on 10 October, before the sync, Code opened the evaluation `.out` logs of 66404/66405. They print the per-n change at K_bin, and the 66406 `.out` prints the four verdict lines. This happened after all jobs had finished and changed nothing; the values below are taken from the synced artifacts. Note for later runs: these `.out` files are not status-only logs.
    - Change in mSCF1 at K_bin vs the saved n = 12 list (rule: trigger only if ≥ +0.02 on **both** sections for the arm):

      | Arm | n | GBM108_positive | 40TopL | Verdict |
      |---|---|---|---|---|
      | central_only | 48 | +0.0114 | −0.0011 | production n = 12 stands |
      | central_only | 192 | +0.0174 | +0.0243 | production n = 12 stands |
      | uniform_mean | 48 | +0.0048 | −0.0085 | production n = 12 stands |
      | uniform_mean | 192 | +0.0147 | +0.0031 | production n = 12 stands |

    - Evaluation status `complete` in all four section-arms. Distinct from the next smaller count: true for every n, section and arm. The campaign code hashes match across the four evaluations.
    - **GBM108_positive run validity** (`GBM108_positive_seed1/<arm>/evaluation/summary.json`): K_bin 584 in both arms. The n = 12 reproduction passed in both (identical bin set, mSCF1 difference 0.0; order differs at 2 positions in central_only, 0 in uniform_mean, which is not gating). Label alignment was the identity at every n, against production references `c5fd9472…` (central_only) and `d8eed7eb…` (uniform_mean). Attribution pixels per component equal n.
    - **The central_only n = 192 case** that depended on this section: GBM108_positive gives +0.0174, below +0.02, so the trigger is not met although 40TopL was +0.0243.
    - **Descriptive, not a verdict:** IG − posterior-|PCC| on GBM108_positive at K_bin (multiplier 1.0) is −0.184 / −0.172 / −0.166 (central_only, n = 12/48/192) and −0.172 / −0.168 / −0.158 (uniform_mean). It is negative at every n and every budget multiplier (range −0.222 to −0.052). Jaccard of the K_bin bin set vs n = 12 is 0.88 / 0.87 (central_only n = 48/192) and 0.88 / 0.86 (uniform_mean). IG process time at n = 12/48/192 was 252 / 252 / 300 s (central_only) and 258 / 269 / 306 s (uniform_mean).
    - Posted to the supervisor chat (10 October). Gate (d) work stops here until the supervisor reviews the table; BIC follows only after that review.
  - **BIC plan approved as the specification with changes**, now written into Section 6 ("BIC run specification"): no GPU IG at any BIC or forced K; an optional, labelled CPU posterior-|PCC| sensitivity with no trigger or verdict; results per section-arm only, with no arm or collection verdict; and BIC runs only after the GBM108_positive decision table has been reviewed.
  - **10 October, 09:45 SAST, supervisor confirmation of gate (d)** (chat entry of that time): the table and the four verdicts match `summary_66406/decisions.json` and both GBM108_positive `evaluation/summary.json` files; the `.out` disclosure is accepted. **Reported wording:** "Gate (d) attribution-pixel count: production n = 12 stands in both arms (no setting reached +0.02 on both development sections); no 16-section rerun; reported descriptively." Descriptive sentences, no verdict:
    - (a) On GBM108_positive, every larger count improved slightly (+0.005 to +0.017), more at n = 192 than at n = 48 in both arms. More attribution pixels give a small, consistent gain that stays below the practical threshold.
    - (b) That gain is about ten times smaller than the IG − posterior-|PCC| gap on the same section (−0.16 to −0.18 at K_bin). **Undersampled attribution pixels do not explain why IG trails the correlation ranking.**
    - BIC was approved to start under the Section 6 specification.
- **15 October (supervisor chat entry of 14:00 SAST): BIC and the S3PL CAC seed-2 control.**
  - **Code written, before any output** (no S3PL, BIC or sensitivity output existed; checked on the cluster):
    - BIC: `slurm_jobs/run_gate_d_bic.sh` (4 array tasks: GBM108_positive and 40TopL × central_only and uniform_mean) and `submit_gate_d_bic.sh` (input checks, refuses existing outputs, creates parent folders, `--parsable`). Each task runs the unchanged `select_gmm_k_bic.py` (selection version 2, `--production-k` 2 for GBM108_positive and 3 for 40TopL, `--seed 1`, `--n-init 20`), then the new `scripts/bic_segmentation_sensitivity.py` ("BIC-K segmentation sensitivity, descriptive", item b).
    - The sensitivity script computes nothing when BIC supports the production K. Otherwise it first rescores the saved production-K posterior-|PCC| (soft and hard) through the same code path and must match the gate (a)/(b) bin-level value to 1e-12, or it stops. It reports ARI and NMI only, with `verdict` and `trigger` null. Both scripts print status lines only; the outcome is read from the JSON after the sync.
    - Six new pipeline tests in `test_fair_scoring_pipeline.py` (refit check and no labels read; refusal outside Slurm; nothing computed at production K; production-K reproduction at another K; the best K ≥ 2 after K = 1; refusal of a BIC record made on another latent).
    - S3PL seed 2: `run_s3pl_cac_centre_control_seed2.sh` (16 array tasks: 0–7 real input, 8–15 tile-centre), `submit_s3pl_cac_centre_control_seed2.sh` (160TopL pilot, tasks 1 and 9, then the other 14 `afterok`; CUDA quarantine excluded) and the status-only `check_s3pl_cac_centre_control_seed2.sh`. **No S3PL code change:** the released `--initialization_seed 2 --sample_order_seed 1` flags are used, as in the GBM initialization screen, with `--number_peaks` set to the matched count. Artifacts go under `reproducibility/s3pl_cac_centre_control/seed2_init2_order1/`, because S3PL training names do not contain the seed, and a seed-2 real-input run in the default folder would have overwritten seed 1.
    - **Asymmetry recorded:** CAC seed 1 used the released code path (one global RNG for initialization and sample order). Seed 2 uses the controlled sample-order stream. The two seeds therefore differ in sample order as well as initialization; within each seed both arms share identical handling, which is what the paired rule compares.
  - **Outage (operational, not scientific):** the `batch` partition has been down since 2026-10-13 07:05 UTC (all nodes not responding, no reservation). Test job 68487, submitted on `batch`, could not start and was cancelled. With Zayd's OK and the supervisor's approval, the test job and BIC were moved to `bigbatch` by setting the partition at submit time (`--partition=bigbatch` / `SBATCH_PARTITION=bigbatch`); no script was changed. They are CPU-only, and the results do not depend on the node.
  - Before submission, the 21 files these jobs use matched the local copies by `sha256sum` on the cluster. Test job resubmitted on `bigbatch` as **68489**.
  - **Test job 68489** (`bigbatch`, mscluster89) completed with exit 0: **92 tests ran, all passed, none skipped**, including the six new BIC tests (`results/validation/fair_scoring_env_tests/68489_unittest.log`). It took 16:48 elapsed for only 3:51 of CPU, against 2:18 for 66389 on 9 October. The node or filesystem was slow; the code was not.
  - **Submitted on 15 October, 10:55 UTC / 12:55 SAST, with Zayd's OK:**
    - BIC array **68496** (tasks 0–3), with `SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_gate_d_bic.sh`. All four tasks started at once.
    - S3PL seed 2: pilot **68500** (tasks 1 and 9, 160TopL, both arms) and array **68501** (the other 14 tasks, `afterok:68500`), with `bash slurm_jobs/submit_s3pl_cac_centre_control_seed2.sh` on `bigbatch` as written, excluding the CUDA quarantine. The IDs are also in `reproducibility/s3pl_cac_centre_control/seed2_init2_order1/provenance/slurm_job_ids.txt`.
    - No outputs have been read. BIC and seed-2 results are read locally only after Zayd's sync.
  - **Completion (15 October):** all jobs exited 0.
    - BIC 68496_0–3 took 1:36 to 2:32, with empty `.err` files and status-only `.out` files.
    - Seed-2 pilot 68500_1/9, then 68501_0, 2–8 and 10–15, all on RTX 3090 nodes after the CUDA warm-up. There were no node failures and no retries.
    - `check_s3pl_cac_centre_control_seed2.sh` verified 16/16 without printing scores.
    - Zayd synced, and the values below were read locally afterwards. `scripts/build_current_evidence_tables.py` rebuilt every curated table, and all cross-checks passed.
  - **BIC result** (`results/diagnostics/gate_d_bic/`; `results/publication/current_evidence/gate_d_bic.csv`; descriptive, no verdict):
    - **BIC selects K = 6 in all four section-arms;** production K is 2 (GBM108_positive) and 3 (40TopL). All candidates converged, and the production refit ARI was 1.0 everywhere.
    - K = 6 is the upper end of the predeclared candidate set. BIC falls by at least 314 at each added component (the tie margin is 10), so the minimum lies at the boundary. The record says BIC does not support the production K, and that no minimum was found within K ≤ 6. Larger K was not predeclared and is not run.
    - "BIC-K segmentation sensitivity, descriptive" at K = 6: each run first reproduced the saved production-K posterior-|PCC| exactly. Then posterior-|PCC| at K_bin changed by −0.300 (GBM108_positive central_only), −0.299 (GBM108_positive uniform_mean), +0.001 (40TopL central_only) and −0.021 (40TopL uniform_mean).
    - ARI against labels fell from 0.56 / 0.64 / 0.43 / 0.62 at production K to 0.25 / 0.22 / 0.34 / 0.35 at K = 6. No IG was run.
  - **S3PL two-seed rule** (supervisor chat, 15 October, item 2; `s3pl_cac_seed_rule.json`): **supported.** Real beats retrained tile-centre by ≥ 0.02 in 8/8 sections in both seeds.
    - Seed 1: mean 0.591 versus 0.179 (+0.413). Seed 2: 0.591 versus 0.153 (+0.438).
    - The caveat stands (harder reconstruction target; not a pure information ablation), as does the sample-order asymmetry between the seeds.
  - **Cluster email:** Zayd's test job 68526 (`--mail-type=BEGIN,END`) completed, but no email arrived. The Slurm `MailProg` is `/bin/mail`, which is absent on the login node. Zayd decided not to use Slurm email; job tracking stays with `sacct` polling.
  - **Supervisor review (chat, 15 October, 15:30 SAST):** both results are confirmed.
    - **BIC wording:** "BIC does not support the production K; it selects the largest candidate (K = 6), with no minimum within the predeclared range; descriptive only. The production K equals the number of annotated classes, so the segmentation is label-free in training and ranking but class-informed in its component count." The last sentence is also added beside the fair-scoring results in the Results Record. The K = 6 sensitivity is not characterised further.
    - **S3PL:** "supported" under the two-seed rule, with both caveats (harder target; sample order differs between the seeds). It concerns S3PL's own training and does not explain the S3PL–VAE gap.
    - The 240TopL fresh-real drift is handled within each campaign; no action.
    - Nothing else is needed before the 19 October meeting. Zayd commits. There are no report or claim-map edits until Hairong has responded.
- **Final experiment round (supervisor chat, 15 October 13:00 and 13:30; Section 6.1). Work done locally on 15 October (SAST); nothing submitted.**
  - **B, runtime table (no new runs):** `scripts/build_runtime_and_training_curves.py` writes `results/publication/current_evidence/runtime_all_sections.csv`, with 66 rows: 16 sections × {VAE centre-only, uniform, attention, S3PL 10 epochs}, plus the two cached GBM108_positive reruns. Every row carries its timer boundary: the historical VAE production trainer streams HDF5 inside each epoch, the attention and cached runs load the section first and time that load separately, and S3PL times its training loop only, after building the patch dataset. The script checks that each `training_seconds` equals its summed per-epoch times, that every status is `complete`, and that the S3PL rows are the released seed-1 RNG path. All runs were on RTX 3090s. The GBM22_2 production VAE runs resumed at epoch 60 (recorded per row).
  - **C1, training curves (no compute):** the same script writes `training_curves_vae.csv` (16 sections × centre-only and uniform × 100 epochs; sample-weighted epoch-mean losses), `training_curves_s3pl.csv` (GBM108_positive initialization seeds 1 and 2 at 10/25/50 epochs, plus the 16 released seed-1 10-epoch baselines) and `training_curves.png`. The S3PL loss is the **last mini-batch MSE of each epoch** (the released `train_history`), not an epoch mean, and is labelled so. The untracked `seed2_init2_order1/run_logs/` were not needed and were left in place.
  - **A, pre-check: stopped before any code or run, for supervisor decision.** The 16 seed-1 real-attention models match the production arms in GMM settings (3 components on CAC and 2 on GBM, full covariance, `n_init` 20, seed 1) and in IG settings (12 pixels per component, 64 steps, sampling seed 1, selection seed 701), and every attribution is `valid`. **K_bin matches on all 8 CAC sections but on none of the 8 GBM sections.** The GBM attention peak evaluations used the pre-tuning counts (530/458/453/478/589/464/686/523), whereas production K_bin is 584/940/691/986/834/1028/695/911. The saved attention IG lists therefore cannot be reproduced at K_bin as item A requires (chat, 15 October 13:00). Posted to the supervisor chat with a proposed fix.
  - **Supervisor answer (chat 15 October 15:35):** A(a)–(c) approved as proposed (specification in Section 6.1). Both G readings confirmed, with a masked-query test added. The E audit extension, a separate `rcc_env` and C2 were approved, with C2 also logging the epoch-mean loss. B and C1 were accepted. **The GBM count mismatch is recorded here as found: no attention IG score at production K_bin had been computed or read when it was found.** Zayd approved `bigbatch` while `batch` is down and the `rcc_env` creation (15 October); the install was started on the login node at about 13:25 UTC.
  - **Supervisor code review (chat 15 October 15:51): the science code matches the specifications; three fixes made before any submission** (15 October, about 16:00 SAST / 14:00 UTC):
    1. **Dates.** The supervisor's three entries are dated 15 October (13:00, 13:30, 15:35), not 16 October. Experiments end **Tuesday 20 October**, and the RCC go/no-go is due by the **end of Friday 16 October**. Every reference in Section 6.1/10, `CLAUDE.md`, the new scripts, tests and job headers, and the S3PL `train.py` comment was corrected. Git Bash ignores `TZ=Africa/Johannesburg` and prints UTC; `TZ=SAST-2 date` or PowerShell `Get-Date` gives SAST.
    2. **`CLAUDE.md`:** the stale "Next" (no RCC, stopped until the meeting, the key still to fill in, an old uncommitted list) was replaced by a pointer to Section 6.1 and the four chat entries of 15 October, plus the agreed submission order.
    3. **Memory:** `run_fair_scoring_extra_arm.sh` is 32G → 8G, because the unchanged evaluator peaked at 0.91 GB (GNU time over all 32 tasks of 66053/66114). `run_rcc_feasibility.sh` is 32G → 8G, with no measured peak: `rcc.rda` is 24.8 MB compressed. Each justification is in its job header.
    - Re-run locally afterwards: `test_centre_masking`, `test_fair_scoring_arms` and `test_fair_scoring_summary`, 21 tests, all pass.
  - **Cluster check and first submissions (15 October; Zayd committed `496825d` and synced):**
    - **Checksums:** 36 of 37 round files (all new and changed code, plus the unchanged evaluator, its modules, the section list and the CUDA quarantine) match `HEAD` by `sha256sum`. The exception is `baselines/s3pl/test.py`. Its local working copy, and therefore the cluster copy synced on 8 October, has CRLF line endings that git normalises on commit. With CRLF converted to LF it is byte-identical to `HEAD`, so Python runs the same code; it was not changed.
    - **Test job 68616** (`bigbatch`, mscluster43, 5:26 elapsed): **119 tests ran and passed, none skipped**, including all of `test_fair_scoring_arms` (7), `test_centre_masking` (8) and `test_neighbourhood` (12). Log: `results/validation/fair_scoring_env_tests/68616_unittest.log`.
    - **A pilot 68620** (attention arm, GBM22_2; A(b) reproduction, then A(a) re-evaluation, then bin-level and approved-partition fair scoring) was submitted at 14:12 UTC / 16:12 SAST on `bigbatch` with Zayd's OK, after 68616 passed.
    - **A pilot result:** 68620_5 completed with exit 0 in 5:05 (mscluster43; `sacct` MaxRSS blank) and an empty `.err`. A(b) saved-list reproduction `passed`; A(a) re-evaluation at K_bin = 1028 complete; fair scoring `complete` in both scopes. No scores were read.
    - **Submitted at 14:19 UTC / 16:19 SAST with Zayd's OK:** A all **68621** (indices 0–4 and 6–15; GBM22_2 done in the pilot) and the G pilot **68628** (task 9, 160TopL G1, alone via `--indices 9`). The other 33 G tasks are submitted only after the pilot is checked and Zayd approves. The per-user QOS job limit queues the tasks.
    - **Submitted at 14:23 UTC / 16:23 SAST with Zayd's OK (`bigbatch`):** the E audit **68632** (array 0–3: 40TopL, 280TopL, GBM108_positive, GBM22_2; `AUDIT_WINDOWS="3 5 7 9"`, output `results/diagnostics/spatial_msipl_data_contract_windows/`, folder created before submission) and the RCC feasibility job **68633**. Neither had existing outputs. Zayd also approved, on condition the G pilot passes: the remaining 33 G tasks and C2.
    - **14:28 UTC / 16:28 SAST:**
      - **A all 68621:** all 15 tasks exit 0, every task `complete` in both scopes, with A(b) passed on every GBM section. No scores were read.
      - **G pilot 68628_9** (160TopL G1): exit 0 in 2:51. Training `complete`, IG `valid`, peak evaluation `complete`, mechanism check `valid`; the masking tests ran in the job (11 OK).
      - **G rest 68643** (33 tasks) was submitted as approved.
      - **C2 pilot 68644** (160TopL) was submitted. Its `afterok` array for the other 15 sections was **refused by the `bigbatch` QOS (`MaxSubmitPU` 48; `MaxJobsPU` 6 running)**, because G's 33 tasks were already queued.
      - A watcher submits the C2 remainder when the queue allows: with `afterok:68644` while the pilot is pending or running, or without it if the pilot has completed. It submits nothing if the pilot failed. The job IDs go to `reproducibility/s3pl_e100/seed1_released/provenance/slurm_job_ids.txt`.
    - **E audit 68632:** `valid` on 40TopL, 280TopL and GBM108_positive for windows 3/5/7/9; GBM22_2 was still running at 14:30 UTC.
    - **RCC 68633: recorded as no-go, but the no-go comes from Code's reading, not the data.**
      - It completed in 21 s. Criterion 1 (Cardinal 3.12.1 in `rcc_env`) and criterion 2 (`rcc.rda` loads: a legacy `MSImageSet`, converted through Cardinal, 16,000 pixels × 10,200 m/z, 8 runs) are met.
      - **All 8 runs have pixel-level cancer and normal labels** (81–793 pixels per class per run). Each also has 609–2,763 pixels with no diagnosis (NA).
      - `rcc_feasibility_export.R` counted a run as labelled only if it had **no** unlabelled pixels. That condition was Code's reading; the supervisor's criterion 3 asks only for pixel-level class labels on ≥ 4 sections. So nothing was exported, and criteria 3 and 4 were recorded false.
      - How to treat the NA pixels is a design decision, posted to the supervisor chat. The output in `results/validation/rcc_feasibility/` and the empty export folder stay as they are; any rerun needs them moved aside with Zayd's OK.
    - **15:14 UTC / 17:14 SAST:**
      - The watcher submitted the C2 remainder as **68675** (indices 0–8 and 10–15, `afterok:68644`, quarantine excluded).
      - **E audit 68632 passed on all four sections** (40TopL, 280TopL, GBM108_positive, GBM22_2): every task exit 0 and `status: valid` for windows 3/5/7/9. The E training specification can now be written.
      - G: 2/34 section-arms complete (160TopL and GBM108_positive G1; 68643_0 took 43:51).
    - **15:48 UTC / 17:48 SAST: node failure on mscluster72 (operational, not scientific).**
      - 20 tasks failed at the CUDA warm-up with "CUDA unknown error" and zero devices, after 2–30 s, before any data load or output: G 68643 tasks 15–33 and the C2 pilot 68644_9. All of them ran on mscluster72.
      - Meanwhile 10 G section-arms completed on other nodes and 4 were running. The C2 remainder 68675 was left at `DependencyNeverSatisfied`.
      - Following the standing rule (record the node, retry only the failed indices, within the runs Zayd approved): mscluster72 was recorded in `cluster_node_issues.txt` and added to the local `gpu_cuda_quarantine.txt` (the cluster copy changes through Zayd's next sync). 68675 was cancelled.
      - Resubmitted with mscluster72 excluded explicitly: **G retry 68717** (tasks 15–33), **C2 pilot 68718** (160TopL) and the **C2 remainder 68719** (`afterok:68718`). No specification changed.
    - **17:34 UTC / 19:34 SAST:** no new failures. G is 30/34 complete (all 16 G1 sections done; G2 GBM tasks 20–22 and G3 task 33 running). C2 pilot 68718_9 completed in 12:27; the remainder 68719 is running at the 6-job cap. A all 68621, E audit 68632, RCC 68633 and test job 68616 had all completed.
    - **Supervisor decisions, 15 October 19:37 (before any RCC export, any p5 score at K_bin, or any E output):**
      1. **RCC:** option (a), NA kept as a third class `unannotated` (Section 6.1 item D). **The first run's no-go was a reading error by Code**: `rcc_feasibility_export.R` counted a run as labelled only if it had no unlabelled pixels, which the criterion never required. The 68633 outputs (`results/validation/rcc_feasibility/` and the empty `/datasets/zsuliman/msi_data/rcc_cardinal/`) are to be moved aside, not deleted, and the job rerun with the corrected code, both with Zayd's OK.
      2. **p5 GBM at the old counts:** approved for the A(a)/(b) route. It was found from metadata before any p5 score at K_bin existed.
      3. **E rule:** confirmed, with P1 added alongside bin level so E matches A and G (Section 6.1). The supervisor implemented it in `window_rule()` and added `test_window_rule_requires_p1_as_well_as_bin_level`; Code re-ran `test_fair_scoring_arms` locally, 9/9 pass.
      4. **Go-aheads:** G1 fair scoring now; G2 and G3 fair scoring when their training finishes; the E pilot after the `sha256sum` check. Each still needs Zayd's OK.
      5. **Capacity:** the order is unchanged. If the 6-GPU cap makes E finish after Tuesday 20 October, the missing sections are reported as not done; G and C2 are not cut. C3 stays last and will probably be dropped, which is acceptable and will be recorded as such.
    - **Pre-submit check:** all 10 files from commits `bde92e6`/`7eda6df` matched on the cluster by `sha256sum` (`cluster_node_issues.txt` differs by CRLF only).
    - **Submitted with Zayd's OK at 18:02 UTC / 20:02 SAST:** **68800**, G1 fair scoring (`attention_centremask_p50`, indices 0–15, `bigbatch`, `--max-concurrent 2`), and **68801**, the E pilot (task 8, 40TopL `uniform_p7`).
    - **RCC rerun (commit `22ca398`; the 3 changed files matched on the cluster by `sha256sum`; the R script parse-checked in `rcc_env` on the login node):** with Zayd's OK, the 68633 outputs were moved aside, not deleted, to `results/validation/rcc_feasibility_superseded_68633/` and `/datasets/zsuliman/msi_data/rcc_cardinal_superseded_68633/` (empty). **68805** was submitted on `bigbatch` at about 18:15 UTC / 20:15 SAST.
    - **Overnight, 15–16 October (Zayd authorized Code at about 18:30 UTC / 20:30 SAST to resubmit failed tasks and submit the remaining approved jobs while he slept; no rule or specification changes):**
      - **About 21:15 UTC / 23:15 SAST:**
        - G1 fair scoring 68800 completed 16/16, every task exit 0.
        - The E pilot 68801_8 (40TopL p7) completed in 6:57 on mscluster43: CUDA warm-up passed, training finished, the checkpoint verified, and IG and peak evaluation ran ("complete").
        - G training is complete, 34/34. C2 has 14/16 complete, with 68719_5 and _6 running.
        - **RCC rerun 68805** completed in 4:56. The job log reports 8 exports audited and decision `go`. The details are read only after Zayd syncs.
      - **Submitted:** **68890**, G2 fair scoring (`uniform_centremask_p50`, 0–15, `--max-concurrent 2`), and **68893**, G3 fair scoring (`shuffled_attention_centremask_p50`, indices 5 and 9), both on `bigbatch`.
      - **Queued behind the `MaxSubmitPU` 48 cap:** an automated loop submits the E remainder (indices 0–7 and 9–31, `--concurrency 5`, leaving one running slot for CPU jobs) once at most 16 jobs are queued. It then submits the approved p5 A(a)/(b) route (`uniform_p5 all`). Each submit checks the job-ID file first, so a dropped connection cannot double-submit. The job IDs are recorded when they are issued.
      - **Issued by that loop:** **68900**, the E remainder (indices 0–7 and 9–31, at most 5 running), submitted 21:30 UTC / 23:30 SAST, and **68940**, p5 A(a)/(b) (`uniform_p5`, 0–15, at most 2 running), submitted 22:31 UTC / 00:31 SAST on 16 October.
      - **By 22:31 UTC:** C2 (68718, 68719) completed 16/16. G2 fair scoring 68890 completed 16/16 and G3 fair scoring 68893 completed 2/2, every task exit 0.
    - **16 October, 06:35 UTC / 08:35 SAST:**
      - p5 A(a)/(b) 68940 completed 16/16.
      - E: p7 is complete 16/16 (68801_8 plus 68900_0–15; GBM 2.3–5.1 h, CAC about 6 min). p9 has 1/16 complete (GBM 3.6 h, 1.55× its p7 counterpart), 5 running and 10 pending. The estimated end of E is about 14:00–14:30 UTC / 16:00–16:30 SAST.
      - **With Zayd's OK, submitted 06:40 UTC / 08:40 SAST:** **69076**, p7 fair scoring (`uniform_p7`, 0–15, `bigbatch`, `--max-concurrent 2`).
      - Zayd authorized p9 fair scoring once every p9 task completes, and resubmission of any failed tasks.
    - **16 October, 14:35 UTC / 16:35 SAST:**
      - **E is complete, 32/32.** p9 GBM took 4.1–8.2 h and CAC 7–10 min; every log ends "complete".
      - p7 fair scoring 69076: 16/16 exit 0.
      - **Submitted** under Zayd's standing OK: **69370**, p9 fair scoring (`uniform_p9`, 0–15, `bigbatch`, `--max-concurrent 4`; the GPU jobs are finished, so no slots need holding back).
      - **C3 was not run.** The remaining time goes to reading and logging the round, as the supervisor accepted on 15 October 19:37.
    - **16 October, about 14:54 UTC / 16:54 SAST:** p9 fair scoring 69370 completed 16/16. **Every job in the final round is now complete.** No scores have been read; reading waits for Zayd's sync.
    - **16 October, after Zayd's pull:** the pull reverted the edited `results/publication/current_evidence/README.md` to the older cluster copy, as on 15 October, and it was restored with `git checkout`. **RCC: GO** (Section 6.1 item D gives the outcome and the NA description).
    - **Decision table for A, G and E** (16 October, run locally on the synced JSON): `scripts/summarise_fair_scoring_arms.py --output results/diagnostics/fair_scoring_baselines/extra_arms/decisions_20261016_local/`. All summaries share one evaluator code hash per scope (the script refuses otherwise). A(b) saved-list reproduction **passed in 16/16** (attention and p5 on GBM). IG mSCF1 at K_bin; differences are mean, with positive sections out of 8, given as bin level / P1.
      - **A, attention vs uniform_mean:** GBM **equivalent** (+0.011, 6/8 / +0.010, 6/8); CAC **equivalent** (−0.006, 4/8 / −0.005, 2/8).
      - **G, rule 2:**
        - G1 vs attention: GBM label "mixed" (−0.039, 1/8 / −0.040, 1/8; that is, centre masking is **below** standard attention on 7/8 sections, but the rule has no "worse" category, so Section 7.1 wording applies); CAC **equivalent** (−0.007, 4/8 / −0.002, 3/8).
        - G1 vs G2: **equivalent** on GBM (−0.003 / −0.002) and on CAC (+0.009 / +0.016).
      - **G3** (descriptive, two development sections): G1 − shuffled = +0.021 on 160TopL and −0.011 on GBM22_2, so "real-context masked attention does not beat shuffled by ≥ 0.02 on both sections".
      - **G mechanism:** median normalised attention entropy 0.999 (160TopL) and 0.998 (GBM22_2) with masking, vs 0.999 and 0.982 unmasked. **Attention stayed near-uniform**, so masking did not make it selective.
      - **E, larger windows vs real 3×3:**
        - p7: GBM label "mixed" (−0.035, 2/8 / −0.032, 2/8; below 3×3); CAC **equivalent** (−0.007, 3/8 / −0.018, 1/8).
        - p9: GBM label "mixed" (−0.035, 2/8 / −0.034, 2/8; below 3×3); CAC **equivalent** (−0.007, 2/8 / −0.005, 2/8).
        - The confirmation-only figures (7 sections) agree in sign: GBM p7 −0.032, p9 −0.031.
        - p5 is descriptive: GBM −0.018 (3/8), CAC −0.006 (3/8).
      - **IG vs each arm's own posterior-|PCC|:** IG is below posterior in **every** extra arm and section: 0/8 positive in all 14 collection-arms. GBM ranges −0.22 to −0.29 and CAC −0.05 to −0.08. The label is the Section 7.1 fall-through "mixed / not resolved".
      - **Wording rule:** a "mixed" label here means "does not meet 'improves/helps'". Where the numbers are consistently negative, the record gives them as such (for example, "below 3×3 in 6/8 GBM sections, mean −0.035"). No verdict category is added after the fact.
    - **C2, S3PL 100 epochs** (read 16 October; descriptive, no verdict; `reproducibility/s3pl_e100/seed1_released/`). mSCF1 at the default count, epochs 10 / 25 / 50 / 100.
      - **Validation:** the epoch-10 checkpoint reproduces the existing 10-epoch mSCF1 in 16/16 sections to the third decimal, except 200TopL (0.671 vs 0.672, within the known GPU drift). The CAC matched-count values also reproduce.
      - **CAC mean:** 0.591 / 0.413 / 0.382 / 0.336. **GBM mean:** 0.316 / 0.212 / 0.209 / 0.212.
      - **10 epochs is the best of the four points in 15/16 sections.** The exception is GBM108_positive (0.033 at 10 epochs, about 0.16 later). So longer training lowers S3PL's score; it does not raise it. Reporting S3PL at its published 10 epochs does not handicap it.
      - The loss curves (last-batch and epoch-mean) are not yet tabulated.
    - **Supervisor, 16 October 17:36:** every round number confirmed against the saved artifacts. The wording rule was confirmed: report the result as labelled, numbers beside it, no new category. The RCC run specification was approved with conditions.
    - **RCC, 16 October, about 18:10–18:30 SAST / 16:10–16:30 UTC (nothing submitted):**
      - The specification was written into Section 6.1 (item D, step 2) before any RCC code existed.
      - The patient mapping was checked from the archive's documentation: 8 runs from 8 subjects (Section 6.1). Code read two text files from the verified archive on the login node; no data was read.
      - Code and tests written:
        - opt-in `--no-legacy`, `--reference-budget` and `--class-subset` in `evaluate_fair_scoring_baselines.py`, and `--no-legacy` in `evaluate_spatial_msipl_attributed_peaks.py`;
        - new `compute_reference_budget.py` and `summarise_rcc_fair_scoring.py`;
        - jobs `rcc_sections.sh`, `run_rcc_preparation.sh`, `run_rcc_campaign.sh`, `run_rcc_fair_scoring.sh` and `submit_rcc.sh`.
      - **Default path bit-identical:** `test_rcc_pipeline.py` (10 tests) runs both evaluators without the new flags beside frozen copies of the pre-change scripts (commit `6d889c1`, sha256 checked in the test) and requires identical summaries, CSVs and NPZ arrays, with legacy and with an approved partition; only runtimes and code hashes may differ. A deliberate one-line change to the oracle made that test fail, and the change was reverted.
      - Locally (Python 3.14.5, NumPy 2.4.4, h5py 3.16.0, sklearn 1.9.1): the 10 new tests and the 77 existing fair-scoring tests all pass, with none skipped. `test_rcc_pipeline` was added to `run_fair_scoring_tests.sh`.
      - **Note for any future rerun:** from commit `d35d063`, a STALE (exit 3) on a GBM/CAC fair-scoring or matched-evaluation result is expected. The evaluator code hashes changed when the opt-in RCC flags were added, and the default path is proven bit-identical by `test_rcc_pipeline`. It is not a fault, and the saved result stands (supervisor, 16 October 18:34).
      - **Consequence:** the two evaluators' code hashes change. Existing GBM/CAC results stay valid as saved, but rerunning one of them now reports STALE (exit 3) by design. All A–G scoring is complete, so no rerun is planned.

0. **9 October, cluster (after v3.1):**
   - Compatibility test job 66006 passed 47/47 under `s3pl_env` (Python 3.11.5, NumPy 2.4.6, sklearn 1.9.0).
   - Partition audit: pilot job 66012 (GBM22_2) and job 66013 (the other 15 sections) completed; GBM22_2 was correctly skipped on rerun.
   - P1 passes S1 in 16/16 sections (widest group 0.416 Da). P3 fails S1 in all 8 GBM sections (one 14.10 Da group of 43,285 bins) and passes on CAC, where both partitions are identical to bin level.
   - `results/diagnostics/peak_partition_audit/partition_approval.json` approves P1 for all 16 sections and P3 for the 8 CAC sections. It was drafted from the audited hashes (each recomputed from the saved arrays) and approved after Codex review.
   - **Noted limitation:** S1 does not detect over-splitting. GBM m/z 115.6–129.8 holds 51% of bins and 37% of P1 groups (median 7 bins, about 15 ppm), so one ion may span several groups there.

1. **9 October, cloud workspace: read-only code validation** on the saved GBM108_positive / uniform_mean artifacts:
   - the NumPy posterior reproduces the saved assignments (maximum difference 6.9e-7);
   - the rebuilt production IG and L2 rankings equal the saved 584-bin lists;
   - refitting the production GMM (K = 2, `n_init` 20, seed 1) reproduces the saved labels.

   No new scores were computed.
2. **9 October, cloud workspace: blinded BIC smoke run (quarantined).** `select_gmm_k_bic.py` was executed once on the same saved GBM108_positive / uniform_mean latents to check that the script ran.
   - It used `n_init` = 2 rather than the protocol's 20, and the earlier code version without the Slurm guard or provenance block.
   - Only the refit check (ARI 1.0) and `status: complete` were printed. The BIC values and the selected K were never displayed or read.
   - The output file was written to a scratch directory and **deleted immediately afterwards. That happened before the instruction not to delete it**, so the result cannot be recovered or audited.
   - It is a blinded code-validation execution, **not evidence**, and must not inform any decision. The protocol BIC run (`n_init` 20, under Slurm) will be the first and only result used.
3. No partition audit, fair-scoring, IG or other scoring run has been executed on any real section.
4. **9 October, cluster compatibility gate:** Slurm job 66006 ran the synthetic fair-scoring test suite under the production `s3pl_env` and passed 47/47 tests in 29.4 s. This validates environment compatibility only; it did not read or score a real section.

## 11. Files (implementation v3; nothing applied to production code or submitted)

| File | Purpose |
|---|---|
| `src/spatial_msipl/peak_groups.py` | P1/P3 partitions, structural audit, S1 hard rule with S2/S3 diagnostics, rule-A runs, K_peak selection, apex-based group references, group scoring, F1 ceiling |
| `src/spatial_msipl/simple_baselines.py` | NumPy GMM posterior, PCC against maps, Moran's I, production IG/L2 reconstruction, posterior-PCC rankings, **signed-PCC supervised oracle**, random draws, budgets |
| `src/spatial_msipl/provenance.py` | File/array hashes, provenance-checked restart, atomic writes, Slurm guard |
| `src/spatial_msipl/gate_d_helpers.py` | Production-preserving nested sampler; BIC selection with the K = 1 rule |
| `scripts/audit_peak_partitions.py` | Partition audit (`Data` and `mzArray` only); provenance block and stale-result refusal |
| `scripts/evaluate_fair_scoring_baselines.py` | Gates (a)/(b) per arm, with the strict IG, L2 and legacy reproduction, provenance, reconstruction files and stale-result refusal |
| `scripts/summarise_fair_scoring_baselines.py` | Decision table; refuses mixed provenance; no verdict below 8 sections; legacy collapse labelled as a diagnostic |
| `scripts/select_gmm_k_bic.py` | Gate (d) BIC on saved latents; Slurm guard and provenance |
| `patches/gate_d_attribution_total.patch` | **Applied 9 October** to `run_spatial_msipl_gmm_integrated_gradients.py`: opt-in `--attribution-total`; omitting it gives production behaviour |
| `slurm_jobs/run_gate_d_pixel_count_ig.sh`, `submit_gate_d_pixel_counts.sh` | Gate (d) GPU IG runs (n = 12/48/192) with the real CUDA warm-up, quarantine exclusions and retry; own output root `results/diagnostics/gate_d_pixel_counts/` |
| `scripts/evaluate_gate_d_pixel_counts.py`, `slurm_jobs/run_gate_d_evaluation.sh` | CPU evaluation per section and arm: production-GMM check, n = 12 reproduction gate (exit 4 on failure), K_bin and budget scoring |
| `scripts/summarise_gate_d_pixel_counts.py`, `slurm_jobs/run_gate_d_summary.sh` | Decision table: ≥ +0.02 on both development sections, per arm |
| `slurm_jobs/fair_scoring_sections.sh` | Shared ordered section list, input paths and pilot index |
| `slurm_jobs/run_fair_scoring_tests.sh` | `s3pl_env` compatibility test (synthetic data only) |
| `slurm_jobs/run_peak_partition_audit_array.sh`, `submit_peak_partition_audit.sh` | Partition-audit array on `batch` with 24 GB, plus its submitter |
| `slurm_jobs/run_fair_scoring_array.sh`, `submit_fair_scoring.sh` | Per-section scoring array on `batch` with 16 GB, plus its submitter |
| `slurm_jobs/run_fair_scoring_summary.sh` | Separate decision-table job |
| `slurm_jobs/check_fair_scoring_campaign.sh` | Login-safe status listing |
| Tests: `test_peak_groups.py`, `test_simple_baselines.py`, `test_gate_d_helpers.py`, `test_provenance.py`, `test_fair_scoring_pipeline.py` | 47 cluster-validated tests including the existing `test_peak_selection` and `test_evaluation`. They add the S1-only width test, the three-class oracle, strict legacy, stale and bare-summary refusal, tampered-hash refusal before scoring, peak-level reconstruction, and the Slurm guard |

**Removed:** the v2 single-allocation jobs `slurm_jobs/audit_peak_partitions.sh` and `slurm_jobs/evaluate_fair_scoring_baselines.sh` (untracked, never submitted).

**Cluster note:** production jobs run `unittest discover` over the tests folder, so these tests will also run there, adding about 40 s.

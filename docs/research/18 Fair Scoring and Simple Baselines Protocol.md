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
  - The budget is K_bin = |R@0.4| over all three classes, as specified. **Superseded on 16 October 19:47** (supervisor chat): K_bin = the released S3PL target, about |R@0.5| (item D, step 2).
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
  - **Budget (spec correction, supervisor chat 16 October 19:47, written before any RCC score existed):** **K_bin = the released S3PL target `num_GT_peaks[<run>]` from `baselines/s3pl/data_configs.py`**, the same convention as GBM/CAC, where the budget follows the released targets.
    - Weigand et al. 2026 (Section 3.2, Table 3) set the budget per collection at PCC 0.4 for GBM, **0.5 for RCC** and 0.3 for CAC. The released RCC targets equal our |R@0.5| over all three classes in 5/8 runs and lie within 13 bins otherwise.
    - The first |R@0.4| budget was an error: it was carried over from GBM, where 0.4 only coincides with the paper's choice.
    - Implementation: `compute_reference_budget.py --released-target-config baselines/s3pl/data_configs.py --released-target-key <run>`, output `released_target_budget.json`. The config is parsed as a literal, never executed. |R_t| at every threshold, our |R@0.5| and its difference from the target are recorded; |R@0.4| is descriptive only. Test: `test_released_target_budget_equals_num_gt_peaks_for_all_8_rcc_runs`.
    - The matched evaluation at this budget goes to `peak_evaluation_released_target/`, and fair scoring and the cancer/normal sensitivity use the same K_bin. Training, the GMM and the IG rankings do not depend on K_bin.
    - Superseded first version, kept as a record: K_bin = |R@0.4|, the size of the mixed reference set at PCC 0.4 over **all three classes**, computed with the existing nearest-threshold rule (`true_indices_at_threshold`) on the raw-intensity class PCCs (`scripts/compute_reference_budget.py`, output `results/experiments/rcc_spatial_msipl/<section>_seed1/reference_budget.json`). |R_t| at every threshold is recorded. The cancer/normal-only sizes are recorded descriptively and are **never** used as a budget.
  - **Structural audit:** the unchanged `audit_peak_partitions.py` (P1 and P3) into `results/diagnostics/peak_partition_audit_rcc/<section>/`.
- **Partition approval (condition 3):** P1 is used on RCC only if it passes S1 in all 8 runs. A reviewer then writes `results/diagnostics/peak_partition_audit_rcc/partition_approval.json` listing P1 alone with the audited hashes. If P1 fails S1 in any run, RCC is scored at bin level only and the record says so. **P3 is never used on RCC,** whatever its audit shows.
- **Step 2, training (GPU, one task per run-arm; 0–7 `central_only`, 8–15 `uniform_mean`):** `train_spatial_msipl_production.py` exactly as the CAC production arms: 3×3 window, 100 epochs, batch 128, hidden 512, latent 5, lr 1e-3, `spatial_lambda` 0, seed 1, checkpoint every 5 epochs. **Loader (runtime-only correction, supervisor chat 16 October 21:42):** the cached loader `--cache-spectra`, validated equivalent to streaming (investigation 10, jobs 61483/61484: identical loss histories and final tensors). The first text said "streaming loader (the runs are small)". That was Code's error: the RCC HDF5s are m/z-major like GBM, so streaming is very slow. All 16 run-arms train cached **from scratch**, so RCC has one loader and one timer boundary. The streamed attempts of pilot 69429 are cancelled and moved to `superseded_streaming/`, not deleted. The real CUDA warm-up runs first and the quarantined nodes are excluded. Root `results/experiments/rcc_spatial_msipl/<section>_seed1/<arm>/`; checkpoints `/datasets/zsuliman/msi_checkpoints/spatial_msipl/rcc/<section>_seed1/<arm>/`.
- **Step 3, GMM and IG:** `run_spatial_msipl_gmm_integrated_gradients.py` with the CAC settings: K = 3, `n_init` 20, 12 attribution and 32 faithfulness pixels per component, 64 steps, seed 1, sampling seed 1.
  - **Predeclared failure handling:** if a GMM component has fewer than 44 pixels (12 + 32), the IG script stops by design. That run-arm is then reported "not done: GMM component below 44 pixels", and no setting is changed. If the IG status is not `valid`, the run-arm is likewise reported as not done. Confirmed by the supervisor (16 October 18:34): no fallback, and no change of K, pixels or seed for any run. An arm with fewer than 8 runs gets "incomplete; no verdict", and its per-run differences are still reported descriptively, with n.
- **Step 4, matched evaluation:** the unchanged-by-default `evaluate_spatial_msipl_attributed_peaks.py` at `--matched-count` K_bin, with the new opt-in flag `--no-legacy` (legacy files are neither required nor read, and legacy rows are omitted). Without the flag, behaviour is unchanged.
- **Step 5, fair scoring (CPU, one task per run, both arms):** the fair-scoring evaluator, with all baselines and the oracle, at bin level and, only if approved, under P1.
  - New opt-in flags (each omitted on GBM/CAC, where the default path is unchanged):
    - `--no-legacy` with `--reference-budget FILE`: no legacy reproduction or legacy rows. K_bin taken from the saved matched evaluation must equal the budget file's K_bin, otherwise the run stops. The summary records "legacy msiPL not run on RCC (requires count tuning)".
    - `--class-subset 0 1`, used **only** for the secondary analysis below.
  - Output: `results/diagnostics/fair_scoring_baselines/rcc/{bin_level_only,with_approved_partitions}/<section>_seed1/<arm>/`.
- **Primary test:** posterior-|PCC| (balanced) vs IG under the Section 7 rules, per arm, over the 8 runs, at bin level and under P1 if approved. It is reported with the Section 7.1 wording and the 16 October wording rule (result as labelled, numbers beside it). A verdict needs all 8 runs of an arm; otherwise "incomplete; no verdict". The IG-vs-legacy rule is not applicable on RCC.
  - **Amendment, 17 October, made after the RCC results (supervisor chat 07:03 and 07:16; Codex review): the RCC verdict uses bin level only.** Reason: after the 19:47 budget correction, P1 on RCC no longer tests partitioning. Its groups are singletons, and peak-level scoring uses its own budget K_peak (≈ |R@0.4|), while bin level uses K_bin = `num_GT_peaks` (≈ |R@0.5|). So "P1 on RCC is singleton groups, so its peak-level score is the bin-level score at the K_peak budget (≈ |R@0.4|); it is a budget sensitivity, not an independent partition check; it does not enter the verdict." The P1 numbers stay in `decisions.json` and the tables, under `ig_minus_posterior_P1_budget_sensitivity`, with this sentence as the table footnote. They never count as a second scale for any reading. This supersedes the 19:27 note "P1 = bin level on RCC", which predates the budget correction.
    - **The verdict labels are unchanged by it** (checked on the regenerated output, not asserted): `central_only` stays "mixed / not resolved by the predeclared rule" (bin −0.156, 0/8 positive); `uniform_mean` stays "incomplete; no verdict (7/8 runs)". Every number is identical; only the P1 key, the P1 note and a `verdict_scale: "bin level only"` field change.
    - Tables: `decisions_20261017_local/` in `rcc/` and `rcc_cancer_normal_sensitivity/`. The committed `decisions_20261016_local/` folders are **superseded** (kept as a record); the raw evaluator outputs are untouched. Test: `RccVerdictScaleTests` in `test_rcc_pipeline.py` (bin level and P1 disagree; only bin level decides).
- **Secondary, descriptive (condition 2): "sensitivity, cancer/normal classes only".**
  - Same rankings and the same K_bin as the primary, with no re-budgeting.
  - With `--class-subset 0 1`, the reference sets, mSCF1, per-class metrics, the F1 ceilings, the oracle and (under P1) the reference groups use only the cancer and normal PCCs. Every pixel is kept and each class PCC is unchanged (class vs rest over all pixels).
  - The IG/L2/posterior reproduction checks still use all three classes, because they reproduce the saved all-class matched evaluation.
  - Output: `results/diagnostics/fair_scoring_baselines/rcc_cancer_normal_sensitivity/{bin_level_only,with_approved_partitions}/...`. It gets no verdict. Its table caption states that the oracle, the ceilings and the P1 reference groups follow the subset (confirmed by the supervisor, 16 October 18:34).
  - **Default path bit-identical:** a test shows that the evaluator without the flag gives the same summary as before the change, apart from runtime and code hashes, and that the subset equal to all classes reproduces the default scores.
- **Out of scope on RCC (condition 6):** attention, larger windows, centre masking and S3PL. Legacy msiPL is not run (condition 4).
- **Decision table:** `scripts/summarise_rcc_fair_scoring.py`. It refuses mixed provenance, reports per-run and per-patient values and the two disclosures, and gives no verdict for the sensitivity analysis.
- **Order (condition 7):** this specification → code and tests → Zayd sees the diff → cluster test job → preparation (8 CPU tasks), then the partition approval → 2-run pilot (UH9610_15, the largest at 3,564 px, and UH0710_33, the smallest at 972 px; both arms, 4 tasks) → the other 12 tasks → fair scoring → summary. Each `sbatch` needs Zayd's OK.
- **Cross-reference, 30 October:** RCC_UH0505_12 `uniform_mean` (seed 1, IG `needs_more_ig_steps` at 64 steps) is rerun at 128/256 IG steps from its saved checkpoint under the Section 6.3 amendment "30 October: IG completeness reruns" (Zayd's decision: complete results before the report). The RCC seed-1 decision is regenerated into a new folder; the 17 October tables stay as the record.

### 6.2 Test S: spatially regularised segmentation (supervisor chat 17 October 08:04, Zayd-approved; predeclared before any output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-17 08:04 Supervisor → Code: New predeclared test S". It was written into this protocol on 17 October before any Test S code was written or run. Later notes (Cardinal source check, implementation) are added below it, never inside it.

**Why.** Investigation 20: spatial information was tested at the encoder input (no benefit) and in the ranking stage (Moran's I strong), but never at the **segmentation** step, which is the component that carries the result. Zayd will show the outcome to Hairong on Monday as an update. This entry is the predeclaration. It is written before any output exists; copy it verbatim into protocol 18 as Section 6.2 "Test S" before running anything.

**S1, primary: structure-adaptive smoothing of the latent means, then the same GMM.**
- Input per run-arm: the saved production latent means and pixel coordinates (`attribution/latent_mean.npy`, `coordinates_and_gmm.npz`), the production K and the production GMM settings (StandardScaler, full covariance, `reg_covar` 1e-6, `n_init` 20, production seed and max_iter). No retraining, no new IG.
- Smoothing, following the adaptive spatial weighting of Alexandrov & Kobarg 2011 and Bemis et al. 2016 (Cardinal SSC "adaptive"): radius r = 1 (3×3 Moore neighbourhood over **measured** pixels only; missing neighbours are dropped, not zero-filled).
  - z̃_i = Σ_j w_ij z_j / Σ_j w_ij, over j ∈ N(i) ∪ {i}.
  - w_ij = α_ij · β_ij, with spatial weight α_ij = exp(−d_ij² / (2σ²)), where σ = (2r+1)/4.
  - Adaptive weight β_ij = exp(−‖z_i − z_j‖² / λ²), with λ = the median of ‖z_i − z_j‖ over all neighbour pairs in that run (data-driven, fixed by rule).
  - Standardise the latents with the production scaler **before** smoothing. Then refit StandardScaler + GMM on z̃ exactly as in production.
  - **Before implementing, check `σ` and the adaptive form against Cardinal's source in `rcc_env`.** If Cardinal's definitions differ, use Cardinal's and record both. If λ cannot be matched, keep the median rule above. Post what you found before running.
- Ranking: posterior-|PCC|, balanced (the same definition and round-robin as `posterior_abs_pcc_balanced`), computed from the **smoothed-GMM** posterior. Method name: `sa_posterior_abs_pcc_balanced`.
- Scoring: the existing fair-scoring evaluator, the same K_bin per run, the same references. GBM and CAC at bin level and P1 (the approved partitions); RCC at bin level only (the 07:16 amendment).
- Arms: `central_only` and `uniform_mean`, on all 24 sections/runs (GBM 8, CAC 8, RCC 8; RCC `uniform_mean` UH0505_12 stays "not done").

**Decision rule (per collection × arm), S1 vs plain posterior-|PCC|:**
- "Spatial segmentation helps": mean difference ≥ +0.02 **and** positive in ≥ 6/8 sections. For GBM/CAC this must hold at both bin level and P1; for RCC at bin level.
- "Equivalent": |mean| < 0.02 at every applicable scale.
- Otherwise "mixed (does not meet the 'helps' rule)", with the numbers reported. RCC `uniform_mean` (7 runs): "incomplete; no verdict"; numbers reported.
- No other variant, radius or λ may be substituted after seeing results.

**S2, descriptive only (no verdict):**
- **(a)** S1 against Moran's I.
- **(b)** Rank fusion: mean of the two per-bin ranks of posterior-|PCC| (balanced order) and Moran's I, ties broken by posterior. This tests the "complementary" idea in investigation 20.
- **(c)** Segmentation agreement: ARI between the smoothed and production GMM labels, and balanced accuracy of each against the expert mask (descriptive).

**Validity checks (refuse on failure):**
- The production GMM refit on the **unsmoothed** latents reproduces the saved labels (ARI 1.000), as in the BIC check.
- With λ → ∞ and σ → 0 (identity smoothing), S1 reproduces plain posterior-|PCC| scores exactly (unit test).
- Measured-pixel neighbour construction matches `evaluation.morans_i`'s Moore edges (test).

**Process:**
- New code: tests first (identity reproduction, neighbour construction, rule logic, refuse paths), then post a diff summary and leave it uncommitted for Codex. After Codex commits: upload, post the pre-submission checklist, run as CPU array jobs on `bigbatch` (one task per section/run, both arms), pull, and post a results entry: the per-collection table plus the verdicts, with S2 descriptive.
- Outputs go to new roots (`results/diagnostics/spatial_segmentation_S/…`); nothing existing is overwritten.
- Stop conditions as usual. Deadline: results by Monday 19 October 08:00 SAST for the meeting pack; hard stop Tuesday 20 October.

**Notes added after the predeclaration (17 October, before any Test S output existed):**
- **Cardinal source check** (supervisor chat 08:14). The `rcc_env` package is Cardinal 3.12.1 (and matter 2.12.0); the matching Bioconductor 3.22 source tarballs, with Packaged stamps identical to `rcc_env`, were read.
  - The neighbourhood (`findNeighbors`, `metric = "maximum"`, r = 1: 3×3 Moore over measured pixels, centre included) matches.
  - σ = (2r + 1)/4 = 0.75 matches; the spatial distance is Euclidean (diagonal √2).
  - **The adaptive weight differs.** Cardinal uses β_ij = exp(−‖z_i − z_j‖² / (2 s_i²)) with the per-pixel scale s_i = max_{j ∈ N(i) ∪ {i}} ‖z_i − z_j‖ / 2 + √eps. By the predeclared rule ("if Cardinal's definitions differ, use Cardinal's and record both"), **Cardinal's per-pixel scale is used**. The 08:04 global-median λ is recorded per run (`median_neighbour_distance_lambda_0804`) but not used.
  - Recorded, not changed: Cardinal applies these weights in a spatially weighted distance, not by smoothing the features. The predeclared design smooths the features and refits the unchanged GMM.
- **Implementation:** `src/spatial_msipl/spatial_segmentation.py`, `scripts/evaluate_spatial_segmentation_s.py` (one section-arm), `scripts/summarise_spatial_segmentation_s.py` (the rule), `slurm_jobs/{run,submit}_spatial_segmentation_s.sh` (24 CPU tasks, both arms each). The fair-scoring evaluator is not edited; its functions are imported.
  - Validity checks (refuse on failure): every input's sha256 equals the fair-scoring summary's record; the production GMM refit on the unsmoothed latents gives ARI exactly 1.0; the smoothing neighbourhoods give exactly the Moran's I Moore edges; plain posterior-|PCC| and Moran's I reproduce the saved mSCF1 to 1e-12 at bin level and (GBM/CAC) P1.
  - S2c balanced accuracy uses the existing `best_component_mapping` (accuracy-maximising permutation).
  - Tests: `test_spatial_segmentation.py` (25).
- **Observation sent to the supervisor (08:14), not a change:** on CAC, P1 is also singleton groups (1,481 groups for 1,481 bins; K_peak 70–239 against K_bin 133–315). So CAC "P1" is the bin-level score at the K_peak budget, as on RCC. The rule is implemented as written (bin level and P1 for CAC) unless the supervisor rules otherwise before results.

### 6.3 Test R: training-seed replication of the core arms (supervisor chat 17 October 09:45, Zayd-approved; predeclared before any output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-17 09:45 Supervisor → Code: New predeclared Test R". It was written into this protocol on 17 October before any Test R code was written or run. Later notes are added below it, never inside it.

**Why.** Every 24-section/run result of our own pipeline is seed 1. The only multi-seed evidence is targeted: GBM108_positive (3 seeds × 3 variants; per-section SD 0.013–0.019, about the size of the 0.02 threshold) and 160TopL/GBM22_2 (attention real vs shuffled). Zayd wants the core decisions checked across seeds on all three datasets before the window closes. This entry is the predeclaration, written before any output. Copy it verbatim into protocol 18 as Section 6.3 "Test R" before writing code.

**Design:**
- **Arms:** `central_only` and `uniform_mean`. **Training seeds 2 and 3.** All 24 sections/runs (GBM 8, CAC 8, RCC 8): 96 trainings.
- **Settings identical to the production seed-1 runs except the training seed** (model initialisation and sample order): 100 epochs, batch 128, hidden 512, latent 5, lr 1e-3, `spatial_lambda` 0, **cached loader**, CUDA warm-up, quarantine.
  - GMM: production K, `n_init` 20, and the **GMM seed fixed at 1**.
  - IG: the **attribution-sampling seed fixed at 1**, 12 px/component, 64 steps.
  - This follows the earlier targeted seed study (only training changes).
- **Scoring:** the existing fair-scoring evaluator at the same K_bin per section/run and the same references. GBM/CAC at bin level and P1; RCC at bin level only (the 07:16 amendment).
- **Outputs:** new roots for seeds 2/3 (`<section>_seed2/`, `<section>_seed3/`). Seed 1 is untouched. If the existing scripts hard-code `_seed1` in paths, change that only through a seed argument whose default reproduces the seed-1 paths, with a test.
- **Rules carried over:** an IG completeness failure makes that seed-arm "not done", with no setting change. A GMM component below 44 px stops IG by design. An arm with fewer than 8 sections at a given seed gets "incomplete" for that seed.

**Predeclared decisions** (per collection × arm, bin level; GBM/CAC also P1):
1. **Headline replication, IG vs posterior-|PCC|.** "Replicates at seed s" if IG is below posterior-|PCC| in ≥ 7/8 sections **and** the mean difference ≤ −0.02. The headline "IG is below its segmentation's correlation ranking" holds overall if it replicates at **both** seeds 2 and 3 in every collection × arm with a complete seed. Otherwise report exactly where it fails.
2. **Context, uniform − centre-only.**
   - Per section, average the three seeds (1–3), then apply the Section 7 rule to the 8 seed-averaged differences: "helps" if mean ≥ +0.02 and ≥ 6/8 positive; "equivalent" if |mean| < 0.02; otherwise "mixed".
   - Also report each seed's own label, and the per-section seed SD for each arm.
   - The seed-1 label (from the existing campaign) is **superseded** by the 3-seed label for the report. If they differ, report both, with the reason.
3. **Descriptive:** per-section seed SD of IG and of posterior-|PCC|; the GMM balanced accuracy per seed; and whether Moran's I vs posterior on RCC (5/8 at seed 1) holds per seed. Moran's I does not depend on the model, so only the posterior side changes.

**Out of scope (stated as a limitation in the report):** reseeding attention, windows, centre masking or Test S. Those remain seed-1 results, backed by the targeted 3-seed checks.

**Process:**
- New job scripts, plus a seed argument if needed. Tests first, including the default path being bit-identical for seed 1. Post a diff summary and leave it uncommitted for Codex. After Codex commits: upload, cluster test job, pre-submission checklist (time per run from the RCC and GBM cached runs, since GBM was about 23 min per training), submit.
- Order: **RCC and CAC first** (fast), **then GBM**. Stay within 6 running GPU jobs, and poll per the CLAUDE.md rule.
- Results entry: the tables for decisions 1–3, rule labels only, no interpretation.
- **Deadline: the end of Tuesday 20 October.** Any seed-arm not finished by then is "not done".

**Notes added after the predeclaration (17 October, before any Test R output existed):**
- **No existing script is changed.** Training already takes `--seed` (model initialisation and sample order); the IG, matched-evaluation and fair-scoring scripts run unchanged. Seeds 2 and 3 use new job scripts (`slurm_jobs/test_r_sections.sh`, `run_test_r_campaign.sh`, `run_test_r_fair_scoring.sh`, `submit_test_r.sh`), which refuse seed 1. So the seed-1 paths and defaults are untouched by construction, and no "default reproduces seed 1" switch is needed.
- **Calls:** the training and IG calls are the RCC campaign's, apart from `--seed SEED` (checked by a test that compares the command text). The GMM seed and the IG sampling seed stay at 1. Matched evaluation: GBM/CAC at the production K_bin with the legacy list (as the 15 October extra arms); RCC at the released target without legacy. Fair scoring: GBM/CAC at bin level and P1; RCC at bin level only, primary analysis.
- **Roots:** `results/experiments/test_r_training_seeds/<section>_seed<S>/<arm>/`, checkpoints `/datasets/zsuliman/msi_checkpoints/spatial_msipl/test_r/`, and fair scoring `results/diagnostics/fair_scoring_baselines/test_r/`. Each training task appends `node_record.json` (node, GPU model, CPU model) for the 09:48 runtime table. The training summary already records `training_seconds` and `dataset_load_seconds` (the cached HDF5 read).
- **Decision table:** `scripts/summarise_test_r.py`. Decision 2 uses IG mSCF1 at K_bin (and P1 matched K_peak), uniform_mean − central_only, the metric of the 15 October arm comparisons. The seed-1 label is computed from the seed-1 fair-scoring summaries. Seed SDs are sample SDs (ddof = 1). Tests: `test_test_r.py` (19).
- **Training phases (Codex review 10:11):** a single array does not order its tasks, so `submit_test_r.sh` submits `train-first SEED` (RCC and CAC, tasks 0–31), then `train-gbm SEED --after <first job>` (GBM, tasks 32–47, `afterok`). If a first-phase task ends in the predeclared "not done" (exit 4), `afterok` can never be met; then GBM is submitted with `--after-reviewed <first job>`, which only proceeds once `sacct` shows the first phase finished.
- **Disclosed differences from seed 1, which no setting can remove:**
  - the seed-1 GBM/CAC models were trained with the streaming loader (September); seeds 2 and 3 use the cached loader, validated equivalent in investigation 10 (identical loss histories and final tensors);
  - the seed-1 GBM `uniform_mean` attributions are IG `attribution_version` 1 (before the 20 September refactor `9f7408f`, which added the centre-only path and relabelled `valid_pilot` as `valid`); all other seed-1 attributions and all seed-2/3 attributions use version 2.

#### Amendment, 30 October: IG completeness reruns (supervisor chat 2026-10-30 12:58 item 1 and the 13:30 ruling; written into this protocol at about 13:35 SAST, before any rerun job was written, submitted or run)

**Decision:** Zayd's, 30 October: a complete-results requirement before the report (submission 11 November; an 8-page paper with no appendix must contain nothing that is or looks incomplete). This amendment changes the Test R carry-over rule "an IG completeness failure makes that seed-arm 'not done', with no setting change" and the matching RCC rule (Section 6.1) for the arms named below only. It is a separately labelled addition; no threshold, rule label, family or other setting changes.

**Item 1 as posted (verbatim, 12:58):**
- **Rule:** an arm that fails the completeness check at 64 steps is rerun **from its saved checkpoint** (no retraining) with the same GMM seed and sampling seed, at **128** steps. If it still fails, it is rerun at **256** steps. All other arms stay at 64. Record the median and 95th-percentile residuals at each step count.
- **Arms:**
  - RCC_UH0505_12 `uniform_mean`, seed 1;
  - RCC_UH0505_12 `central_only`, seed 2;
  - RCC_UH9912_01 `uniform_mean`, seed 3;
  - GBM39_2 `uniform_mean`, seed 3.
- **GMM check:** the rerun GMM must match the saved GMM wherever one is saved. If it does not, stop and post.
- **Step-count control (descriptive, so the methods can state that the step count does not change results):**
  - Rerun 4 **valid** arms at 128 steps into a **new** folder: RCC_UH0505_12 `central_only` s1, RCC_UH9912_01 `uniform_mean` s1, GBM39_2 `uniform_mean` s1, and CAC 40TopL `uniform_mean` s1.
  - Report, against 64 steps, the change in mSCF1 at K_bin and the Jaccard of the K_bin bin set.
- **Downstream regeneration, all into new output folders:** matched evaluation and fair scoring for those arms; RCC seed-1 decision; Test R Decisions 1 and 2; Test S RCC uniform; BIC RCC UH0505_12 `uniform_mean`; Test V seed means; Section 6.6 statistics, with families unchanged; the evidence tables.
- **Post the old and new labels side by side.** Labels may change, and that is fine: we report whatever the rule says.

**Implementation notes (13:23 plan, 13:30 ruling; fixed before any output exists):**
- **Why the four arms failed (saved summaries):** each fails only the 95th-percentile criterion (normalised residual ≤ 0.15): 0.175 (UH0505_12 uniform s1), 0.338 (UH0505_12 centre s2), 0.156 (UH9912_01 uniform s3), 0.189 (GBM39_2 uniform s3). Medians 0.0002–0.0007 (limit 0.05). The completeness criterion itself is unchanged.
- **IG call:** the campaign call unchanged (GMM K production, `n_init` 20, `--seed 1 --sampling-seed 1`, 12 px/component, 32 faithfulness px, internal batch 8) except `--ig-steps N` and `--align-gmm-labels-to-production <saved 64-step attribution folder>`. The step count that enters the decisions is the first that passes (128, else 256). If 256 also fails, the arm stays "not done".
- **GMM gate (13:30, answer 1):** `--align-gmm-labels-to-production` (refit hard assignment identical to the saved one under exactly one permutation, posterior within 1e-4; otherwise exit 5 before any output is written) **and** the recorded permutation must be the identity (a renumbering would change the seeded pixel sample). The job also requires the rerun `model_state_sha256` to equal the saved one. The maximum absolute differences of `latent_mean.npy` and `gmm_parameters.npz` against the saved files are reported descriptively. Any gate failure: stop and post.
- **Step-count controls (13:30, answer 2):** each control arm is rerun at **64 and 128** steps. Each 128-step control is reported against both the saved 64-step run and the rerun 64-step run (Δ fair-scoring bin-level IG mSCF1 at K_bin, and the Jaccard of the first K_bin bins of the IG ranking). Controls are descriptive and never enter a decision. **GBM39_2 `uniform_mean` s1** (saved IG version 1, the production seed-1 table value): report separately whether the 64-step rerun reproduces the saved K_bin set and mSCF1; if not (Jaccard < 1 beyond near-tie swaps, or |Δ mSCF1| > 0.005), post with the numbers and continue the item; the supervisor rules on the table value.
- **Roots (new; seed folders and checkpoints are only read):** `results/experiments/ig_steps_rerun_20261030/<section>_seed<S>/<arm>/steps<N>/` (failed arms), `results/experiments/ig_steps_control_20261030/<section>_seed1/<arm>/steps<N>/` (controls), each holding `attribution/` and the matched evaluation (`peak_evaluation_released_target/` for RCC without legacy at the released target, `peak_evaluation/` for GBM/CAC at the production K_bin with the legacy list); fair scoring under `results/diagnostics/fair_scoring_baselines/ig_steps_20261030/<scope>/<section>_seed<S>/<arm>/steps<N>/` (RCC bin level only, without legacy; GBM/CAC bin level and P1 with legacy).
- **Downstream (13:30, answer 3):** Test S RCC UH0505_12 `uniform_mean` and BIC RCC UH0505_12 `uniform_mean` rerun with their unchanged evaluators into new roots. The local summarisers (RCC seed-1 decision, Test R Decisions 1–2, Test S, Test V seed means, Section 6.6 statistics, evidence tables) run unchanged on a new dated composite root, assembled by copying (never moving) the unchanged arms plus the reruns, with a manifest of source path and SHA-256 per file. If a provenance check refuses the composite, stop and post; no patching.
- **Cluster:** GPU on `bigbatch` with the quarantine `--exclude` and without `--exclusive` (no timing from these runs enters the report; 13:30); CPU fair scoring on `batch`. Each `sbatch` needs Zayd's OK on its checklist.
- **Partition note, 30 October 14:08 (decision log D52):** `bigbatch` was overloaded, so all 12 first-round tasks were moved to `batch` (RTX 3060) at submit time. The saved 64-step runs were on `bigbatch` (RTX 3090).

**Gate correction after 78483 tasks 1/4/8 (30 October, supervisor rulings 14:46 and 14:54; Zayd's OK; written at about 15:00 SAST): the identity-permutation condition replaced by the direct sample/target check it stood for; the decision was made before any of these tasks was scored.**
- **What happened:** tasks 1, 4 and 8 (RCC_UH0505_12 `central_only`, s2 at 128 steps and the s1 controls at 64 and 128) exited 5 at the gate. Only `identity_permutation` was false. The model state was equal, the hard assignment was equal, and the built-in alignment (1e-4) passed. On the RTX 3060, sklearn listed the components in a different order, and the alignment renumbered them.
- **Why the condition was wrong:** it was added in the 13:23 plan as a proxy for "same seeded pixel sample". But the alignment runs before `choose_disjoint_samples` and reorders the GMM parameters, so the renumbering leaves the sample and the IG targets unchanged. The gate is about provenance, not scores. So this is a correction of a gate that tested the wrong thing, not tuning to an outcome.
- **Evidence before the correction** (local, read only, 14:53; chat table): for 12/12 tasks of 78483, these are identical to the saved 64-step run per component: hard assignment, attribution pixel indices, faithfulness pixel indices (rebuilt from the saved labels with the script's sampling function; the rebuild was validated against the saved attribution indices) and IG target per pixel. The aligned component means and covariances differ by ≤ 1e-6 (max 9.5e-7). No task had been scored.
- **Corrected gate (v2):** `model_state_equal` **and** `hard_assignment_equal` **and** the alignment check (exactly one permutation, posterior within 1e-4) **and**, per component, attribution and faithfulness pixel indices identical, the IG target identical, and the aligned component mean and covariance within 1e-6.
  - It is written as `gmm_gate_v2.json` next to each output; `gmm_gate.json` (v1) is never overwritten.
  - Fair scoring and the summariser read v2. Committed check: `scripts/check_ig_steps_gate.py`.
- **Consequences:**
  - tasks 4 and 8 get their missing matched evaluation as a CPU step on `batch`, with the unchanged Test R evaluator call; there is no GPU rerun of tasks 1, 4 or 8;
  - task 1 stays "needs more steps" at 128;
  - task 13 (256 steps) is submitted only after the v2 gate is committed, and its GPU job applies v2.

**Escalation beyond 256 steps (30 October, supervisor ruling 15:45, decision log D37; Zayd's OK; written at about 15:49 SAST, before task 13 was submitted or any 256-step result existed).**
- If RCC_UH0505_12 `central_only` s2 still fails completeness at 256 steps, it continues with the same doubling, **512, then 1024**. Each step uses the same IG call, the same gate v2 and one short checklist.
- **1024 is the cap.** Only if the arm still fails at 1024 is it reported as "not done (IG completeness not reached at 1024 steps)", with its residual trajectory (median and p95 at 64, 128, 256, 512 and 1024).
- The completeness criterion itself is unchanged (median ≤ 0.05 and p95 ≤ 0.15 of the normalised residual).
- **Implementation note:** the task table (`ig_steps_sections.sh`) currently ends at 256 steps (rows 12–15). 512 and 1024 rows for this one arm would be a small code addition (new rows appended, existing rows unchanged), committed by Codex before any such submission.

### 6.4 Test V: VAE segmentation vs a PCA segmentation (supervisor chat 17 October 12:42, Zayd-approved; predeclared before any output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-17 12:42 Supervisor → Code: New predeclared Test V". It was written into this protocol on 17 October before any Test V code was written or run. Later notes are added below it, never inside it.

**Why.** Codex's review (item 1) and the corrected update pack: we cannot claim the nonlinear encoder is needed, because no model-free segmentation was run through the same segment-then-correlate ranking. Zayd wants to test it. This entry is the predeclaration, written before any output. **The test can come out either way, and the report states whichever result occurs.** Copy it verbatim into protocol 18 as **Section 6.4 "Test V"** before writing code.

**Design (S = segmentation; everything after the segmentation is identical to the seed-1 fair scoring):**
- **Input:** each section's/run's centre spectra, through **exactly the preprocessing the VAE receives** (the same normalisation and scaling path as the production centre input). Verify against the training code and record the function names. Measured pixels only.
- **PCA-5 (primary):** PCA to **5 components** (= the VAE latent dimension), sklearn `PCA(n_components=5, svd_solver="randomized", random_state=1)`. Then the production segmentation step on the scores: StandardScaler, then GMM with production K, full covariance, `reg_covar` 1e-6, `n_init` 20, seed 1.
- **Ranking and scoring:** posterior-|PCC| balanced (the same definition and round-robin as `posterior_abs_pcc_balanced`) from the PCA-GMM posterior. The existing evaluator, the same K_bin and references. GBM/CAC at bin level and P1; RCC at bin level only.
- **Comparator:** the saved seed-1 **VAE `central_only`** posterior-|PCC| (the like-for-like single-spectrum input). VAE `uniform_mean` is reported descriptively.
- All 24 sections/runs. CPU only, saved data, new root `results/diagnostics/segmentation_control_V/`.

**Decision rule (per collection), VAE centre-only posterior-|PCC| minus PCA-5 posterior-|PCC|:**
- **"VAE segmentation helps":** mean ≥ +0.02 **and** positive in ≥ 6/8, at every applicable scale (GBM/CAC bin and P1; RCC bin).
- **"Equivalent":** |mean| < 0.02 at every applicable scale.
- **"PCA better":** mean ≤ −0.02 **and** VAE positive in ≤ 2/8, at every applicable scale. This is added because, unlike earlier tests, both directions are plausible here.
- **Otherwise "mixed".**
- No other number of components, preprocessing or clustering may be substituted after seeing results.

**Descriptive only (no verdict):**
- **(a) PCA-20:** the same pipeline with 20 components, to show sensitivity to the PCA dimension.
- **(b) Segmentation balanced accuracy** against the expert mask (`best_component_mapping`) for PCA-5 against the VAE.
- **(c) PCA-5 posterior-|PCC|** against Moran's I and IG.
- **(d) If Test R has finished:** the VAE side recomputed as the mean over seeds 1–3. This is reported next to, not instead of, the seed-1 verdict.

**Validity checks (refuse on failure):**
- The production GMM refit on the saved VAE latents reproduces the saved labels (ARI 1.0).
- Plain VAE posterior-|PCC| reproduces the saved mSCF1 to 1e-12.
- The preprocessing matches the VAE input (test on a synthetic section).
- PCA explained variance is recorded per section.

**Process:**
- Tests first; post a diff summary and leave it uncommitted for Codex. After Codex commits: upload, run the cluster test job, post the checklist, submit.
- The `bigbatch` QOS (48 submitted / 6 running per user) is shared with Test R, so submit as slots free up. **Test R keeps priority.** This is CPU-only, so throttle to at most 2 running.
- Results entry: rule labels and numbers only. **Deadline: the end of Tuesday 20 October**; anything not done is reported as not done.

**Notes added after the predeclaration (17 October, before any Test V output existed):**
- **Preprocessing, verified against the code:**
  - The VAE's centre input is the raw `Data` row read as float32 and passed through `spatial_msipl.preprocessing.tic_normalize`. That is the `target` returned by `H5SpatialContextDataset.__getitem__` (and its cached subclass); `CentralOnlyVAE.encode` receives it, and `run_spatial_msipl_gmm_integrated_gradients.encode_all` uses the same tensor.
  - No further scaling is applied before the first dense layer.
  - `segmentation_control.vae_centre_inputs` reproduces this for all measured pixels. A test checks it is element-for-element equal to the dataset's `target`, in both HDF5 layouts, for the streaming and the cached dataset.
- **GMM:**
  - `reg_covar` 1e-6 is sklearn's default and the production value (the production call does not set it).
  - The PCA scores are cast to float64 before `StandardScaler`, as in Test S's `fit_gmm`.
  - n_init 20 and seed 1 are fixed constants, not read from the section.
- **Comparator and references:** the seed-1 `central_only` fair-scoring summaries (`with_approved_partitions` for GBM/CAC, `rcc/bin_level_only` for RCC).
  - They supply K_bin, P1 and the input and artifact hashes.
  - They also supply the descriptive IG values. VAE `uniform_mean` is read from the matching `uniform_mean` summary; RCC_UH0505_12 has none (IG not done), so its value is None.
- Moran's I is also checked to reproduce its saved mSCF1 to 1e-12, as in Test S.
- **(d)** reads Test R's `central_only` fair-scoring results when both seeds 2 and 3 are complete for a section; otherwise it is left empty.

#### Addendum: PCA reconstruction error (supervisor chat 17 October 20:17, Zayd-approved; predeclared before any output exists)

- **New predeclared Test V addendum: PCA reconstruction error (written before any output exists).**
  - **Why:** the results draft may say "PCA-5 is simpler and reconstructs worse, yet gives equivalent peak ranking." Test V saved only PCA explained variance, which can't be compared with the VAE's saved MSE. This must be measured, not assumed. PCA-5 is the MSE-optimal rank-5 linear map, and the VAE is trained on cross-entropy, so either outcome is possible.
  - **Inputs and PCA:** exactly as Test V (protocol 18 Section 6.4). The same `tic_normalize` on raw `Data` as float32, measured pixels only, and `PCA(n_components=5 and 20, svd_solver="randomized", random_state=1)`, fitted on all pixels of each section. All 24 sections.
  - **Reconstruction:** `inverse_transform` of the scores.
    - **Primary:** MSE, MAE and cosine similarity on the raw reconstruction.
    - **Secondary:** the same three metrics after clipping at 0 and re-applying TIC, to match the VAE's "after decoder TIC normalization" convention.
    - Before writing code, the builder confirms from the VAE evaluation code that MSE and MAE are averaged in the same way (over all pixel × feature entries) and states this in the chat.
  - **Comparison:** against the saved VAE values (`evaluation/comparison.json`: centre-only and uniform-mean), for GBM (`spatial_msipl_reconstruction`) and CAC (`spatial_msipl_cac_reconstruction`). RCC has no saved VAE reconstruction, so its PCA values are reported alone, with no comparison.
  - **Validity:** the explained-variance-ratio sum reproduces the saved Test V value within 1e-6 in every section, or that section is "not done".
  - **Cluster run:** CPU only, `batch`, a job script based on `run_segmentation_control_v.sh`. New root `results/diagnostics/pca_reconstruction_V/`. No new mSCF1 scoring; Test V's scores are reused.
  - **Reporting (descriptive, no decision rule):**
    - per section, the PCA-5, PCA-20 and VAE MSE/MAE/cosine;
    - per collection, the number of sections where the PCA-5 MSE exceeds the centre-only VAE MSE;
    - the median ratio of PCA-5 MSE to VAE MSE.
  - **Wording, fixed now:**
    - If the PCA-5 MSE is higher in at least 6 of 8 sections in both GBM and CAC, under both the primary and the secondary metric: "PCA-5 reconstructs worse than the VAE yet gives equivalent peak ranking."
    - Otherwise: "Reconstruction error does not separate PCA-5 from the VAE," and the "reconstructs worse" claim is dropped.

### 6.5 Test N: S3PL retrained with shuffled nonlocal neighbours, CAC (supervisor chat 17 October 13:04, Zayd-approved; predeclared before any output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-17 13:04 Supervisor → Code: New predeclared Test N". It was written into this protocol on 17 October before any Test N code was written or run. Later notes are added below it, never inside it.

**Why.** The S3PL control (retrained centre-tiled: 0.179 / 0.153 vs real 0.591) removes all neighbour information and makes the patch target unattainable. It shows that S3PL fails without neighbour input. It does **not** show that S3PL needs *spatially correct* neighbours. Our VAE claims rest on a shuffled-neighbour control, so S3PL needs the same kind of control before we can contrast the two. This entry is the predeclaration, written before any output. Copy it verbatim into protocol 18 as **Section 6.5 "Test N"** before writing code.

**Design:**
- **CAC, all 8 sections. Two seeds, using exactly the same seed and RNG conventions as the existing centre-tiled control**: seed 1 on the released code path (global RNG), seed 2 on the controlled sample-order stream.
- **The only change from the "real" S3PL runs:** at training **and** inference, every non-central position of each p×p input patch is replaced by the spectrum of a nonlocal measured pixel.
  - Fixed global permutation π of measured pixels, seed 1701, the same construction as the VAE `shuffled_p3` arms.
  - The neighbour of pixel i at offset o is replaced by π(that neighbour); missing positions are handled as in the real runs.
  - The centre spectrum stays real.
  - The reconstruction target is the input patch, as in S3PL. So the target here is the shuffled patch. Record this.
- **Settings:** released CAC settings (p = 9, z = 256, d1 = 51, d2 = 1, 10 epochs, batch 16, lr 1e-2, `reference_spatial_max`).
- **Scoring:** the matched peak count, exactly as `s3pl_cac_controls.csv` (`matched_peaks`). Outputs go to new roots.

**Decision rule (per seed, then both), real minus retrained-shuffled:**
- **"S3PL depends on spatially correct neighbours":** ≥ 0.02 on ≥ 7/8 sections **and** mean ≥ 0.02, in **both** seeds. This is the same thresholds as the existing centre-tiled rule.
- **"Not spatially specific":** |mean| < 0.02 in both seeds.
- **Otherwise "mixed"**, with per-section values.

**Descriptive:** retrained-shuffled against retrained centre-tiled (does any neighbour input rescue training?), and against mean intensity at the same count.

**Validity checks:**
- A test shows the shuffle leaves the centre unchanged and that π is a permutation of measured pixels.
- The real-arm seed-1/seed-2 scores reproduce the saved `real` column.
- The default S3PL path stays bit-identical (test).

**Process:** tests first; diff summary; uncommitted for Codex. After commit: upload, cluster test, checklist, submit. 16 short GPU runs.

**Cluster priority** (shared `bigbatch` QOS of 48 submitted / 6 running): (1) the Test R jobs already queued keep running; (2) **Test V next** (CPU, the most important for interpretation); (3) Test N; (4) the remaining Test R seed-3 submissions; (5) ranking-stage timing last.
**Deadline: the end of Tuesday 20 October.** Anything not finished is reported as not done.

**Notes added after the predeclaration (17 October, before any Test N output existed):**
- **Shuffle construction:**
  - The map is the VAE `shuffled` construction (`mapping[order] = roll(order, 1)`, `order = default_rng(1701).permutation(n)`; one n-cycle, so no pixel maps to itself).
  - The source walk is also the VAE's: start at `mapping[j]` and move on while the candidate lies in the pixel's own window.
  - For S3PL the window is the 9×9 patch, so every source lies outside the patch. The VAE `shuffled_p3` arms excluded their own 3×3 window. With a 3×3 exclusion, sources could fall inside S3PL's 9×9 patch and would not be nonlocal.
  - The map uses its own generator and draws nothing from the global NumPy RNG (tested).
- **CAC runs read imzML through m2aia:**
  - m2aia fills each unmeasured window position with a random measured pixel of the same window (global RNG), and pads border windows with random repeats.
  - Test N keeps that construction, so the global RNG stream is identical to the real run (tested). It then maps every non-central slot through the shuffle.
  - "Centre" is the central slot exactly as the released code fills it. For border pixels m2aia's padding can put another pixel there; that quirk of the released code is unchanged.
  - On every call, the re-derived real index list is checked to reproduce m2aia's own patch; any mismatch stops the run.
  - The HDF5 path keeps unmeasured positions empty, as in its real runs.
- **Target:** the input patch, i.e. the shuffled patch. It is recorded in each run's config (`reconstruction_target`, `neighbour_shuffle_seed` 1701). This differs from the centre-tiled control, which kept the real-patch target.
- **The "real" values** are recomputed from the saved `metrics.json`: seed 1 from the `_matched_<count>peaks` runs, seed 2 from `s3pl_cac_centre_control/seed2_init2_order1`. They reproduce the saved `real` column exactly in 16/16 (checked before any Test N run).
- **Mean intensity (descriptive)** is the fair-scoring bin-level value at K_bin. K_bin equals the S3PL matched count in every CAC section. It uses a different scorer and representation (TIC-normalised HDF5 bins), and is labelled so.
- **Default path:**
  - `build_patch_dataset` and `H5SpectrumPatchDataset` without the new argument are tested bit-identical to a frozen copy of the pre-change `data_source.py`.
  - The m2aia default branch is unchanged.
  - Training and inference call the patch builder exactly as before for `none` and `tile_centre` (tested on the cluster, where torch is installed).

### 6.6 Stats: predeclared statistical-analysis plan, saved results only (supervisor chat 20 October 10:28, Zayd-approved; predeclared before any test output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-20 10:28 Supervisor → Code | Codex | Zayd: Title correction; predeclared statistical-analysis plan (Section 6.6 "Stats"), saved results only" (the title correction in that entry is not part of the plan). It was written into this protocol on 20 October at 10:39 SAST, before any statistics code was written or run. The comparison family is listed in the chat and confirmed by the supervisor before anything is computed. Later notes are added below it, never inside it.

- **Statistical-analysis plan, predeclared before any test output exists.** Copy it verbatim into protocol 18 as Section 6.6 before writing code. It is analysis of saved per-section results, run locally. The existing practical labels ("helps", "equivalent", …) stay unchanged; the tests are reported **beside** them, never replacing them.
  1. **Paired comparisons:** every rule-labelled comparison in the family (protocol 18 Sections 6–7 and Tests S, V, N, R; Code lists the family, about 20, in the chat before computing anything). For each:
     - n;
     - the exact two-sided Wilcoxon signed-rank p (`scipy.stats.wilcoxon`, exact method; zero differences reported, `zero_method="wilcox"`);
     - the Hodges–Lehmann median paired difference with an exact distribution-free 95% CI (Walsh averages);
     - matched-pairs rank-biserial r;
     - the sign count;
     - a Holm-adjusted p across the whole family.
  2. **Units:**
     - Average the training seeds per section before testing when 3 seeds exist (Test R arms); otherwise use seed 1.
     - GBM is also reported at PDX-line level: average the 2 sections per line, n = 4, so the minimum attainable two-sided p is 0.125. This must be stated.
     - CAC is one biopsy: its tests are within-specimen. RCC is 8 subjects.
     - Development sections are excluded wherever the original comparison excluded them.
  3. **Mann–Whitney U, only for independent groups.** Per-peak quality of the *selected* bins of two rankings, e.g. each selected bin's maximum |PCC| with any class mask, for IG vs posterior correlation within each section. The selected sets aren't paired. Report U, p, and the common-language effect size per section, plus a per-collection summary with no pooled p.
     - Code first checks whether per-bin mask correlations are saved locally. If they aren't, this item is "not done" and must not trigger new cluster work without a separate OK.
  4. **Mixed model (descriptive):** score ~ method + (1 | section) [+ (1 | seed) where seeds exist], per collection, for IG vs correlation and VAE vs PCA-5. Report the fixed-effect estimate and its 95% CI. No model selection; if it fails to converge, report "not converged".
  5. **Output:** `results/diagnostics/statistics_6_6/` (`tests.csv`, `mann_whitney.csv`, `mixed_models.csv`, `summary.json` with provenance and input hashes). Tests use known toy data (e.g. a hand-checked Wilcoxon/HL case).
- **Wording rule, fixed now:**
  - p-values describe these sections, not a population.
  - With n = 8 the smallest possible p is 0.0078, and with n = 4 it is 0.125.
  - A comparison is called "statistically supported" only if the Holm-adjusted p < 0.05 **and** the practical label is "helps" (or its opposite). Otherwise the practical label stands alone.
- **Scope:** no retraining and no new scoring. The optional random-list chance baseline is *not* part of this plan.

#### Addendum: comparison family and Holm families by question (supervisor chat 20 October 10:46; predeclared before any statistic was computed)

Written into this protocol on 20 October at 10:47 SAST, before any statistics code existed. It records the family Code proposed (chat 10:39) and the supervisor's confirmation with one amendment (chat 10:46). The original plan above is unchanged.

- **Family (bin level; each difference signed as in its rule, first − second; n = sections the rule used):**
  - Rows 1–6: IG − posterior-|PCC| (Section 7; Test R Decision 1; RCC primary). GBM, CAC, RCC × `central_only`, `uniform_mean`. Seed mean 1–3.
  - Rows 7–10: IG − legacy msiPL (Section 7). GBM, CAC × both arms. Seed 1.
  - Rows 11–13: IG `uniform_mean` − `central_only` (Test R Decision 2). GBM, CAC, RCC. Seed mean 1–3.
  - Rows 14–15: attention − uniform IG (item A). GBM, CAC. Seed 1.
  - Rows 16–19: G1 − attention, G1 − G2 (item G rule 2). GBM, CAC. Seed 1.
  - Rows 20–23: G1 IG − posterior, G2 IG − posterior (item G rule 3). GBM, CAC. Seed 1.
  - Rows 24–27: p7 − 3×3, p9 − 3×3 IG (item E). GBM, CAC. Seed 1.
  - Rows 28–33: S1 − plain posterior-|PCC| (Test S). GBM, CAC, RCC × both arms. Seed 1.
  - Rows 34–36: VAE `central_only` posterior − PCA-5 posterior (Test V). GBM, CAC, RCC. Seed 1, with the seed mean reported beside.
  - Rows 37–38: S3PL real − retrained shuffled-nonlocal (Test N). CAC, seed 1 and seed 2 separately.
  - **Excluded:** gate (d) pixel count (n = 2), G3 (2 sections), the G mechanism (not a paired score), BIC, C2 and p5 (no rule), the RCC cancer/normal sensitivity (no verdict), Test V (a)–(d) and the PCA reconstruction addendum (descriptive), and the Test N descriptive contrasts. No development section is excluded, because every listed rule used all 8 sections.
- **Amendment (Q1): Holm families by research question, not one family of 38.** With exact Wilcoxon at n = 8 the smallest attainable p is 0.0078, so Holm's first step can be cleared only when k ≤ 6. One family of 38 could never give "statistically supported", whatever the data.
  - **F1, primary ranking:** rows 1–6. **F2, vs legacy:** rows 7–10. **F3, encoder context and variants:** rows 11–27. **F4, segmentation:** rows 28–36. **F5, S3PL:** rows 37–38.
  - Holm is applied within each family, and unadjusted p is also reported. `summary.json` records per family k, the Holm first-step threshold, and whether that threshold is attainable at the family's n.
  - Report wording: with 8 sections, only a family of ≤ 6 tests can reach Holm significance, so effect sizes and CIs carry the weight, and p-values are supporting evidence.
- **Q2:** bin level is primary. P1 (GBM/CAC) is secondary, with its own Holm within the same family structure.
- **Q3:** seed means use only sections with all 3 seeds (as Test R Decision 2); the reduced n is shown.
- **Q4:** each test uses the unit of the predeclared label it accompanies: rows 1–6 and 11–13 the seed mean (3-seed Test R labels); rows 34–36 seed 1, with the seed mean beside.
- **Q5:** GBM PDX-line tests (n = 4) are reported beside each GBM row, outside the Holm families.
- **Q6:** item 3 (Mann–Whitney) is "not done" as specified. Per-bin mask PCCs are saved locally only for the IG- and L2-selected bins, not for the posterior-selected bins. IG vs L2 is not substituted. A CPU job for the posterior-selected bins would need its own specification.
- **Q7:** mixed models use statsmodels `MixedLM` (local uv environment only). Every model is labelled descriptive, and singular or boundary fits are flagged.
- **Zero differences:** counted and reported, together with what the installed scipy does with them under `method="exact"`.

### 6.7 Investigation 21: S3PL GBM reproduction gap and seed sensitivity (supervisor chat 20 October 10:53, Zayd-approved scope; predeclared before any new output exists)

The predeclaration below is copied verbatim from the supervisor chat entry "2026-10-20 10:53 Supervisor → Code | Codex | Zayd: New predeclared Investigation 21: S3PL GBM reproduction gap and seed sensitivity (parts A–D, Zayd-approved scope)". It was written into this protocol on 20 October at 11:42 SAST, before any Investigation 21 code was written or run. The investigation document is `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`. Later notes are added below it, never inside it.

**Why.** Our S3PL GBM is 0.30–0.34 (3 seeds) against the published 0.496. The gap is systematic (in 7/8 sections the published value is above all our seeds), and single sections swing hugely between seeds (GBM108_positive: 0.026 / 0.444 / 0.079). The supervisor asked us to explain statistically what causes the gap and why seeds change the result. Known candidate causes:
- (1) initialisation and seed luck, including best-of-N reporting;
- (2) the components of the seed (weight init, data order, GPU nondeterminism);
- (3) preprocessing: the paper says TIC, but the released helper normalises by the per-spectrum maximum;
- (4) tuned-on-test hyperparameters in the paper (investigation 19). This is reported, not tested.

**First, verify and post (code facts, no runs):**
- what S3PL's seed actually sets (torch init, DataLoader shuffle, patch sampling, numpy/python RNG, cuDNN flags);
- whether per-run peak lists and the training loss are saved for GBM seeds 1–3 and CAC seed 1;
- the exact GPU time per run from the saved records.

**A. Saved data only (no compute):**
- variance decomposition per collection: score ~ (1 | section) + (1 | seed), reporting section, seed and residual variance shares;
- per-section seed SD;
- top-K Jaccard overlap of the selected peaks between seeds, if the lists are saved;
- final training loss vs mSCF1 across seeds, per section (descriptive, n = 3).

**B. Seed distribution (GBM and CAC, as reproducing contrast):** S3PL with the released protocol unchanged (10 epochs, published p and z, native peak count, our scorer), **seeds 1–10** on all 8 sections of each. Reuse saved seeds 1–3 only if the code facts show a fixed seed reproduces bit for bit; otherwise rerun them. Report:
- per-section mean, SD, min and max;
- collection mean ± SD across the 10 seed-level collection means;
- the per-section percentile of the published value within our 10 seeds.

Predeclared questions and labels:
- **B1, consistency:** where the published collection mean sits against our 10 seed-level collection means. Label "inside our seed distribution" if it is ≤ their maximum, otherwise "outside our seed distribution".
- **B2, best-of-k:** per section, the expected maximum over k seeds (exact, from all k-subsets of the 10), averaged over sections, for k = 1…10. Report the smallest k at which it reaches the published mean. Label "consistent with per-section best-of-k selection (k = …)" if k ≤ 10, otherwise "not explained by seed selection alone".
- **B3:** the same for CAC (published 0.601).

**C. What part of the seed matters (3 GBM sections with the largest seed SD in the saved seeds 1–3, chosen now from saved data; Code names them):** a small S3PL change gives separate RNG streams for (i) weight init and (ii) data order, with the production default **bit-identical** (a test is required).
- **Arm "init varies":** 5 init seeds, data order fixed.
- **Arm "order varies":** 5 order seeds, init fixed.
- **Arm "repeat":** the production seed 1 run 3 times, to measure the nondeterminism floor.
- Report the per-section SD of each arm. A component is "dominant" if its SD is ≥ 2× the other's in ≥ 2 of the 3 sections. If the repeat SD is ≥ half the smaller arm's SD, the conclusion is "dominated by nondeterminism".

**D. Preprocessing:** GBM, 8 sections × seeds 1–3, with true TIC normalisation in place of the released max-normalisation helper; everything else unchanged. Use the seed-mean per section, paired against the released-helper seed-mean. Label:
- **"explains the gap"** if the TIC collection mean is ≥ 0.446 (within 0.05 of 0.496);
- **"partly"** if it rises by ≥ +0.05 but stays below 0.446;
- **"does not explain"** otherwise.
- Section 6.6-style statistics (Wilcoxon, Hodges–Lehmann CI) are reported beside the label.

**Rules:**
- Cached data where the S3PL loader allows it, `batch` for CPU scoring, GPU quarantine respected, and new output roots only.
- Each arm needs the pre-submission checklist and Zayd's OK. Order: A, then D and B, then C.
- All outcomes are reported, including "not explained".
- (4) is discussed in the report and not tested.

#### Addendum: correction note and answers to Q1–Q6 (supervisor chat 20 October 11:46; written before any Part B, C or D output)

Written into this protocol on 20 October at 11:54 SAST. The verbatim text above is unchanged.

- **Correction:** the released helper `reference_spatial_max` normalises by the maximum over a *spatial* axis of the `(1, D, p, p)` patch, not per spectrum. Part D's question is unchanged: the paper's stated TIC normalisation (`paper_tic`) against the released helper.
- **Q1:** Part B uses the released `random_seed` 1–10 (the paper's protocol). The initialisation-screen numbers quoted above are controlled runs and are described as such.
- **Q2:** reuse of saved released runs is approved behind a gate. B, C and D run on RTX 3090 nodes. The GBM12_2 released seed-1 repeat runs first. If it is bit-identical to job 53121 (all losses, mSCF1 and the peak-list SHA-256), saved released runs are reused; otherwise every saved run in B is rerun. The outcome is reported either way.
- **Q3:** B1–B3 and D use S3PL's own in-job mSCF1 (the metric of the published 0.496 / 0.601), stated as S3PL's evaluator, not the fair-scoring one.
- **Q4:** D runs as specified. Its label carries: "seed 1 existed before the predeclaration (0.289 vs 0.316) and was seen during the inventory; seeds 2–3 are blind." The cut-offs stand.
- **Q5:** C runs as specified. Disclosed: GBM108_positive's initialisation and order pattern was largely visible from saved runs. C's new information is GBM108_negative, GBM12_2 and the repeat arm. A bit-identity test of the default path for the opt-in seed flags (`3624b56b`) is added before any C run.
- **Q6:** Part A now is "preliminary" (GBM: initialisation screen; CAC: released seeds 1–3; the different seed modes are stated). After B, the same analysis on released seeds 1–10 is the primary decomposition. New descriptive item for A and B: a per-section bimodality check (seed-score plot and the largest gap between sorted scores). Any bimodality wording waits for the data.
- **Order:** Part A (local); the GBM12_2 repeat gate (1 GPU run); B and D; the rest of C. At most 3 GPU tasks running at once, quarantine excluded, new output roots only, and the pre-submission checklist before each submission.

#### Clarification: Part C aggregation (supervisor chat 20 October 21:11; written into this protocol on 21 October at 08:58 SAST, before any Part C output exists)

This records the supervisor's confirmation of Code's reading posted at 21:06 (Codex finding 1, 21 October 08:55). It clarifies the Part C rule and does not change it. The verbatim text above and the committed summariser (`3877fab4`) are unchanged.

- **Nondeterminism counts** if the repeat SD is ≥ half the smaller arm's SD in **at least 2 of the 3 sections**. Per-section values and the bit-identity check are reported beside it.
- **A repeat SD of 0 never counts** toward nondeterminism.
- **An SD of 0 never makes a component dominant.**

### 6.8 msiPL Beta re-tune (supervisor chat 2026-10-30 12:58 item 2 and the 17:33 ruling; Zayd-approved; written at about 17:40 SAST, before any re-tune code was written or any re-tuned list existed or was scored)

**Decision:** Zayd's, 30 October: a complete-results requirement before the report (decision log D10, D28). This section fills the empty RCC msiPL cell and makes the third clause of "IG beats legacy" (Section 7; Section 7.1 gap 2) assessable. It is a separately labelled analysis. No threshold, rule label or Holm family changes.

**Item 2 as posted (verbatim, 12:58):**
- **Why RCC is empty:** the RCC count is not reachable on the current grid. At Beta 0.0, 6/8 runs fall short (for example MH0204_33 gives 1,154 against 2,200).
  - The sweep flattens near 0 (1,151 → 1,154), because `LearnPeaks` keeps only local maxima of the mean spectrum.
  - A wider grid (Beta from −2.0 to 2.5, step 0.01) should find msiPL's **maximum attainable count**. This is a property of msiPL, not an incompleteness.
- **Targets:** round(K_bin × m) for m ∈ {0.5, 0.75, 1, 1.5, 2}, on GBM, CAC and RCC, with the existing tolerance of 50.
  - If a target cannot be reached, use msiPL's maximum count and label it `msipl_cap`.
- **Consistency check:** m = 1 on GBM/CAC must reproduce the saved legacy lists and scores exactly (to 1e-12). If it doesn't, stop.
- **Scoring:**
  - Score every legacy list with the fair-scoring evaluator. Then assess the budget-stability clause of "IG beats legacy" with the existing Section 7.1 rule, as written.
  - On RCC, also score **every ranking** at msiPL's own per-run count, so the main table has a count-matched RCC msiPL comparison wherever the target is capped.
  - RCC msiPL rows are **descriptive, outside Holm**. The predeclared families stay as they are.

**Answers fixed at 17:33, before any re-tuned list exists:**
1. **m = 1 on GBM/CAC is the saved list,** because it defines K_bin.
   - The consistency check recomputes `LearnPeaks` at the saved Beta (`beta_selection.json` → `chosen.beta`) from the restored weights. It must reproduce the saved `learned_peaks.csv` exactly (identical m/z array), and the scorer must reproduce the saved legacy scores (integer TP/FP/FN at every threshold; mSCF1 to 1e-12). Otherwise: stop and post.
   - m ≠ 1 is re-selected on the new grid. **RCC m = 1 is re-selected** like the other multipliers.
2. **Comparator: count-matched.** For every re-tuned list, its snapped unique-bin count n_m is the budget. Legacy msiPL and every ranking are scored at exactly n_m, at bin level, with all classes.
   - Rankings are rebuilt with the fair evaluator's own functions over all bins (not truncated). Before scoring, the scorer must reproduce: the saved GMM posterior; the saved IG and L2 lists at K_bin (exact ties only); IG and L2 mSCF1 at K_bin (1e-12); and the first 2 × K_bin entries of every ranking in the saved `rankings_prefix.npz`. Otherwise it stops.
3. **Clause 3 ("ordering stable across the budget multipliers"), operationalised here before any re-tuned list is scored.**
   - For each collection × arm on GBM and CAC (the scope of clauses 1–2), clause 3 is met if IG mSCF1 > legacy mSCF1 in **≥ 7/8 sections at every m ∈ {0.5, 0.75, 1, 1.5, 2}**, both scored at n_m.
   - Capped (`msipl_cap`) points are included, because they are count-matched anyway, and flagged.
   - "IG beats legacy, robust to scoring" is reported as met only if clauses 1, 2 and 3 are all met. RCC stays descriptive.
4. **RCC main-table cell:**
   - per run, the m = 1 re-selected list (capped where the target is unreachable) at its unique-bin count n;
   - legacy msiPL vs IG, posterior-|PCC|, mean intensity, variance, Moran's I and the oracle, all at n, at bin level;
   - descriptive, outside Holm.
   - The main table shows legacy at n, with a footnote giving the median n against K_bin and the count-matched IG and correlation values.
5. **Seeds:** IG seed 1, both arms (as for clauses 1–2).
   - The RCC_UH0505_12 `uniform_mean` seed-1 IG is the 128-step rerun (Section 6.3 amendment, 30 October), with its matched evaluation and fair scoring from `ig_steps_*_20261030`.

**Implementation notes (fixed with the code, before any output):**
- **Sweep:** `scripts/retune_msipl_beta.py`, env `msipl_legacy` (Python 3.6). It reuses `LearnPeaks`, `VAE_BN`, `load_dataset` and `tic_normalise` from `run_msipl_legacy_gbm.py`, as the existing tuner does.
  - Grid: −2.0 to 2.5, step 0.01 (451 values), built by the existing `beta_grid`.
  - Per m: target = `int(round(K_bin × m))`, the expression of `simple_baselines.budgets`, with the labels "0.5", "0.75", "1.0", "1.5" and "2.0".
- **Selection rule (unchanged from `tune_msipl_massnet_beta.py`):** the closest raw learned-peak count to the target, with ties going to the larger Beta. Status is `within_tolerance` if |count − target| ≤ 50.
  - Otherwise, if the target is above the grid's maximum count: the Beta with the maximum count (ties to the larger Beta), status `msipl_cap`.
  - Otherwise (the target lies within the grid's count range but no count is within tolerance, or the target is below the minimum count): the closest count, status `closest_outside_tolerance`, flagged.
- **Count used for scoring:** the snapped unique-bin count n_m (`nearest_unique_indices`), as in the fair evaluator. The raw count is recorded beside it.
- **Scorer:** `scripts/score_msipl_retune.py` (s3pl_env). It imports the fair evaluator's functions. The production evaluator is **not** changed, so its code hash and every saved result stay valid.
- **Roots (new):**
  - `results/baselines/msipl/retune_20261030/<collection>/<section>/` (sweep CSV, and per m `learned_peaks.csv` plus `selection.json`);
  - `results/diagnostics/fair_scoring_baselines/msipl_retune_20261030/<section>_seed1/<arm>/`.
  - Saved msiPL folders and `/datasets` are read only.
- **Cluster:** cluster test job → GBM22_2 pilot (time and MaxRSS) → the other 23 sections → scoring. CPU on `batch` unless the pilot shows more than 30 GB. No `--exclusive`. Each `sbatch` needs Zayd's OK on its checklist.

**Implementation note, 30 October about 21:55 SAST: sweep fast path (supervisor ruling 21:51; Codex commit `c625f52a`). This is an implementation change, not an analysis change.**
- **Why:** the first GBM22_2 pilot (78796) could not finish in its 4 h limit. Legacy `LearnPeaks` recomputes per Beta its Beta-independent steps. The costliest is the nearest local maximum of each learned bin, found against a Python list. Measured locally at GBM size: about 10 s per Beta at 2.5, rising to about 127 s per Beta at 0 and below.
- **Change:** `SweepLearnPeaks` in `retune_msipl_beta.py`.
  - Once per section, by the legacy expressions: the per-unit weight order, sorted values, and their mean and std; the local maxima; and every bin's nearest local maximum (argmin, first index on ties).
  - Per Beta: only the threshold `mean + Beta × std`, the union across units and the unique step.
  - `baselines/msipl/LearnPeaks.py` is unchanged and is still used for the m = 1 reproduction.
- **Identity:**
  - Tests: arrays and dtypes are identical to `LearnPeaks` at all 451 grid values in three synthetic cases (float64, float32, equidistant-m/z ties). `test_msipl_retune` 23/23, run locally and independently by the supervisor.
  - In the job, on real data: the fast path is compared with `LearnPeaks` at Beta 2.5, the saved Beta (GBM/CAC), 0.0 and −2.0. Any difference writes `fast_path_check.json` and exits 5. `summary.json` records the check.
- **Unchanged:** grid, targets, tolerance, tie rule, `msipl_cap`, saved-list handling, roots and scorer.
- **The timed-out 78796 folder** (only `retune_stdout.log`) is moved with `mv -n` to the sibling `GBM22_2_78796_timeout`, kept as a record, before the pilot is resubmitted.

**Implementation note, 30 October about 23:20 SAST: scorer prefix gate and RCC node (Codex commit `199cb276`; Zayd's overnight approval). The gates are exact as before; no rule, threshold or grid changes.**
- **Legacy entry:** on GBM/CAC the fair evaluator stores the snapped legacy msiPL list as `legacy_msipl` in `rankings_prefix.npz`, beside the rankings. The first scoring run (79025) stopped because the gate treated it as a ranking. The gate now requires that entry to equal the snapped m = 1 re-tune list exactly, and refuses it when no m = 1 list is supplied (RCC). Every ranking prefix is still checked exactly.
- **RCC node:** the saved RCC fair-scoring rankings come from 69565 on `bigbatch`, and exact reproduction is CPU-specific. Any RCC run whose prefix gate fails on `batch` is rescored on its 69565 node (`--nodelist`, from `ranking_stage_runtime_rcc_bigbatch/provenance/task_node_map.txt`), as with the 17 October option (a). The gate is not relaxed. The 4 runs that passed on `batch` (UH0505_12, UH9610_15, UH9812_03, UH9905_18) stand.
- **Amendment, 31 October (Zayd's ruling 07:2x):** the node need not be the 69565 node itself, only one with the same CPU model (Intel i9-10940X). MH0204_33 and UH9911_05 were rescored on mscluster79 and passed the exact gate. The 4 runs above were rescored with the fixed scorer, giving identical numbers (only the code hash and runtime differ), so all 48 section-arms carry one scorer code.

### 6.9 C3 training length (supervisor chat 2026-10-30 12:58 item 3, 13:20 Zayd's approval, 20:16 request 4; Codex review 2026-10-31 07:31; written 31 October about 07:50 SAST, before any snapshot model, score or loss comparison exists)
**Question (descriptive):** how do the IG and posterior-|PCC| rankings change with VAE training length, and where does the training loss level off? This supports the 100-epoch choice with the same kind of evidence the report gives for S3PL (C2). **No epoch is chosen on mSCF1** (D20g). Whatever the result, the production 100-epoch runs and every result built on them stay as they are.

**Fixed scope:**
- **Sections:** the two development sections GBM108_positive and 40TopL only (not confirmation evidence).
- **Arms:** `central_only` and `uniform_mean`. **Seed:** 1.
- **Epochs scored:** 10, 25, 50 and 100.
- **Training:** the production recipe (3×3, 100 epochs, batch 128, hidden 512, latent 5, lr 1e-3, spatial λ 0, seed 1) with the cached loader (`--cache-spectra`, mandatory for training jobs). The run is retrained once, saving opt-in `snapshot_epoch<NNN>.pt` at epochs 10, 25 and 50 (`train_vae(snapshot_epochs=...)`; saving only reads state). Epoch 100 is the run's final checkpoint.
- **Per epoch:** the production GMM (K = 2 GBM, 3 CAC; `n_init` 20; GMM seed 1) and IG (64 steps; 12 pixels per component; sampling seed 1), with `--expected-epochs E` (default 100 unchanged). Then the matched evaluation at the production K_bin (584 for GBM108_positive, 315 for 40TopL) with the legacy list, and the unchanged fair evaluator at **bin level, all classes**. Reported per epoch: **IG and posterior-|PCC| (balanced) mSCF1 at K_bin**.
- **Loss:** `total_loss`, `reconstruction_loss` and `kl_loss` for every epoch 1–100, from this run's `training_history.json`. The production runs' saved histories are shown beside it, descriptively.

**Epoch-100 reproduction rule:** the epoch-100 rerun must give the production seed-1 fair-scoring IG and posterior-|PCC| mSCF1 to 1e-12 **and** identical ranking prefixes for both, per section and arm. If it does not, the section-arm is reported as **"epoch 100 not reproduced"**: its epoch 10/25/50 numbers are shown only with that label, and nothing about it is described as a training-length effect.
- **Caveat stated in advance:** the GBM108_positive production model was trained with the streaming loader. The cached loader was validated as equivalent (investigation 10) but is not proven bit-identical, and the GPU node can differ. Non-reproduction is a possible outcome, not a fault.

**Not done:** a GMM component under 44 px, or an IG status other than `valid`, makes that epoch "not done" for that section-arm, with no fallback and no setting change; the other epochs continue. A missing epoch is never interpolated.

**Implementation** (code reviewed by Codex 07:31, no defect found): `slurm_jobs/training_length_sections.sh`, `run_training_length.sh`, `submit_training_length.sh`, `scripts/summarise_training_length.py`, and the opt-in flags in `training.py`, `train_spatial_msipl_production.py` and `run_spatial_msipl_gmm_integrated_gradients.py`. Tests: `test_training_length.py`; the 2 Torch tests must run and pass in the cluster test job before any campaign.
- **Roots (new):** `results/experiments/training_length_20261030/`; `/datasets/zsuliman/msi_checkpoints/spatial_msipl/training_length_20261030/` (checkpoints, written only by the campaign); `results/diagnostics/fair_scoring_baselines/training_length_20261030/bin_level_only/`.
- **Cluster:** `bigbatch` (RTX 3090, as production), 4 CPUs, 48G, 8 h, no `--exclusive`, the CUDA quarantine as `--exclude` on the command line, real CUDA warm-up. Order: Codex commit → upload → cluster test job → campaign checklist → Zayd's OK for each `sbatch`.

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
      - **Sync log, 16 October 18:47 SAST / 16:47 UTC, upload (local → cluster), run by Code under the 16 October permission:**
        - From the clean HEAD `f91d6e0`, with the source-upload command of `docs/operations/cluster_sync.md` (from `code/msi`; `-n` preview first; no `--delete`).
        - 3 files sent: `scripts/summarise_rcc_fair_scoring.py`, `src/spatial_msipl/tests/test_rcc_pipeline.py`, and the untracked `.pym2aia_prefs.xml`. The last one has identical content on both sides (same sha256), so only its timestamp was updated.
        - `sha256sum` check afterwards: all 13 code files of `d35d063` and `f91d6e0` match HEAD on the cluster.
        - Earlier, Zayd synced `d35d063` himself; those 13 files had matched by `sha256sum` at about 18:40 SAST.
      - **Cluster test job 69420** (Zayd's OK; submitted 18:48 SAST / 16:48 UTC on `bigbatch` with `SBATCH_PARTITION=bigbatch`, because `batch` is still down; mscluster48; 4:51; exit 0). **131/131 tests pass under `s3pl_env`, 0 skipped**, including all 10 of `test_rcc_pipeline` (the default-path bit-identity tests among them), `test_fair_scoring_arms`, `test_centre_masking` and `test_neighbourhood`. Log: `results/validation/fair_scoring_env_tests/69420_unittest.log`.
      - **RCC preparation 69421** (Zayd's OK; submitted 18:55 SAST / 16:55 UTC, `SBATCH_PARTITION=bigbatch`, indices 0–7): 8/8 COMPLETED, exit 0, 11–40 s each. Every task logs budget `complete` and partition audit `complete`; the `.err` files are empty. No result was read on the cluster.
      - **Download stopped before syncing** (about 19:05 SAST / 17:05 UTC, under the standing approval of 18:56). The `-n` preview of the documented artifact pull (`cluster_sync.md`) listed:
        - 40 files in `results/diagnostics/peak_partition_audit_rcc/`, 18 in `results/experiments/rcc_spatial_msipl/` and 2 in `results/validation/fair_scoring_env_tests/`, as expected;
        - but also 18 Slurm logs in `logs/`, which the download rule does not allow;
        - and an overwrite of the committed `results/publication/current_evidence/README.md` by the older cluster copy (the known 15 October issue).
        - Both are stop conditions in `CLAUDE.md`, so nothing was pulled and the P1 decision waits. Code did not change the command.
      - **Pull conflict resolved** (supervisor chat 19:12, Zayd agreed): the documented artifact pull no longer includes `logs/` and excludes the curated `results/publication/current_evidence/README.md`.
      - **Sync log, 16 October 19:18 SAST / 17:18 UTC, download (cluster → local), run by Code:**
        - The updated pull of `cluster_sync.md`, from `code/msi`, `-n` preview first.
        - 60 new files and 19 new folders: 40 in `results/diagnostics/peak_partition_audit_rcc/`, 18 in `results/experiments/rcc_spatial_msipl/` and 2 in `results/validation/fair_scoring_env_tests/`.
        - No existing file changed; no `logs/` and no README.
        - `git status` afterwards: no tracked file under `results/` modified. `build_current_evidence_tables.py` was re-run and its tables did not change.
      - **RCC P1 decision (mechanical, S1 only; standing approval):** **P1 approved.** It passes S1 in 8/8 runs; the widest group is 0.0 Da. P3 is not used.
        - Descriptive: on RCC, P1 is identical to bin level (10,200 singleton groups for 10,200 bins; S3 "near bin-level", informational). The RCC bin spacing exceeds the 50 ppm hard break, so every bin starts a new segment. RCC P1 results will therefore repeat the bin-level results.
        - **Budgets** (`reference_budget.json`, all complete), K_bin = |R@0.4| over the three classes: MH0204_33 3,382; UH0505_12 2,316; UH0710_33 2,167; UH9610_15 1,167; UH9812_03 2,676; UH9905_18 2,501; UH9911_05 3,210; UH9912_01 2,994. That is 11–33% of the 10,200 bins, far larger than the GBM/CAC budgets. These are descriptive only and change nothing.
        - The approval file was first refused by the session's permission guard. Zayd then approved writing it in the session.
        - The supervisor verified the S1 evidence (chat 19:27): max group size 1 bin, width 0.0 Da. Reporting rule: "P1 = bin level on RCC (bin spacing ≈0.083 Da > merge threshold); no separate P1 verdict". It is not counted as independent confirmation, and the summary gives the budget range next to GBM/CAC. *(Superseded 17 October: after the 19:47 budget correction P1 is a budget sensitivity and does not enter the RCC verdict; see the Section 6.1 amendment.)*
        - **`results/diagnostics/peak_partition_audit_rcc/partition_approval.json` written** (16 October, about 19:25 SAST): P1 approved for 8/8 with the audited hashes; P3 not used. It was written locally from the pulled audits and copied identically to the cluster (sha256 `689822537e26…4877` on both sides).
      - **RCC pilot 69429** (standing approval; Zayd's explicit OK in the session): `submit_rcc.sh pilot`, tasks 2, 3, 10 and 11 (UH0710_33 and UH9610_15, `central_only` and `uniform_mean`). Submitted 19:26 SAST / 17:26 UTC on `bigbatch`, with the 16 quarantined nodes excluded.
      - **Spec correction: RCC budget** (supervisor chat 16 October 19:47; Zayd informed, and on 16 October he instructed Code not to submit the remaining runs until the fix was in place). The reason is in Section 6.1 item D step 2: the paper's RCC budget is PCC 0.5, and the released `num_GT_peaks` equal our |R@0.5|.
        - **Code, about 20:00–20:20 SAST:**
          - `compute_reference_budget.py` gained opt-in `--released-target-config`/`--released-target-key`; the config is parsed with `ast`, never executed. The output `released_target_budget.json` records K_bin = `num_GT_peaks[run]`, all |R_t|, our |R@0.5| and its difference.
          - The RCC jobs now read `released_target_budget.json` and write or read the matched evaluation in `peak_evaluation_released_target/`. The preparation job appends to `audit_stdout.log` instead of overwriting it.
          - `summarise_rcc_fair_scoring.py` adds the budget note (RCC range next to GBM 584–1,028 and CAC 133–315) and the 19:27 P1 note.
          - Nothing is moved or overwritten: the 69421 `reference_budget.json` files and the pilot's |R@0.4| `peak_evaluation/` stay as a superseded record.
        - **Tests:** `test_rcc_pipeline` now has 12 tests, all passing locally. They include `test_released_target_budget_equals_num_gt_peaks_for_all_8_rcc_runs` (K_bin == `num_GT_peaks[run]` for all 8 runs, and the run list and job flags agree) and a refusal test for unknown or partial flags.
        - `baselines/s3pl/data_configs.py` is identical on the cluster (sha256 `fd4c9c6a…6635`).
        - **No retraining is needed.** Training, the GMM and IG don't depend on K_bin. After commit and upload, the plan is:
          1. re-run the CPU preparation (released-target budgets; the audit is skipped when its provenance is unchanged);
          2. resubmit only the pilot indices (2, 3, 10, 11). The campaign job skips training (complete checkpoint) and IG (valid), and runs only the matched evaluation into `peak_evaluation_released_target/`.
        - The remaining 12 tasks wait for this.
        - **Sync log, 16 October 20:14 SAST / 18:14 UTC, upload, run by Code:** from the clean HEAD `f01ee5f` (Zayd's commits `17712b6` and `f01ee5f`), with the documented command and `-n` first.
          - 7 files sent: `compute_reference_budget.py`, `summarise_rcc_fair_scoring.py`, `test_rcc_pipeline.py` and the 4 RCC job scripts. The untracked `.pym2aia_prefs.xml` was also listed; it had a timestamp-only difference.
          - `sha256sum` against HEAD: 9 of 10 checked files match.
          - The 10th, `baselines/s3pl/data_configs.py` (unchanged since the S3PL setup commit `1fa881c`), differs from HEAD only in line endings: HEAD converted to CRLF gives exactly the cluster's sha256 `fd4c9c6a…6635`. `ast` parses it identically, so this is not a code mismatch, like `cluster_node_issues.txt` on 15 October. `released_target_budget.json` records the hash of that cluster copy.
        - **Pilot 69429:** still training at 20:14 SAST (48 min; CUDA warm-up passed on RTX 3090 on all 4 tasks).
        - **Released-target prep 69440** (standing approval, plus Zayd's 19:47 instruction): `SBATCH_PARTITION=bigbatch submit_rcc.sh prep`, indices 0–7, 20:15 SAST / 18:15 UTC. 8/8 COMPLETED, exit 0, 8–38 s each. Every task logs budget `complete` and partition audit `complete` (skipped: unchanged provenance); the `.err` files are empty.
        - **Download stopped (about 20:20 SAST, before syncing).** The `-n` preview of the documented pull would:
          - change 9 committed local files: the 8 `peak_partition_audit_rcc/*/audit_stdout.log` (the rerun appended to them) and `rcc_spatial_msipl/provenance/slurm_job_ids.txt` (new job IDs). `partition_approval.json` showed a timestamp difference only;
          - bring partial files of the still-running pilot 69429.
          - Both are stop conditions in `CLAUDE.md`. The new `released_target_budget.json` files (8) are only on the cluster, so far.
          - **Zayd's decision, about 20:22 SAST:** the pull may update those append-only logs, and he commits afterwards. The pull runs once, after the pilot and its re-score have finished (downloads only for finished jobs).
      - **Runtime-only change: cached loader for RCC** (supervisor chat 16 October 21:42, which replaces the entries now stamped 21:36 and 21:41; Zayd agreed). No scientific effect.
        - **Found:** pilot 69429 was healthy but slow. UH0710_33 took about 1.5 min/epoch and UH9610_15 at least 4 min/epoch, so UH9610_15 would hit the 4 h limit. The RCC HDF5s are m/z-major (`mz_by_pixels`, like GBM), and `run_rcc_campaign.sh` trained without `--cache-spectra`. The spec's "streaming loader (the runs are small)" was Code's error.
        - **Change (about 21:43 SAST):** `--cache-spectra` added to the training call in `run_rcc_campaign.sh`. `training_stdout.log` is now appended (`>>`), so a resumed run keeps the log of its streamed part. `test_rcc_pipeline` checks both; it passes 12/12 locally.
        - The cached loader was validated equivalent in investigation 10 (61483/61484). Code confirmed that `data_loader` is not in `resume_signature` (`training.py`, about lines 292–319; `data_source` is the same HDF5 path for both loaders).
        - **Pilot plan (21:42, final):** after commit and upload, `scancel 69429` (Zayd's OK given). The 4 runs' streaming checkpoints and partial result folders are moved to `superseded_streaming/` on the cluster (a move, not a delete; Zayd's OK). Indices 2, 3, 10 and 11 are then resubmitted **cached from scratch**, so all 16 RCC run-arms use one loader. An earlier supervisor suggestion to resume cached from the streaming checkpoints (then stamped 21:48, now 21:41) was technically valid, because the loader is not in the resume signature, but it was withdrawn at 21:42 in favour of one loader.
        - **Structural fix (supervisor chat 21:48):** `src/spatial_msipl/tests/test_job_scripts.py::test_training_jobs_use_cached_loader` fails if any job script that calls `train_spatial_msipl_production.py` lacks `--cache-spectra`. The 9 frozen pre-October streaming scripts are on an explicit allowlist, each with its reason. 3/3 tests pass locally. A pre-submission checklist was added to `CLAUDE.md`.
        - **Label only:** with `--cache-spectra`, the training summary's `purpose` string reads "cached full-run runtime/equivalence validation, not frozen baseline". That comes from the training script's generic label and does not mean these are validation runs. The RCC runs are the production RCC arms.
        - **Executed by Code (Zayd's instruction in the session; supervisor chat 21:42 and 21:48 reconciliation), 16 October:**
          - **Upload** from the clean HEAD `d62bc63` at 21:56 SAST, with `-n` first. Sent: `run_rcc_campaign.sh`, `test_job_scripts.py` (new), `test_rcc_pipeline.py`, and `submit_rcc.sh` (timestamp only). `sha256sum`: 7/7 checked RCC files match HEAD.
          - **`scancel 69429`** at 21:57 SAST: all 4 tasks CANCELLED after 2 h 30 min of streamed training, with no final checkpoint. (The pilot never reached the matched evaluation, so no |R@0.4| `peak_evaluation/` exists.)
          - **Moved aside** at 21:58 SAST with `mv -n` (refusing an existing target): the 4 checkpoint folders and the 4 result folders of indices 2, 3, 10 and 11, to `/datasets/zsuliman/msi_checkpoints/spatial_msipl/rcc/superseded_streaming/<run>_seed1/<arm>/` and `results/experiments/rcc_spatial_msipl/superseded_streaming/<run>_seed1/<arm>/`. 16 files in all: 4 × `checkpoint_latest.pt`, plus `progress.json`, `training_history.json` and `training_stdout.log` for each.
          - Checked afterwards: no `checkpoint_latest.pt` and no arm result folder remains for those indices; the run-level budget files are untouched.
          - **Cached pilot 69482** submitted 21:59 SAST / 19:59 UTC (`submit_rcc.sh pilot`, indices 2, 3, 10 and 11, `bigbatch`, the 16 quarantined nodes excluded), after the checklist was posted to the chat at 22:00. If a task runs past 1 h, Code stops and reports.
          - **Overnight queue (supervisor chat 22:07, Zayd-approved; commit permission until Saturday 17 October 12:00 SAST):**
            - `[overnight]` commit `a609a00` (item 1): RCC summary tables in the GBM/CAC format.
            - `[overnight]` commit `e60f9ea` (item 2): `run_s3pl_cac_seeds.sh` and `submit_s3pl_cac_seeds.sh`.
            - Upload at 22:16 SAST, `-n` first, 4 files; 4/4 match HEAD.
            - **69502**, S3PL CAC seeds 2 and 3, submitted 22:16 SAST / 20:16 UTC: 16 tasks, at most 2 running, `bigbatch`, quarantine excluded. The checklist was posted in the chat first. Output `reproducibility/s3pl_cac_seeds/`.
            - Gate job **69511** (S3PL RCC staging and adapter gate; `bigbatch`, CPU): **passed**. S3PL's |R@0.5| equals ours for all 8 runs. `[overnight]` commits `60c2e61` (item 3) and `5242874` (item 4); uploads checked against HEAD by `sha256sum`.
            - **69502** (S3PL CAC seeds 2 and 3): 16/16 COMPLETED, exit 0, 1–2.3 min each.
            - **Pilot 69482: gate passed.** All 4 run-arms: cached, 100 epochs from scratch; IG `valid`; matched evaluation at K_bin = `num_GT_peaks`, `complete`. UH0710_33 took 4.5 min per task and UH9610_15 27–28 min (IG streams; no change made).
            - **Pull** at 22:32 SAST: 239 new files and the 9 approved append-only logs (11 lines added). The evidence tables are unchanged. All 8 released-target budgets have K_bin == `num_GT_peaks`.
            - Submitted 22:34 SAST / 20:34 UTC after the checklists: **69524** (`submit_rcc.sh rest`, 12 tasks, at most 4 running) and **69529** (`submit_s3pl_rcc.sh train`, 24 tasks, at most 2 running).
            - Further `[overnight]` commits, each uploaded from the clean HEAD (`-n` first) and checked with `sha256sum`:
              - `f1bd2b2`: S3PL seed summariser plus `results/comparisons/s3pl_seed_stability/cac/`. Seed means 0.591 / 0.582 / 0.511, all inside the published CI.
              - `8e04ee8`: `run_rcc_bic.sh`.
              - `c3e2058`: RCC ion-image export and its test.
              - Local tests: `test_rcc_pipeline` 13/13, `test_s3pl_rcc_adapter` 3/3, `test_job_scripts` 3/3.
            - **RCC remainder 69524:** 11/12 complete. **69524_9** (UH0505_12 `uniform_mean`) failed with exit 4: IG `needs_more_ig_steps` at 64 steps (median normalised residual 0.00019 ≤ 0.05; 95th percentile 0.175 > 0.15).
              - Code stopped and posted (22:55). The supervisor (22:57) applied the predeclared rule: "not done (IG completeness failed at 64 steps)", no rerun, and `uniform_mean` is 7/8, "incomplete; no verdict".
            - **S3PL-RCC 69529:** 24/24 complete. Seed means 0.441 / 0.427 / 0.406 (published 0.470, CI 0.352–0.588); `[overnight]` `151ef59`.
            - **Pulls** at 23:19 and 23:43 SAST (new files only, plus append-only job-ID logs).
            - **RCC fair scoring 69565** (`fair p1`, `bigbatch`, after the checklist): 8/8 exit 0, 60 evaluator outputs; the UH0505_12 `uniform_mean` arm skipped as not done.
            - **Decision tables** (local, `[overnight]` `028491a`):
              - `central_only`: "mixed / not resolved by the predeclared rule" (Section 7.1 fall-through). IG below posterior-|PCC| in 0/8 runs; mean −0.156 at bin level, −0.179 under P1.
              - `uniform_mean`: "incomplete; no verdict (7/8 runs)", 0/7 positive, mean −0.185.
              - Sensitivity (cancer/normal only, descriptive): −0.045 (3/8) and −0.077 (1/7).
              - P1 on RCC is singleton groups at the K_peak (≈ |R@0.4|) budget, not at K_bin. Wording sent to the supervisor (23:50 entry).
            - **Legacy msiPL 69570:** 7/8 complete; 69570_1 failed on the known mkdir race (the submitter did not pre-create the checkpoint root). It was posted, not retried, and the submitter fixed (`[overnight]` `62884f2`).
              - Count gate: 2/7 within ±50; 5/7 "count not reached" (nearest 1,054–1,248 bins against targets 1,676–2,200); the grid was not widened.
              - mSCF1 mean 0.160 on 7 runs (published 0.159), each run within 0.012.
            - Submitted 23:45 SAST / 21:45 UTC, after the checklist, on `bigbatch`: **69583** (RCC BIC, 16 tasks, output parents pre-created) and **69588** (ion-image export).
            - **69583, BIC (descriptive):** 15/16 tasks; task 9 exited by design (UH0505_12 `uniform_mean` not done). BIC selects K = 6, the largest candidate, in all 15 run-arms, with refit ARI 1.000. Posterior-|PCC| at K = 6 minus K = 3: −0.061 (`central_only`) and −0.115 (`uniform_mean`).
            - **69588, ion-image export:** 2 files in `results/visualisations/rcc/`.
            - Pulled at 23:48 SAST. **End of overnight queue:** items 1–6 done; open points are the legacy UH0505_12 retry and the P1 wording.
          - **17 October morning (supervisor chat 07:03 and 07:16):**
            - **Legacy msiPL UH0505_12 retry, 69625** (`submit_msipl_rcc.sh --indices 1`, Zayd present, approved 07:03). The first failure (69570_1) is recorded as **Code's oversight** (the submitter did not pre-create the shared checkpoint root), not a node failure. Checklist posted at 07:19; cluster scripts matched HEAD `12d7cdf` by `sha256sum`. Submitted 07:20 SAST / 05:20 UTC on `bigbatch` (`--exclusive`, CPU); COMPLETED in 3:55 on mscluster74, exit 0.
              - Result (descriptive): mSCF1 **0.139** (published 0.14). Count **not reached**: Beta 0.0 (the grid edge) picked 1,288 bins against the target 1,448 (−160); `closest_outside_tolerance`; the grid was not widened.
              - Legacy msiPL on RCC is now 8/8: mean **0.157** (published 0.159, CI 0.141–0.176); count reached in 2/8, not reached in 6/8.
            - **Pull** at 07:37 SAST (cluster → local, the documented artifact pull, `-n` first): 21 new files in `results/baselines/msipl/{rcc,rcc_fixed_beta}/RCC_UH0505_12/` plus one line appended to `rcc_provenance/slurm_job_ids.txt`. The preview touched none of the uncommitted local edits under `results/` (the S3PL summaries and the new decision folders). Evidence tables rebuilt: unchanged.
            - **RCC verdict amendment** (Section 6.1, primary test): bin level only; P1 relabelled as a budget sensitivity. Regenerated into `rcc/decisions_20261017_local/` and `rcc_cancer_normal_sensitivity/decisions_20261017_local/`; `decisions_20261016_local/` superseded. Verdict labels and all numbers unchanged (CSV files byte-identical).
            - **S3PL seed summariser, fail-closed provenance checks** (Codex review): per run, `metrics.json` (dataset, normalisation, picked count = `num_GT_peaks`, no ablation or context mode, source training name), the training log (seed, settings, data file, artifact root), the manifest (seed, settings) and the picked-peaks CSV row count, with sha256 of each file. CAC seed 1 (run 21 August) predates the manifests and the normalisation option (`3fb2f75`, 12 September); its missing fields are recorded as "not recorded (pre-provenance format)", and any field it does record must still be right. Regenerated `results/comparisons/s3pl_seed_stability/{cac,rcc}/`: 24/24 runs pass in each; `section_table.csv` byte-identical; `summary.json` gains only `provenance_checks` and `provenance`.
            - Tests (local Python 3.14.5, NumPy 2.4.4, sklearn 1.9.1, h5py 3.16.0, in a scratch venv; none skipped): `test_rcc_pipeline` 16/16, `test_s3pl_seed_provenance` 11/11 (new), `test_job_scripts` 3/3. The code changes are left uncommitted for Codex review, so they are not on the cluster.
            - **Test S (Section 6.2; supervisor chat 08:04, 08:14, 08:28, 08:37):** code committed by Codex as `20158f8`. Supervisor go at 08:37: Cardinal weights accepted; CAC keeps bin level **and** P1 as predeclared, with the footnote "CAC P1 is singleton groups (1,481 for 1,481 bins), so its peak-level score is the bin-level score at the K_peak budget; requiring both is a two-budget check, not an independent partition check".
              - **Upload** 08:39 SAST (local → cluster, documented command, `-n` first): 11 files (7 Test S files, plus 4 from `83d8222`); `sha256sum` 11/11 match HEAD.
              - **Cluster test job 69628** (`bigbatch`, CPU): COMPLETED in 7:30, 162 tests OK, `test_spatial_segmentation` 25/25 run (not skipped).
              - SSH connection reuse set up in WSL with Zayd's OK, scoped to the cluster host (chat 08:49). Polling corrected to the 17 October rule.
              - **69631** submitted 08:51 SAST / 06:51 UTC after the checklist (chat 08:51): `SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_spatial_segmentation_s.sh`, 24 tasks, at most 4 running. Output `results/diagnostics/spatial_segmentation_S/` (a new root).
              - 69631: 23/24 complete (12 s – 3:44 per task). Task 18 (RCC_UH0710_33) failed 3 times on mscluster54 with `FileNotFoundError` on an existing file whose sha256 matches the record (69631_18, 69656_18, 69657_18). 69657 used `SBATCH_EXCLUDE`, which Slurm does not read (Code's error). **69658** (direct `sbatch --exclude=mscluster54`, Zayd's OK) COMPLETED on mscluster74 in 21 s. The node is recorded in `cluster_node_issues.txt`.
              - **Pull** 09:16 SAST (cluster → local, `-n` first): 97 new files (94 Test S, the job-ID log, the 69628 test logs); no committed file changed.
              - **Validity:** all checks passed in 47/47 section-arms (refit ARI 1.0; 158/158 saved-score reproductions to 1e-12; edges = Moran's I edges; every smoothed GMM converged, none with an empty component). No refusals.
              - **Decision table** (local): `results/diagnostics/spatial_segmentation_S/decisions_20261017_local/`. S1 − plain posterior-|PCC|, bin / P1:
                - GBM `central_only` "equivalent" (+0.013, 5/8 / +0.010, 5/8);
                - GBM `uniform_mean` "does not meet the 'helps' rule (labelled mixed)" (+0.029, 3/8 / +0.027, 5/8);
                - CAC `central_only` "equivalent; P1 +0.007, 8/8 positive" (bin −0.001, 4/8);
                - CAC `uniform_mean` "equivalent" (+0.004, 5/8 / +0.006, 3/8);
                - RCC `central_only` "equivalent" (bin −0.012, 5/8);
                - RCC `uniform_mean` "incomplete; no verdict (7/8 runs)" (−0.023, 4/7).
                - S2 is descriptive; see the supervisor chat entry of 09:17.
            - **Test R (Section 6.3; supervisor chat 09:45, 09:59, 10:11, 10:24, 10:26):** code committed by Codex as `1779ec7` (record `9f61993`).
              - **Upload** 12:06 SAST / 10:06 UTC (local → cluster, documented command, `-n` first, from the clean HEAD `9f61993`): 9 files (the 7 Test R files from `1779ec7`, plus `cluster_node_issues.txt` and `summarise_spatial_segmentation_s.py` from `ba71569`); `sha256sum` 9/9 match HEAD.
              - **Cluster test job 69674** (`bigbatch`, CPU; `batch` still down): COMPLETED in 8:07 on mscluster55, 181 tests OK, `test_test_r` 19/19 run (none skipped).
              - Checklist posted (chat 12:16). **69683** `train-first 2` submitted 12:17 SAST / 10:17 UTC (tasks 0–31, at most 3 running). **69689** `train-gbm 2 --after 69683` submitted 12:19 SAST (tasks 32–47, `afterok`).
              - `train-first 3` was refused by Slurm (`QOSMaxSubmitJobPerUserLimit`: the `mss_bigbatch` QOS allows 48 submitted and 6 running jobs per user, counting each array task). Only empty seed-3 parent folders and `manifest_seed3.txt` (correct contents) were left behind; no job was created. Seed 3 is submitted once seed 2's first phase has left the queue (chat 12:20).
              - **69683_2** (RCC_UH0505_12 `central_only`, seed 2): exit 4 after 15:08. Training and the checkpoint check passed; IG `needs_more_ig_steps` at 64 steps. Under Section 6.3 this seed-arm is **"not done"**, with no setting change. As a result, 69689's `afterok` can no longer be met; the plan is in the chat entry headed 12:47, actually posted 12:35 SAST (`scancel 69689`, then `--after-reviewed`, once Zayd has OK'd it).
              - 69683 finished about 13:10 SAST (31 COMPLETED; 69683_2 "not done"). **69746** `train-gbm 2 --after-reviewed 69683 --concurrency 2` submitted 13:29 SAST (Zayd's OK; supervisor 13:25 queue plan: GBM at 2 running and Test V at 1 while 69724 runs, raised when 69724 finishes).
              - **69724_15** (RCC_UH9912_01 `uniform_mean`, seed 3): exit 4 after 16:07. Training and the checkpoint check passed; IG `needs_more_ig_steps` at 64 steps. **"Not done"** under Section 6.3. Seed-3 GBM will use `--after-reviewed 69724`.
              - 69724 finished about 14:17 SAST (31 COMPLETED; 69724_15 "not done"). **69820** `train-gbm 3 --after-reviewed 69724` (at most 3 running) was submitted 14:21 SAST. 69746's throttle was raised to 3 at the same time (supervisor 13:25 item 3).
              - **69820** (seed-3 GBM) finished about 19:15 SAST: 15 COMPLETED. **69820_47** (GBM39_2 `uniform_mean`, seed 3): exit 4 after 35:42; training and the checkpoint check passed; IG `needs_more_ig_steps`. **"Not done"** under Section 6.3. **69979** `fair 3` (`SBATCH_PARTITION=bigbatch`, 24 tasks) was submitted 19:17 SAST. `batch` came back (73 idle nodes at 19:19), so 69979 was cancelled while still pending and resubmitted as **69980** on `batch` (the script default) at 19:20 SAST; it COMPLETED 24/24.
              - **69746** (seed-2 GBM): 16/16 COMPLETED (the last task, 69746_45 on mscluster81, took 1:50:25). **70060** `fair 2` on `batch` (24 tasks) was submitted 19:53 SAST. All Test R training is now finished.
              - 70060 COMPLETED 24/24. **Pull** 20:29 SAST (the documented artifact pull, `-n` first, no jobs running): 2,941 new files; no committed file changed. 156/156 Test R evaluator summaries `complete`.
              - **Test R decision table** (`results/diagnostics/fair_scoring_baselines/test_r/decisions_20261017_local/`):
                - **Decision 1: the headline does not hold overall.** CAC seed 2 "does not replicate" in both arms (`central_only` P1 6/8; `uniform_mean` bin and P1 6/8). Every other complete seed replicates. Four seed-arms are incomplete because IG was not done: RCC `central_only` seed 2, RCC `uniform_mean` seeds 1 and 3, GBM `uniform_mean` seed 3.
                - **Decision 2:** CAC "helps" (3-seed; agrees with seed 1); GBM "incomplete (7/8)" (seed-1 "equivalent" superseded); RCC "incomplete (6/8)".
                - Numbers and decision 3: chat 20:30.
              - **Test V (d)** (descriptive; VAE seed-mean 1–3 − PCA-5): GBM +0.042 5/8 / +0.041 5/8; CAC −0.012 2/8 / −0.023 2/8; RCC −0.011 3/7. Written to `segmentation_control_V/decisions_20261017_with_test_r_local/`; the seed-1 verdicts are unchanged.
              - **Runtime v2** regenerated with the 96 Test R cached rows (242 rows; v1 unchanged), after a one-line builder fix that skips the `provenance/` folder (uncommitted for Codex).
              - **69724** `train-first 3` submitted 13:03 SAST (tasks 0–31, at most 3 running) once the QOS had room. 69683's throttle was set back to 3 at the same time.
              - Zayd's OK (session, about 12:40 SAST; supervisor recommendation 12:41): `scontrol update JobId=69683 ArrayTaskThrottle=6` at 12:41 SAST, until seed 3 is queued; `scancel 69689` at 12:42 SAST (CANCELLED, never started). Seed-2 GBM will be resubmitted with `--after-reviewed 69683` once 69683 has finished; seed 3 follows the same path if needed.
            - **Test V and runtime addendum (Sections 6.4; supervisor chat 09:48, 12:42):** code committed by Codex as `f2e8040` (record `06ab508`). **Upload** 12:58 SAST (local → cluster, documented command, `-n` first, clean HEAD `06ab508`): 13 code files, `sha256sum` 13/13 match HEAD. **Cluster test job 69714** submitted 12:58 SAST (`bigbatch`, CPU), sharing the 6-running QOS limit with Test R. It **FAILED** in 6:54 on mscluster84: 226 tests, 1 failure and 2 expected skips (runtime-artifact tests). `test_segmentation_control_v` ran 18/18 OK. The failure is a test-only bug: `test_refuses_outside_slurm_without_the_flag` assumed `SLURM_JOB_ID` is unset, but it is always set inside the test job. The fix hides the variable in the test; it is uncommitted for Codex (chat 13:13). Test V was held.
              - **Test V submitted** 13:29 SAST (Zayd's OK for option (b); supervisor 13:25). It was submitted after test job 69714, whose only failure was the unrelated test-only bug in `test_ranking_stage_runtime`, fixed in `c0bc174`. Checklist: chat 13:29. **69749**: `SBATCH_PARTITION=bigbatch submit_segmentation_control_v.sh --indices 0-5 --concurrency 1` (the GBM sections; later chunks follow as the 48-job QOS frees). Later chunks, each at most 1 running: 69760 (6–8), 69764 (9–11), 69768 (12–14), 69771 (15), 69777 (16–18), 69785 (19), 69790 (20–22), 69797 (23); the last was submitted 14:12 SAST. **Cluster test job 69798** for `c0bc174` was submitted 14:12 SAST. It COMPLETED in 4:22 on mscluster58: 232 tests OK with 3 expected artifact skips; the S3PL suite 25 OK with none skipped (the real-m2aia and torch training-call tests ran).
              - **Test V complete:** 24/24 COMPLETED. **Pull** 14:29 SAST (cluster → local, the documented artifact pull, `-n` first). Two excludes kept out jobs still running: `results/experiments/test_r_training_seeds/` and the 69798 logs. 53 new files; no local file changed.
                - Validity: refit ARI 1.0 in 24/24; 80/80 reproductions within 1e-12; every PCA GMM converged, none with an empty component.
                - Decision table: `results/diagnostics/segmentation_control_V/decisions_20261017_local/`. VAE `central_only` − PCA-5 posterior-|PCC|, bin / P1:
                  - GBM "mixed" (+0.023, 5/8 / +0.023, 5/8);
                  - CAC "mixed" (−0.013, 4/8 / −0.028, 2/8);
                  - RCC "equivalent" (+0.015, 3/8, bin only).
                - Descriptive values: chat 14:30. The ranking-stage timing waits for a test job that passes after `c0bc174`.
            - **Test N (Section 6.5):** committed by Codex as `c0bc174` (together with the ranking-test fix; record `84504d7`). **Upload** 13:29 SAST (documented command, `-n` first, HEAD `84504d7`): 15 files, `sha256sum` 15/15 match HEAD. The cluster test job is submitted once the QOS has room; Test N is submitted only if its m2aia and torch tests run, not skip.
            - **Ranking-stage timing (09:48 item 2):** submitted 19:20 SAST / 17:20 UTC as **69985** on `batch` (script default; `batch` back up), array 0–23, at most 4 running, `--exclusive`. Gate: test job 69798 passed after `c0bc174`. Checklist: chat 19:20. Output: `results/diagnostics/ranking_stage_runtime/`.
              - **69985 stopped on its reproduction check:** 9 COMPLETED (the 8 CAC tasks, plus RCC_UH0505_12, which had no saved ranking to check), 15 FAILED with exit 4 (all GBM and RCC tasks with a saved ranking). Cause: the script made a contiguous pixels × bins copy of the bins × pixels GBM/RCC files, which changed NumPy's summation order (differences up to about 1e-16, reproduced locally). Near-tied bins then swapped in the full ranking. The scientific results are unaffected. The fix keeps the evaluator's chunk layout, with a bit-for-bit test; it is uncommitted for Codex (chat 19:28). Rerun plan: move the first attempt aside, then resubmit all 24 tasks (needs Zayd's OK).
              - Codex committed the fix as `303d07d` (record `2b40cc5`). Zayd's OK for the move and the resubmission came at about 19:42 SAST. **Upload** 19:44 SAST (documented command, `-n` first): 2 files changed in content, `sha256sum` matching HEAD. **Cluster test job 70032** (`batch`) submitted 19:44 SAST. It COMPLETED in 5:04: 233 OK with 3 expected skips; the ranking suite 14/14, including the bit-identity test; S3PL 25 OK.
              - **Move** 19:51 SAST: `mv -n results/diagnostics/ranking_stage_runtime results/diagnostics/ranking_stage_runtime_superseded_69985` (10 files kept). **70034** resubmitted all 24 tasks on `batch` at 19:51 SAST / 17:51 UTC.
              - 70034: 17 COMPLETED. All 8 GBM and all 8 CAC pass the exact full-ranking check, plus RCC_UH0505_12, which has nothing to check against. The 7 other RCC tasks FAILED with exit 4: their saved rankings came from fair-scoring job 69565 on `bigbatch` GPU nodes, a different CPU type from the `batch` pool (GBM/CAC were scored on `batch`, job 66053). Decision on (a) RCC on `bigbatch` nodes, (b) a relaxed RCC check, or (c) RCC "not done": chat 19:54.
              - **PCA reconstruction addendum and RCC timing option (a) upload:** 21:18 SAST, from clean committed HEAD `acd9e905`, using the documented source upload with `-n` first and no `--delete`. Fourteen source/test files were transferred or timestamp-refreshed; the command was rerun with the exact documented lowercase `*.imzML` exclusion after a capitalization typo in the first real invocation (no data file was listed or transferred). Cluster and local SHA-256 values match for all 14 uploaded files; `git diff --exit-code HEAD -- code/msi` passed before the check.
              - **Cluster compatibility test 70119 submitted:** 21:19 SAST on the script-default `batch` partition: `sbatch --parsable slurm_jobs/run_fair_scoring_tests.sh`. It must pass, with `test_pca_reconstruction_v` 6/6 and no skips, before either scientific submission.
              - **Cluster compatibility test 70119 FAILED:** finished in 5:17 on mscluster146, exit 1. The required `test_pca_reconstruction_v` module ran 6/6 with no skips and all six passed. The full Python suite ran 243 tests with 1 failure and 3 expected artifact skips: existing `test_segmentation_control_v.SummariserTests.test_verdicts_per_collection` expected `d_vae_seed_mean_minus_pca5` to be `None`, but the cluster's now-present Test R artifacts populated it. The S3PL sub-suite did not run because the main unittest pipeline failed. Per the stop rule, neither the PCA reconstruction array nor the RCC timing jobs were submitted.
              - **Test-isolation fix and resubmission (Code; Codex builder retired, chat 21:45):**
                - The fix is `55d20f0e`: `SummariserTests` passes an empty `--test-r-fair`.
                - **Upload** 21:54 SAST, from clean HEAD `f80b587f`, using the documented command with `-n` first. One file transferred (`test_segmentation_control_v.py`). `sha256sum` matches HEAD in 12/12 changed files.
                - **Cluster test 70132** (`batch`, mscluster146), submitted 21:55 SAST, COMPLETED in 4:21. The main suite ran 243 tests, all OK, with 3 expected artifact skips: `test_pca_reconstruction_v` 6/6, `test_segmentation_control_v` all OK. S3PL 25/25 OK.
              - **PCA reconstruction array 70137** was submitted 22:00 SAST (20:00 UTC) with `bash slurm_jobs/submit_pca_reconstruction_v.sh`: indices 0–23, `%4`, `batch`, new root `results/diagnostics/pca_reconstruction_V/`.
              - **RCC ranking timing (option (a)):** `bash slurm_jobs/submit_rcc_ranking_stage_timing.sh` was run 22:00 SAST. It made 8 single-task submissions on `bigbatch`, each `--nodelist` set to the node of the matching 69565 task:
                - 70142 (index 0, mscluster71), 70143 (1, mscluster74), 70144 (2, mscluster76), 70145 (3, mscluster77), 70146 (4, mscluster55), 70147 (5, mscluster74), 70148 (6, mscluster71), 70149 (7, mscluster76).
                - Output root `results/diagnostics/ranking_stage_runtime_rcc_bigbatch/`. The map is recorded in `provenance/task_node_map.txt`.
                - **Note:** mscluster74 and mscluster76 are on `gpu_cuda_quarantine.txt`. The job is CPU-only and uses those nodes because they made the saved RCC rankings, so the CUDA quarantine does not apply (supervisor chat 21:53).
              - **70137 finished** by 22:08 SAST: 24/24 COMPLETED, exit 0, on `batch` (mscluster129–132, 146).
                - Logs: 23 sections `complete`. CAC 360TopL is `not_done`: the PCA-5 explained-variance sum differs from the saved Test V value by 2.82e-6, against the 1e-6 tolerance. PCA-20 passed at 2.85e-7.
                - In the other 23 sections the differences are 1.5e-9 to 5.6e-7, never exactly 0.
                - Likely cause, not verified: Test V ran on `bigbatch` (mscluster73/79/86; 360TopL was task 69768_13 on mscluster73), while this addendum ran on `batch` as predeclared. Randomized float32 PCA rounds differently on another CPU type.
                - The tolerance is unchanged. Under the addendum the section is "not done".
              - **Pull** 22:13 SAST (documented quiet artifact pull, `-n` first): 32 new files (25 `pca_reconstruction_V`, 2 `ranking_stage_runtime_rcc_bigbatch/provenance`, 5 test-job validation records). No committed file changed.
              - **RCC timing status at 22:08 SAST:** all 8 tasks PENDING.
                - The 6 tasks pinned to mscluster55/71/74/77 wait on `Priority`. Each node is fully allocated (14/14 CPUs) to another user's job with a 3-day limit, and `--exclusive` needs the node empty.
                - The 2 tasks pinned to mscluster76 (indices 2 and 7) show `ReqNodeNotAvail`, because mscluster76 is `down*` (Not responding).
                - No `bigbatch` node is idle.
              - **RCC timing moved to "shared node, not exclusive"** (Zayd's OK, about 22:19 SAST):
                - **CPU-model check:**
                  - `scontrol` (once) shows identical hardware on mscluster55/71/74/76/77: 1 socket × 14 cores × 2 threads, 124,000 MB. It does not report the CPU model.
                  - The Test R `runtime_metrics` record `Intel(R) Core(TM) i9-10940X CPU @ 3.30GHz` for mscluster55, 71 and 77. All 96 `bigbatch` records in `results/` show that model.
                  - mscluster74 and 76 have no record, because they are GPU-quarantined.
                  - The summariser refuses mixed CPU models within a collection, so an unexpected model fails closed.
                - **Cancelled** 70142–70149 while pending (8/8 `CANCELLED`, none started).
                - **First resubmission attempt refused by sbatch:** `--oversubscribe` on the command line is "mutually exclusive" with the runner's `#SBATCH --exclusive`. Nothing was submitted.
                - **Resubmitted as array 70179** at 22:21 SAST: `bigbatch`, indices 0–7, `%1`, `--exclude=mscluster[42-54,56-70,72-73,75,78-89]`, so only nodes 55/71/74/76/77 are allowed.
                  - It was submitted through `sbatch --wrap="bash slurm_jobs/run_ranking_stage_timing.sh <root>"`, with the runner's `#SBATCH` resources repeated on the command line apart from `--exclusive` (`--nodes=1 --ntasks=1 --cpus-per-task=2 --mem=24G --time=02:00:00`, same log names). The committed runner is unchanged.
                  - `scontrol` shows `OverSubscribe=OK`. The partition has `OverSubscribe=NO`, so the node is shared but not the CPUs.
                  - New root: `results/diagnostics/ranking_stage_runtime_rcc_bigbatch_shared/` (provenance `slurm_job_ids.txt` and `notes.txt`). The exact full-ranking reproduction check is unchanged.
                - **Label:** "shared node, not exclusive".
                - **Stop rule:** if nothing has finished by Monday 19 October 18:00 SAST, use option (c).
                - At submission it was pending on `Priority`, because all four live nodes are fully allocated.
              - **CAC 360TopL PCA rerun** (supervisor ruling 22:28; Zayd's OK about 22:29 SAST): **job 70180**, submitted 22:30 SAST.
                - Placement: `bigbatch`, not exclusive (`OverSubscribe=OK`), 2 CPUs, 16 GB, 2 h, the same thread settings as Test V (2).
                - Allowed nodes: only those with a recorded i9-10940X (mscluster52, 55, 58, 71, 73, 77, 79, 81, 84, 86, 87), via `--exclude=mscluster[42-51,53-54,56-57,59-70,72,74-76,78,80,82-83,85,88-89]`.
                - It runs the unchanged `evaluate_pca_reconstruction_v.py` through `sbatch --wrap`, with the gate unchanged at 1e-6.
                - New subfolder: `results/diagnostics/pca_reconstruction_V/rerun_360TopL_bigbatch_i9/` (`CAC/360TopL_seed1/`, plus `provenance/slurm_job_ids.txt` and `cpu_model.txt`, written by the job). The `not_done` record is untouched.
                - Test V's 360TopL ran on mscluster73 (69768_13).
                - **Fallback:** if it hasn't passed by Monday 19 October 18:00 SAST, use the conservative CAC count (supervisor 22:28, point 2).
              - **18 October, morning check** (one `squeue`/`sacct`, 10:33 SAST):
                - **70180** COMPLETED, 0:34. It started 21:06 UTC (23:06 SAST, 17 Oct) on mscluster86; `cpu_model.txt` records `i9-10940X`.
                - **70179** ran 23:07–23:09 UTC (01:07–01:09 SAST, 18 Oct), every task on mscluster77. 7 COMPLETED (7–49 s each). **Task 2 (RCC_UH0710_33) FAILED**, exit 1 after 4 s: `FileNotFoundError` for `results/experiments/rcc_spatial_msipl/RCC_UH0710_33_seed1/uniform_mean/attribution/latent_mean.npy`.
                - The file exists on the cluster (19,568 bytes, 16 Oct 20:03), and the other 7 tasks on the same node read their own files. So the node did not see one existing file, as with mscluster54 on 17 Oct (69658). Not retried, per the overnight stop rule.
              - **Pull** 10:35 SAST (documented quiet artifact pull, `-n` first): 12 new files (3 from the `pca_reconstruction_V/rerun_360TopL_bigbatch_i9/` rerun, 9 from `ranking_stage_runtime_rcc_bigbatch_shared/`). No committed file changed.
              - **Validity, read locally:**
                - The 360TopL rerun is `complete`. Its explained-variance gate passes: PCA-5 7.9e-8, PCA-20 4.7e-8, both under 1e-6. Its code record equals the primary 23 sections'.
                - RCC timing: 7 summaries `complete`, all on the i9-10940X. All 24 full-ranking checks are `identical (full-ranking SHA-256)`: 6 sections × posterior-|PCC|, Moran's I, mean intensity and oracle. UH0505_12 has no saved ranking (not available, as before).
              - **PCA reconstruction summary** (supervisor 10:45; summariser `7eef7b8d`, equal to HEAD), about 10:45 SAST.
                - Command: `summarise_pca_reconstruction_v.py --rerun CAC/360TopL=results/diagnostics/pca_reconstruction_V/rerun_360TopL_bigbatch_i9/CAC/360TopL_seed1/summary.json --output results/diagnostics/pca_reconstruction_V/summary_local`, without `--conservative-not-done`.
                - **Printed wording: "Reconstruction error does not separate PCA-5 from the VAE."**
                - GBM 8/8, CAC 8/8 (360TopL from the labelled rerun), RCC 8/8 reported alone.
                - Counts and median ratios are in `summary_local/summary.json` and the supervisor chat (10:48).
              - **RCC timing retry 70528** (index 2, RCC_UH0710_33 only; Zayd's OK), submitted 10:46 SAST (08:46 UTC).
                - Same `--wrap` command and root as 70179. `--exclude=mscluster[42-54,56-70,72-73,75,77-89]` adds mscluster77, so mscluster55, 71, 74 and 76 are allowed.
                - `OverSubscribe=OK`; pending on `Priority`. The input file is visible from the login node (19,568 bytes).
              - **RCC timing retry widened** (Zayd's OK, 18 Oct; the requirement is the CPU model, not the original five nodes):
                - One `sinfo -p bigbatch -N` at 10:56 SAST: every node with a recorded i9-10940X (52, 55, 58, 71, 73, 77, 79, 81, 84, 86, 87) was `allocated` with 0 idle CPUs; none was down or drained.
                - **70528** was still PENDING and was cancelled (`CANCELLED`, never started).
                - **70530** submitted 10:56 SAST (08:56 UTC): index 2 (RCC_UH0710_33) only, with the same `--wrap` command and root, not exclusive (`OverSubscribe=OK`).
                - Allowed nodes: mscluster52, 55, 58, 71, 73, 79, 81, 84, 86, 87. `--exclude=mscluster[42-51,53-54,56-57,59-70,72,74-78,80,82-83,85,88-89]` excludes mscluster77 (the failure), mscluster54 (the 17 Oct file-visibility incident), 74 and 76 (model unrecorded) and every other `bigbatch` node.
                - The reproduction check and the `cpu_model` record are unchanged. The Monday 19 Oct 18:00 fallback (c) applies.
              - **20 October, outcome of 70530** (one `sacct` check, 09:46 SAST; chat 09:56):
                - `70530_2` COMPLETED, exit 0:0, on mscluster52. It ran 18:46:27–18:46:52 UTC on 18 Oct (20:46 SAST), before the Monday 19 Oct 18:00 SAST stop rule, so fallback (c) does not apply.
                - **Pull** 09:55 SAST (documented quiet artifact pull, `-n` first). It brought 2 files: the new `ranking_stage_runtime_rcc_bigbatch_shared/RCC_UH0710_33_seed1/uniform_mean/summary.json`, and `provenance/slurm_job_ids.txt`, which gains the 70528/70530 lines with its earlier content unchanged. Zayd OK'd the change to that committed file before the pull.
                - **Read locally:** `complete`. All 4 full-ranking checks (posterior-|PCC|, Moran's I, mean intensity, oracle) are `identical (full-ranking SHA-256)`; the posterior's maximum difference is 8.2e-7. `cpu_model` is `Intel(R) Core(TM) i9-10940X CPU @ 3.30GHz`.
                - **RCC timing:** 8/8 `complete` on i9-10940X ("shared node, not exclusive"). Exact reproduction holds in 7 sections (28/28 checks); UH0505_12 has no saved ranking to compare against.
              - **20 October 10:39 SAST, Section 6.6 (statistics plan):** the supervisor's 10:28 plan was copied verbatim into Section 6.6 before any statistics code existed. The proposed comparison family was posted to the chat for confirmation; nothing is computed until the supervisor confirms it. Local only; no cluster work.
              - **20 October 10:47–11:00 SAST, Section 6.6 run (local only; chat 10:46 and 11:00):** the family amendment was written as the dated Section 6.6 addendum before any code. Built `paired_statistics.py`, `compute_statistics_6_6.py` and `test_statistics_6_6.py` (14/14 local). All 38 rows reproduce their saved decisions' per-section values to 1e-12. Output `results/diagnostics/statistics_6_6/`, byte-identical on a second run. A first development run showed estimates beside 3 non-converged mixed models; the code was fixed to report "not converged" only, and that run was copied to the session scratchpad (its `tests.csv` is identical to the final run). Item 3 (Mann–Whitney) is "not done". Uncommitted, for Codex.
              - **20 October 11:42 SAST, Section 6.7 (Investigation 21):** the supervisor's 10:53 predeclaration was copied verbatim into Section 6.7 and `investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md` was started. Code facts were checked from the S3PL code and saved records only (no compute, no cluster work); facts and a costed plan were posted to the chat. Nothing is built or submitted until the supervisor checks that post; B, C and D each need Zayd's OK.
              - **20 October 11:54 SAST, Section 6.7 addendum and Part A (local):** the supervisor's 11:46 correction note and Q1–Q6 answers were written as the dated Section 6.7 addendum. Part A (preliminary) was built (`scripts/summarise_s3pl_seed_investigation_21.py`, `test_s3pl_seed_investigation_21` 11/11 local) and run to `results/diagnostics/s3pl_seed_investigation_21/part_a_preliminary/`; a second run was byte-identical in all 6 files. Uncommitted, for Codex.
              - **20 October 11:53 SAST (09:53 UTC), Investigation 21 gate job 72135 (Zayd's OK):** GBM12_2 released seed-1 repeat via `sbatch --wrap` around the unchanged `run_s3pl_massnet_gbm.sh`; `bigbatch`, `--exclusive`, recorded RTX 3090 nodes only (quarantine and mscluster54 excluded), in-job RTX 3090 guard; root `reproducibility/s3pl_investigation_21/gate_repeat/GBM12_2_p3_seed1_repeat/`. **FAILED** in 0 s on mscluster87, exit 127: `source: not found` (the wrap runs `/bin/sh`). No S3PL code ran; only the provenance folder exists. Stopped per Zayd's stop-on-failure instruction; fix proposed in the chat. Cluster S3PL code checked against HEAD first: 13 files, identical after removing carriage returns (5 cluster copies are CRLF, the same copies that made every saved S3PL run).
              - **20 October 12:02 SAST (10:02 UTC), gate retry 72136 (Zayd's OK; supervisor chat 11:58):** same command wrapped as `bash -lc '…'`, new root `gate_repeat/GBM12_2_p3_seed1_repeat_r2/` (the 72135 folder is kept as its record), **not exclusive**. `bigbatch` has no GPU Gres (`Gres=(null)`, no gpu in `CfgTRES`), so `--gres=gpu:1` cannot be requested; the job uses `cuda:0` with the RTX 3090 guard and logs other GPU processes at start. This pattern applies to every Investigation 21 GPU job. Started on mscluster73 with no other GPU process.
              - **Gate 72136 COMPLETED** (16:18, mscluster73). **Pull** 12:19 SAST, documented artifact pull with `-n` first: 9 new files, all under `reproducibility/s3pl_investigation_21/gate_repeat/`; no committed file changed. **Gate passed** against job 53121: all 10 losses identical, `mixed_f1` identical at every threshold, mSCF1 0.512 identical, peak-list SHA-256 identical (`c541e57a…`), both RTX 3090. The config logs differ only in `artifact_root` (by design) and in two keys that the August code did not write (`normalization`, `input_context_mode`; their defaults are the released path). Saved released runs are reused (Q2).
              - **12:23 SAST (10:23 UTC), Parts B and D chunk 1, array 72139 (tasks 0–27, %3; Zayd's OK):** task table `reproducibility/s3pl_investigation_21/provenance/tasks.tsv` (140 tasks: 0–11 GBM released seeds 2–3 for the 6 sections without them; 12–27 D paper-TIC seeds 2–3 × 8; 28–83 CAC released seeds 4–10; 84–139 GBM released seeds 4–10). Chunks of ≤ 48 tasks (QOS) are submitted one at a time. Same wrap pattern as 72136 (not exclusive, RTX 3090 nodes and guard, existing-run refusal); the runners are unchanged (`run_s3pl_massnet_gbm.sh`; CAC `main.py` with config defaults, as `run_s3pl_cac_seeds.sh`).
              - **12:38 SAST, concurrency raised to 5 (Zayd):** `scontrol update JobId=72139 ArrayTaskThrottle=5` (was 3); later chunks use `%5`. The `bigbatch` QOS allows 6 running per user; one slot stays free.
              - **13:30 SAST (11:30 UTC), chunk 2 = array 72190 (tasks 28–59, CAC released seeds 4–7, %5), `--dependency=afterok:72139`:** starts only after every chunk-1 task succeeds, so running jobs stay ≤ 5 and a chunk-1 failure blocks it. Same command as chunk 1 (checked against `manifest.txt`). At submission chunk 1 had 16/28 COMPLETED, 0 failed, 12 in the system (44 total, within the 48-job QOS).
              - **Chunk 1 (72139): 28/28 COMPLETED.** **Chunk 2 (72190): 26/32 COMPLETED, 6 FAILED** (indices 32, 37, 38, 45, 53, 54; 27–38 s each, on mscluster77/84/86/87). Every failure is `FileExistsError` on the shared `released/CAC/seed<S>/logs` or `/results` folder: concurrent CAC tasks of one seed raced to create it (the 66114 race). Only the per-seed roots had been pre-created, not their subfolders: a submission-setup fault, not a node, CUDA or S3PL fault. The failure happens while the output folders are created, before training; no run log or weight exists for the 6. **Stopped** (Zayd's stop-on-failure); nothing queued or retried; fix proposed in the chat.
              - **Pull** 14:04 SAST, documented artifact pull with `-n` first: 273 new files, all under `reproducibility/s3pl_investigation_21/`; no existing file changed.
              - **Part D run (local; `scripts/summarise_s3pl_investigation_21_bd.py --part D`, uncommitted for Codex; `test_s3pl_investigation_21_bd` and Part A tests 23/23 local):** output `results/diagnostics/s3pl_seed_investigation_21/part_d/`. **Label: "does not explain"** (with the 11:46 disclosure). TIC collection mean 0.303 vs released 0.324 (rise −0.021); paired TIC − released per-section seed means, n = 8: 5+/3−, exact p = 0.742, HL −0.012 [−0.154, 0.099].
              - **15:34–15:35 SAST (13:34 UTC), chunk-2 fix, step 1 (Zayd's OK; supervisor chat 15:33):** new submitter `reproducibility/s3pl_investigation_21/provenance/submit_chunk.sh`, piped to the login node. It refuses to submit if any selected task's `logs/s3pl`, `results/baselines/s3pl` or `checkpoints/baselines/s3pl` folder is missing, if a row does not match its index, or if the submission would take the queue over 48 tasks; `DRY_RUN=1` stops before `sbatch`. A dry run before the folders existed refused, as intended. **Folder creation then went wrong (my error):** `tasks.tsv` is space-separated, but I split it with `cut -f6` (tab-separated). The loop therefore ran `mkdir -p` of the three subfolder trees under every word of every row. The real roots got their subfolders (a dry run over 0–139 passed the folder check and refused only on the 48 limit), but **160 stray folders** were created directly in `$HOME/msi` (`0`…`139`, `GBM`, `CAC`, the 16 section names, `reference_spatial_max`, `paper_tic`). A read-only check found all 160 created at 13:34–13:35 UTC, each holding only the three empty trees; no pre-existing folder was touched. **Stopped:** nothing submitted; the cleanup needs Zayd's OK (chat 15:40).
              - **15:38 SAST, stray-folder cleanup (Zayd's OK; supervisor 15:37 conditions; new check-first rule for cluster file loops):**
                - **Echo pass** (posted to the chat): 160 names, each created at 13:34–13:35 UTC, with no files and exactly 8 empty subfolders. The plausible names (`GBM`, `CAC`, the section names) were checked explicitly. The run was 1,440 `rmdir` commands, bottom-up.
                - **Result:** exit 0. `ls -A $HOME/msi` matches the expected listing: 13 entries, i.e. the 173 before cleanup minus the 160. Working files are in `$HOME/msi/logs/inv21_cleanup/`, on the cluster only.
              - **15:38 SAST (13:38:45 UTC), retry 72269:** indices 32, 37, 38, 45, 53 and 54 (CAC seeds 4–7), `%5`, submitted with `submit_chunk.sh`. The dry run and the folder check passed for all 6 tasks.
              - **72269: 6/6 COMPLETED** (1:27–1:42 each, on mscluster84, 86 and 87). CAC seeds 4–7 now have 32/32 `picked_peaks` and `metrics.json` files (file count only).
              - **15:44 SAST, chunk 3 = 72276** (tasks 60–83, CAC released seeds 8–10, `%5`): submitted with `submit_chunk.sh` after a dry run with the folder check passed.
              - **72276: 24/24 COMPLETED**; CAC seeds 8–10 have 24/24 `picked_peaks` and `metrics.json` files (file count only). CAC released seeds 1–10 are now complete.
              - **15:58 SAST, chunk 4 = 72303** (tasks 84–115, GBM released seeds 4–7, `%5`): submitted with `submit_chunk.sh` after a dry run with the folder check passed. Expected time: about 15–21 min per task, so about 2 h for the chunk.
              - **72303: 32/32 COMPLETED** (10:04–22:43 per task; on mscluster84 ×10, 86 ×9, 87 ×9 and 56 ×4; mostly 3–4 tasks running at once). GBM seeds 4–7 have 32/32 `picked_peaks` and `metrics.json` files (file count only).
              - **18:45 SAST, chunk 5 = 72440** (tasks 116–139, GBM released seeds 8–10, `%5`): submitted with `submit_chunk.sh` after a dry run with the folder check passed.
              - **72440: 24/24 COMPLETED** (10:04–22:56 per task; on mscluster56 ×6, 84 ×6, 86 ×6, 87 ×5 and 80 ×1). Released runs on the cluster: 124/124 `metrics.json`, peak lists and config logs. **Part B GPU work is complete:** released seeds 1–10 for all 16 sections.
              - **Pull** 20:33 SAST, documented artifact pull, `-n` first. Result: 430 new files, all under `reproducibility/s3pl_investigation_21/`. One existing file was updated: the untracked `provenance/slurm_job_ids.txt`, whose cluster copy has the new job lines appended. No tracked file changed. `build_current_evidence_tables.py` was not rerun, because no file it reads changed.
              - **20:34 SAST, Part B summariser refused (stopped):** `summarise_s3pl_investigation_21_bd.py --part B` exits on its predeclared native-count check. CAC 240TopL released seed 7 (72190_55) has 256 picked peaks against `num_GT_peaks` 257. A count-only check found this is the only deviation in 160 runs.
                - **Cause:** this is the released code's own behaviour. `test.py:167–184` takes the top-z indices per patch, pools the distinct m/z and cuts the list at `num_GT_peaks`. That run's log reads "length of peak selection before cut-off = 256", so the list is short because only 256 distinct m/z were ever selected, not because anything failed.
                - Part A (`--set released`) was not run either, because it uses the same runs. A decision is needed (chat 20:36).
              - **20:39–20:44 SAST, option 1 implemented (supervisor 20:39; Zayd's OK), for Codex review:**
                - **Logged counts:** `provenance/selection_counts.tsv` records the logged distinct-selection count for all 140 tasks. It was transcribed from the Slurm `.out` files by grepping only the `task=` and cut-off lines, with each log's SHA-256. Its rows match `tasks.tsv`.
                - **Code:** the shared `check_peak_count` in the Part A script is used by both summarisers. It accepts a count equal to native when the log (if any) is at least native, and a count below native only when it equals the logged count. Part A applies it to the released set only.
                - **Tests:** 28/28 local, 5 of them new.
                - **Preliminary Part A:** rerun, identical except for the code hash.
              - **Cleanup result (supervisor 15:37, condition 2):** `ls -A $HOME/msi` after the cleanup matched the saved expected list exactly, 13 entries; posted in the chat at 20:45.
              - **20:54 SAST, Part D provenance note** (Codex 20:51 finding): added to the investigation document. `part_d/` was produced with the code from before the short-list change; it was neither regenerated nor edited.
              - **20:55 SAST, Part B and Part A-released (local, committed code):**
                - `part_b/` and `part_a_released/` under `results/diagnostics/s3pl_seed_investigation_21/`, both exit 0, each from 641 input files.
                - **Labels, as printed:** GBM B1 "outside our seed distribution", B2 "not explained by seed selection alone"; CAC B3 the same two labels.
                - Collection mean ± SD across the 10 seeds: GBM 0.3193 ± 0.0419, CAC 0.5470 ± 0.0377.
                - Short lists: 1/160, as reported.
                - Full outputs are in the chat at 20:55. Awaiting the supervisor's verification and Codex's review.
              - **21:06 SAST, Part C prerequisites (uncommitted, for Codex; nothing submitted):**
                - **Default-path bit-identity test:** `baselines/s3pl/tests/test_seed_flags_default.py`, with the frozen reference `fixtures/pre_seed_flags/train.py` (today's `train.py` with only the `3624b56b` hunks reversed). It is added to `run_fair_scoring_tests.sh`. Locally the 2 text-level tests pass; the run-level class needs torch, so it runs in the cluster test job.
                - **Part C summariser:** `scripts/summarise_s3pl_investigation_21_c.py` with tests; 37/37 local across Investigation 21. The nondeterminism clause is aggregated as "≥ 2 of 3 sections", which is Code's reading and is posted for the supervisor to confirm.
                - **Task table:** `reproducibility/s3pl_investigation_21/part_c/provenance/` (19 new runs: init 4, order 11, repeat 4; gate 72136 counts as one of the planned repeats). `submit_chunk.sh` now takes `PROV`.
              - **21 October 08:58 SAST, Part C clarification** (Codex finding 1, 08:55): the supervisor's 21:11 aggregation confirmation was written as the dated Section 6.7 clarification. Docs only; the committed code was not changed (chat 08:58).
              - **21 October 08:59 SAST, upload** (local → cluster, documented source upload, `-n` first, clean committed HEAD `2293ed5a`): 16 files. The 15 tracked files match HEAD by `sha256sum`; the 16th is the untracked editor file `baselines/s3pl/.pym2aia_prefs.xml` (timestamp only).
              - **Part C provenance copy:** `part_c/provenance/tasks.tsv` and `manifest.txt` were copied with `rsync -R`, `-n` first and no directory metadata changes, creating `part_c/provenance/`. Both match `3877fab4` by `sha256sum`.
              - **Cluster test job 72595** was submitted at 06:59 UTC (08:59 SAST) on `batch` (Zayd's OK, 21 October).
              - **72595 FAILED** (1:0, mscluster131, 7:51). The main suite passed: 259 tests, OK, 3 skipped. `test_seed_flags_default` crashed with `TypeError: DefaultRunTests.run() missing … 'name'`. Its classmethod helper `run` replaces `unittest.TestCase.run`, so neither bit-identity assertion ran. **The gate is not passed. Stopped** before any `mkdir` or submission, because the fix is a test-code change (Codex). Chat 09:12.
              - **10:05 SAST, gate fix (Codex 09:35 finding 1; supervisor 09:36: CPU required), uncommitted, for Codex.** The helper is renamed `train_once`. `setUpClass` now asserts `torch.cuda.is_available()` is False. The test job runs `test_seed_flags_default` in its own invocation with `CUDA_VISIBLE_DEVICES=""`. Fixture, assertions and configuration are unchanged. Local: 2/2 text-level tests (run-level class skipped, no torch); Investigation 21 37/37. Chat 10:05.
              - **10:41 SAST, upload** (local → cluster, documented source upload, `-n` first, clean HEAD `449a757b`; fix commit `178720e8`): `test_seed_flags_default.py` and `run_fair_scoring_tests.sh`, both matching HEAD by `sha256sum`. The untracked `.pym2aia_prefs.xml` was refreshed by timestamp only.
              - **Cluster test job 72625** (`batch`, mscluster129, 08:41 UTC, 5:55): **COMPLETED 0:0.** Main suite: 259 tests, OK, 3 skipped. S3PL modules: 25 tests, OK. `test_seed_flags_default`: 4 tests, OK, with both `DefaultRunTests` methods run and none skipped, on CPU (`GPU available: False`, device `cpu`). **The gate passed.**
              - **Folders:** an echo-first pass listed 57 subfolders (19 roots × 3), none existing. Created with one `mkdir -p` per subfolder. `part_c/` then held 172 directories (provenance + 19 roots + 19 × 8 nested) and 2 files.
              - **Dry run:** `DRY_RUN=1 PROV=…/part_c/provenance submit_chunk.sh 0-18` passed its checks for 19 tasks.
              - **72626 submitted** at 08:51 UTC (10:51 SAST): Part C tasks 0–18 at `%5`, on `bigbatch`, not exclusive, with the recorded exclude list and the RTX 3090 guard (Zayd's OK, 21 October).
              - **72626: 19/19 COMPLETED 0:0** (10:51–13:10 SAST, 10:18–16:43 per task). Only mscluster71 and 79 were free, so at most 2 ran at once. No retries.
              - **Pull** 13:17 SAST, documented artifact pull, `-n` first: 117 new files (111 under `part_c/`, including the updated untracked `slurm_job_ids.txt`, plus 6 test logs from 72595 and 72625). No tracked file changed. `build_current_evidence_tables.py` was not rerun, because no file it reads changed.
              - **13:17 SAST, Part C summariser** (committed code, local): exit 0. Wrote `results/diagnostics/s3pl_seed_investigation_21/part_c/` from 144 inputs; a second run was byte-identical. **As printed:** "initialisation dominant" (init ≥ 2× order in 2/3 sections, order ≥ 2× init in 0/3); "not dominated by nondeterminism" (0/3); repeats bit-identical in 3/3, repeat SD 0 in each section. Full outputs are in the chat at 13:18. Awaiting the supervisor's verification and Codex's review.
              - Cluster test 69798 passed with those tests run. The checklist was posted (chat 14:31). **69830** `submit_s3pl_cac_shuffle_control.sh` (tasks 0–15, at most 2 running) was submitted 14:31 SAST.
              - It started about 18:45 SAST, once seed-2 GBM dropped below 3 running. 16/16 COMPLETED (1:54–3:04 per task). **Pull** 19:15 SAST (`-n` first): 106 new files under `reproducibility/s3pl_cac_shuffle_control/`; no local file changed; Test R outputs excluded.
              - Validity: real reproduced from saved `metrics.json` in 16/16; every shuffled-run configuration as predeclared.
              - **Decision** (`results/diagnostics/s3pl_cac_shuffle_control/decisions_20261017_local/`): **"mixed"**. Real − retrained shuffled-nonlocal: seed 1 mean +0.039, at least 0.02 in 4/8; seed 2 mean +0.040, 3/8. Descriptive values in chat 19:17.
          - **Gap noted, not improvised:** 21:42 point 1 also asked for a per-run `validate_spatial_window_cache.py` check before training. It is not in the committed script, and the validator only accepts the window and attention variants (not `central_only` or 3×3 `uniform_mean`), so adding it needs a code change. It was reported in the chat. Cache equivalence rests on investigation 10.
      - **Consequence:** the two evaluators' code hashes change. Existing GBM/CAC results stay valid as saved, but rerunning one of them now reports STALE (exit 3) by design. All A–G scoring is complete, so no rerun is planned.

- **30 October, IG completeness reruns (Section 6.3 amendment "30 October: IG completeness reruns"):**
  - **About 13:35 SAST:** amendment and Section 6.1 cross-reference written before any rerun job existed. Code and tests reviewed and committed by Codex as `5806e2f1` (chat 13:46). HEAD at upload was `dcae5f77`; it adds only chat and report commits on top, with no change under `code/msi`.
  - **13:52 SAST (11:52 UTC), upload** (local → cluster, documented source upload from `code/msi`, `-n` first, clean committed HEAD `dcae5f77`): 9 files. These were the 6 new files (`scripts/summarise_ig_steps.py`, `slurm_jobs/{ig_steps_sections,run_ig_steps_rerun,run_ig_steps_fair_scoring,submit_ig_steps}.sh`, `src/spatial_msipl/tests/test_ig_steps.py`), the changed `slurm_jobs/run_fair_scoring_tests.sh`, `scripts/plot_s3pl_seed_distributions.py` (committed in `e9893505`, not previously uploaded) and the untracked editor file `baselines/s3pl/.pym2aia_prefs.xml` (timestamp only). `sha256sum` on the cluster matches the HEAD blobs for 14/14 files: the 8 tracked uploaded files plus the 6 dependencies the jobs call (`test_r_sections.sh`, `run_spatial_msipl_gmm_integrated_gradients.py`, `evaluate_spatial_msipl_attributed_peaks.py`, `evaluate_fair_scoring_baselines.py`, `gate_d_helpers.py`, `attribution.py`).
  - **13:54 SAST (11:54 UTC), cluster test job 78479** (5a; Zayd's OK in the session): `sbatch --parsable slurm_jobs/run_fair_scoring_tests.sh` on `batch` (2 CPUs, 8G, 30 min). Gate: `test_ig_steps` runs 15/15 (none skipped) and every module passes.
  - **78479 COMPLETED 0:0** in 5:01 on mscluster129 (one `sacct` check, 14:01 SAST). `s3pl_env` Python 3.11.5, NumPy 2.4.6, sklearn 1.9.0. Main suite: 274 tests OK, 3 skipped, the same local-artifact skips as before (`test_runtime_v2` ×2, `test_s3pl_shuffle_control` ×1). `test_ig_steps`: 15/15 ran and passed. S3PL suites: 25 and 4 tests OK. Empty `.err`. **Gate passed.** Records: `results/validation/fair_scoring_env_tests/78479_*`.
  - **14:03 SAST (12:03 UTC), GPU array 78481** (Zayd's OK in the session; checklist in chat 14:03): `bash slurm_jobs/submit_ig_steps.sh ig 0-11` was run on `bigbatch` with `%4`, not exclusive, and `--exclude` set to the 16-node quarantine. Tasks 0–3 are the failed arms at 128 steps, 4–7 the controls at 64 steps and 8–11 the controls at 128 steps. All 12 tasks were pending (Resources) at submission. The job ID is logged in `results/experiments/ig_steps_rerun_20261030/provenance/slurm_job_ids.txt`.
  - **14:09 SAST (12:09 UTC), moved to `batch`** (supervisor ruling 14:08, decision log D52; Zayd's OK in the session). `bigbatch` was overloaded, with all 12 tasks of 78481 pending (Priority).
    - `squeue`/`sacct` first confirmed that all 12 were still pending and none had started. Then `scancel 78481`, which `sacct` shows as CANCELLED.
    - No task root existed afterwards.
    - Resubmitted as **78483** with `SBATCH_PARTITION=batch bash slurm_jobs/submit_ig_steps.sh ig 0-11`. The script was not edited. Settings: `%4`, the same 16-node quarantine `--exclude`, and the CUDA warm-up in every task.
    - `--mem=24G` is unchanged, because every `batch` node has 30,000 MB.
    - All 12 tasks of every 64-vs-128 control pair now run on `batch` (RTX 3060). The saved 64-step runs were on `bigbatch` (RTX 3090, i9-10940X), so the saved-vs-rerun comparisons cross hardware, as ruled. If the GMM gate fails because of the CPU model, stop and post; no task is moved back.
  - **78483 outcome** (one `sacct` check, 14:40 SAST): 9/12 COMPLETED 0:0. The completed tasks are 0, 2, 3, 5, 6, 7, 9, 10 and 11, with elapsed times from 0:13 to 14:35. **Tasks 1, 4 and 8 FAILED with exit 5 (GMM gate).** All three are RCC_UH0505_12 `central_only` (s2 at 128 steps; s1 controls at 64 and 128), on mscluster134 (RTX 3060). Tasks 7 and 10 on the same node passed.
    - Per the Slurm `.out` gate line: `model_state_equal` true, `hard_assignment_equal` true, alignment succeeded (the IG script did not exit 5), **`identity_permutation` false**.
    - Matched evaluation did not run for these three; outputs are kept as written.
    - **Item stopped and posted** (chat 14:41). No retry and no gate change without a ruling.
  - **14:52 SAST, pull** (cluster → local, documented artifact pull, `-n` first; supervisor ruling 14:46 Q4; Zayd's OK). Before the pull, there were no uncommitted edits under `results/`. **229 new files:**
    - 150 under `results/experiments/ig_steps_control_20261030/`;
    - 76 under `results/experiments/ig_steps_rerun_20261030/`, including `provenance/`;
    - 3 under `results/validation/fair_scoring_env_tests/78479_*`.
    - No existing or tracked file changed. `build_current_evidence_tables.py` was not rerun, because none of its inputs changed.
  - **About 14:53 SAST, direct gate check (local, read only; ruling 14:46 step 1):** all 12 tasks of 78483 were compared with their saved 64-step runs, component by component. For **12/12**:
    - the hard assignment is equal;
    - the attribution pixel indices are equal;
    - the faithfulness pixel indices are equal (rebuilt from the saved labels, with the rebuild validated against the saved attribution indices);
    - the IG target per pixel is equal;
    - the component means and covariances after alignment are within 1e-6 (max 9.5e-7).
    - Tasks 1, 4 and 8 included. Table in chat 14:53. Script: scratchpad only (`direct_gate_check.py`), not committed.
  - **Gate v2 committed by Codex:** `4f3ed9b0` (code and decision records) and `e92a2653` (pulled evidence). The local Windows Bash-dependent tests were blocked for Codex (Git Bash `0xC0000142`); the supervisor's independent Linux run gave 45/45 (chat 15:12).
  - **15:15 SAST (13:15 UTC), upload** (local → cluster, documented source upload from `code/msi`, `-n` first, clean committed HEAD `157ac61b`). The documented command was used plus one narrowing `--exclude='/tmp/'`, because the preview showed two empty scratch folders under `code/msi/tmp/`.
    - 8 files: `scripts/{check_ig_steps_gate,summarise_ig_steps}.py`, `slurm_jobs/{run_ig_steps_gate_v2,run_ig_steps_rerun,run_ig_steps_fair_scoring,submit_ig_steps}.sh`, `src/spatial_msipl/tests/test_ig_steps.py`, and the untracked `.pym2aia_prefs.xml` (timestamp only).
    - `sha256sum` cluster vs HEAD: 13/13 match. That is the 7 changed files plus `ig_steps_sections.sh`, `test_r_sections.sh`, `run_fair_scoring_tests.sh`, the IG script and both evaluators.
  - **15:19 SAST (13:19 UTC), two jobs submitted on `batch`** (Zayd's OK in the session; checklists in chat 15:18):
    - **78515:** cluster test job `run_fair_scoring_tests.sh` (gate v2). Gate: `test_ig_steps` 26/26 and `test_test_r` 19/19 run, none skipped.
    - **78516:** archive-hash job (`--wrap`; item 5). `sha256sum` of the five archives in `/datasets/zsuliman/msi_data/zips/`, which are read only, into `results/validation/dataset_archive_hashes/78516.sha256`. It must reproduce the two recorded hashes.
    - **78515 COMPLETED 0:0** (5:01, mscluster129):
      - main suite: 285 tests OK, 3 skipped (the known local-artifact skips);
      - `test_ig_steps` 26/26 ran and passed, including the read-only check that gate v2 passes 12/12 on the cluster's 78483 outputs;
      - `test_test_r` 19/19;
      - S3PL suites: 25 and 4 tests OK;
      - empty `.err`. **Gate passed.**
    - **78516 COMPLETED 0:0** (2:04, mscluster143). Both recorded hashes were reproduced (`gbm_data.zip` `a69a4246…097f`, CardinalWorkflows `301a3815…c485`). The three new hashes are written into `docs/research/03` (Provenance check).
  - **15:28 SAST (13:28 UTC), gate job 78549** (Zayd's OK in the session; checklist in chat 15:27): `bash slurm_jobs/submit_ig_steps.sh gate 0-11` on `batch` (script default), `%4`. It writes v2 in all 12 roots, plus the matched evaluation for tasks 4 and 8.
    - **78549: 12/12 COMPLETED 0:0** (0–53 s each), with empty `.err`. v2 was written in all 12 roots. Tasks 4 and 8 ran the matched evaluation (complete). Task 1 is "IG completeness fails at 128 steps", with no evaluation.
  - **15:42 SAST, pull** (documented artifact pull, `-n` first): 34 new files (v2 files, the tasks 4/8 evaluations, `78515_*` and `dataset_archive_hashes/78516.sha256`). **One committed file was held back** with an extra `--exclude`: `results/experiments/ig_steps_rerun_20261030/provenance/slurm_job_ids.txt`. The cluster copy is the committed one plus one appended line (`78549 stage=gate …`), and the CLAUDE.md rule is to ask before a pull changes a committed file. No tracked file changed.
  - **15:42 SAST, `summarise_ig_steps.py`** (local; committed code): output `results/diagnostics/ig_steps_20261030/summary_pre_fair_scoring/`, exit 0. Gate v2 passes 12/12. Decision steps:
    - RCC_UH0505_12 `uniform_mean` s1: **128**;
    - RCC_UH9912_01 `uniform_mean` s3: **128**;
    - GBM39_2 `uniform_mean` s3: **128**;
    - RCC_UH0505_12 `central_only` s2: **pending** (fails at 128, p95 0.195; task 13 at 256 steps is next).
    - The "missing" 256-step rows of the three passing arms are not run by design.
  - **About 15:49 SAST:** the escalation beyond 256 steps (512, then 1024 as the cap; ruling 15:45, D37) was written into §6.3 before task 13 was submitted.
  - **15:49 SAST (13:49 UTC), two submissions on `batch`** (Zayd's OK in the session; checklists C and D in chat 15:45):
    - **78582:** `submit_ig_steps.sh fair 0,2-11` (11 rows, `%4`);
    - **78583:** `SBATCH_PARTITION=batch submit_ig_steps.sh ig 13`, i.e. RCC_UH0505_12 `central_only` s2 at 256 steps, with the quarantine `--exclude`.
  - **About 15:50 SAST, pull of the provenance log** (Zayd's OK; ruling 15:45: append-only log): `ig_steps_rerun_20261030/provenance/slurm_job_ids.txt`, single-file rsync, `-n` first. The only change is 3 appended lines (78549, 78582, 78583). Left for Codex to commit.
  - **Outcome (one check, about 16:02 SAST):**
    - **78582:** 11/11 COMPLETED 0:0 (0:06–2:01), all summaries `complete` (RCC bin level; GBM/CAC bin level and P1), empty `.err`.
    - **78583_13:** COMPLETED 0:0 (4:03, mscluster143). Gate v2 passed (identity recorded only: false). **IG valid at 256 steps**, and the matched evaluation is complete. **No escalation to 512 is needed** (D37 not triggered).
  - **16:05 SAST, pull** (documented, `-n` first): 75 new files (53 fair-scoring outputs, 22 for task 13). No tracked file changed.
  - **16:06 SAST, `summarise_ig_steps.py`** → `results/diagnostics/ig_steps_20261030/summary_post_fair_scoring/` (exit 0).
    - **Decision steps:** RCC_UH0505_12 `uniform_mean` s1 **128**; RCC_UH0505_12 `central_only` s2 **256** (p95 0.338 → 0.195 → 0.038 at 64/128/256); RCC_UH9912_01 `uniform_mean` s3 **128**; GBM39_2 `uniform_mean` s3 **128**.
    - **Controls** (fair-scoring bin-level IG mSCF1 at K_bin):
      - rerun 64 equals saved 64 in 4/4 arms (Jaccard 1, Δ 0). This includes **GBM39_2 `uniform_mean` s1 (saved IG version 1): reproduced exactly**, so the production table value stands (13:30 ruling).
      - 128 vs 64: Δ 0.0000 / +0.0002 / −0.0003 / 0.0000, Jaccard 1 / 0.9990 / 0.9978 / 1 (RCC_UH0505_12 centre s1, RCC_UH9912_01 uniform s1, GBM39_2 uniform s1, 40TopL uniform s1). The only differences are one-bin swaps at the K_bin boundary.
  - **16:08 SAST (14:08 UTC), 78676** (`submit_ig_steps.sh fair 13`; Zayd's OK): COMPLETED 0:0 (0:23), bin level `complete`. Pulled at 16:13 (3 new files plus the append-only provenance log, which now has 4 appended lines; Zayd's OK 15:45).
  - **16:15 SAST, composite root** (D32; local copy, never a move): `results/diagnostics/ig_steps_20261030/composite_root/`.
    - It holds 240 arm-level `summary.json` files copied from `fair_scoring_baselines/{rcc/bin_level_only, test_r/{bin_level_only,with_approved_partitions}, bin_level_only, with_approved_partitions}`.
    - The 5 previously empty slots are filled with the rerun summaries at their decision steps: RCC_UH0505_12 uniform s1 (128); RCC_UH0505_12 centre s2 (256); RCC_UH9912_01 uniform s3 (128); GBM39_2 uniform s3 (128, bin level and P1).
    - `manifest.csv` records destination, source, SHA-256 (each copy verified equal to its source) and role. The builder is `build_composite.py` beside it.
    - Provenance keys (evaluator code, parameters, approval) of the rerun summaries equal those of the saved campaigns (checked on 4 pairs).
  - **16:16 SAST, RCC seed-1 decision** (unchanged `summarise_rcc_fair_scoring.py`, `--root` composite `rcc/bin_level_only`) → `fair_scoring_baselines/rcc/decisions_20261030_ig_steps_local/`, exit 0.
    - `central_only`: unchanged, "mixed / not resolved by the predeclared rule" (bin −0.156, 0/8).
    - **`uniform_mean`: "incomplete; no verdict (7/8 runs)" → "mixed / not resolved by the predeclared rule"** (bin, 8/8 runs, mean −0.169, 0/8 positive; was −0.185 over 7).
    - The 17 October tables stay as the record.
  - **16:17 SAST, Test R summariser refused the composite** (unchanged `summarise_test_r.py --fair-root <composite>`, exit 1): "attribution …/ig_steps_rerun_20261030/RCC_UH0505_12_seed2/central_only/steps256/attribution/latent_mean.npy is not the seed-2 root". Its `expected_attribution` accepts only `/test_r_training_seeds/<section>_seed<S>/<arm>/attribution/` for seeds 2 and 3. **Stopped and posted, no patch** (13:30 answer 3). No output was written.
  - **Ruling 16:53:** the RCC uniform verdict is accepted. Approved: a Test R allow-list (explicit, read from `summary_post_fair_scoring/summary.json`, matching path step and gate v2) and an opt-in `--results-root` for the evidence tables. Codex reviews both.
  - **16:56 SAST (14:56 UTC), F and G on `batch`** (Zayd's OK; checklists in chat 16:19). Both are `sbatch --wrap`. In the same call: 3/3 script hashes matched HEAD, outputs absent, inputs present, gate v2 passed for the rerun.
    - **78721 (F):** `evaluate_spatial_segmentation_s.py` on the RCC_UH0505_12 `uniform_mean` 128-step rerun → `results/diagnostics/spatial_segmentation_S_ig_steps_20261030/RCC/RCC_UH0505_12_seed1/uniform_mean`.
    - **78722 (G):** `select_gmm_k_bic.py` and `bic_segmentation_sensitivity.py` on the same arm → `results/diagnostics/gate_d_bic_rcc_ig_steps_20261030/RCC_UH0505_12_seed1/uniform_mean`.
  - **Evidence tables, about 16:58 SAST:** no regeneration change is needed, and the approved `--results-root` (proposal 2) was **dropped** (ruling 17:00).
    - `build_current_evidence_tables.py` reads only the seed-1 GBM/CAC fair scoring, the gate (d) pixel counts, S3PL and the GBM/CAC BIC. No rerun touches any of these.
    - Run unchanged into a scratch folder, its 7 outputs were byte-identical to `results/publication/current_evidence/`.
  - **Test R allow-list** (ruling 16:53; uncommitted, for Codex): opt-in `--ig-steps-allow-list` in `summarise_test_r.py`. Without it, the output is byte-identical to `test_r/decisions_20261017_local/` (a test checks this).
    - Codex finding 1 (17:01, upheld 17:03): the substring check was replaced by an exact path equality.
    - Refusal tests cover an extra prefix, an extra suffix and a sibling tree.
    - Local: 52/52 (`test_test_r` 26, `test_ig_steps` 26).
    - The supervisor's independent Linux run (17:07) gave 51/52. The byte-identity test failed on line endings only: the references are LF in git but CRLF in the Windows working tree. The test now compares after CRLF → LF ("identical apart from line endings"); the summariser is unchanged. Local after the fix: 52/52.
  - **F and G outcome** (one check, about 17:07): 78721 COMPLETED 0:0 (0:23), 78722 COMPLETED 0:0 (0:45), both with empty `.err`. **17:11 SAST pull** (`-n` first): 4 new files under `spatial_segmentation_S_ig_steps_20261030/` and `gate_d_bic_rcc_ig_steps_20261030/`. No tracked file changed apart from the approved provenance log.
  - **Codex commits:** `c150fe28` (Test R allow-list and tests), `167dabae` (F/G evidence). Independent Linux run: 52/52 (chat 17:16).
  - **17:20–17:25 SAST, downstream regeneration** (local; committed code; new output folders; old tables kept as the record). Before each new run, the old table was reproduced from the saved inputs; all were identical after line-ending normalisation, except §6.6 `summary.json`, which differs only in the recorded Python version (3.14.3 vs 3.14.5).
    - **Test R:** `summarise_test_r.py --fair-root <composite> --ig-steps-allow-list summary_post_fair_scoring/summary.json` → `fair_scoring_baselines/test_r/decisions_20261030_ig_steps_local/` (exit 0; allow-list: GBM39_2 s3 uniform 128, RCC_UH0505_12 s2 centre 256, RCC_UH9912_01 s3 uniform 128).
      - **Decision 1:** the incomplete list is empty. GBM uniform s3, RCC centre s2, RCC uniform s1 and RCC uniform s3 each go from "incomplete (7/8 sections)" to "replicates".
      - The headline is still False: CAC centre and uniform at seed 2 "does not replicate", unchanged.
      - **Decision 2 (three-seed):** RCC "incomplete (6/8 sections)" → **equivalent** (bin +0.018, 6/8); GBM "incomplete (7/8 sections)" → **equivalent** (bin −0.0035, 3/8; P1 −0.0075, 2/8); CAC unchanged, "helps" (bin +0.023, 8/8; P1 +0.027, 8/8).
    - **Test V (d)**, VAE seed mean − PCA-5, descriptive (`summarise_segmentation_control_v.py --test-r-fair <composite test_r>` → `segmentation_control_V/decisions_20261030_with_test_r_ig_steps_local/`): RCC −0.011 (3/7) → −0.010 (3/8); GBM and CAC unchanged. Seed-1 verdicts unchanged.
    - **Test S** (composite `ig_steps_20261030/composite_root_test_s/`: 47 saved summaries plus the 78721 arm, with a SHA-256 manifest) → `spatial_segmentation_S/decisions_20261030_ig_steps_local/`.
      - **RCC uniform: "incomplete; no verdict (7/8 sections)" → "mixed (does not meet the 'helps' rule)"**, S1 − plain bin −0.021 (4/8), median +0.0001. One run is at −0.166.
      - All other Test S labels are unchanged.
    - **BIC RCC_UH0505_12 uniform** (78722): BIC selects K = 6, the largest candidate (monotone fall from K = 1 to 6; no interior minimum). Production refit ARI 1.0. **RCC BIC: 16/16 run-arms select K = 6** (was 15/15).
    - **§6.6** (composite project root `ig_steps_20261030/composite_root_6_6/`: the 7 source folders, with Test R, Test S and Test V seed means replaced by the new tables under the names the script reads; SHA-256 manifest) → `results/diagnostics/statistics_6_6_ig_steps_20261030/`.
      - Families are unchanged. 8 of 38 test rows change; **no Holm decision at 0.05 changes** (rows 3, 5, 6, 9, 10 and 30 significant before and after).
      - Changes: row 5 (RCC centre IG − posterior) n 7 → 8, p 0.0156 → 0.0078, Holm 0.047 → 0.047; row 6 (RCC uniform) n 6 → 8, p 0.031 → 0.0078, Holm 0.047 → 0.047; row 3 (CAC centre P1) Holm 0.047 → 0.031 (step-down only); row 13 (F3, RCC uniform − centre) n 6 → 8, mean +0.026 → +0.018, p 0.063 → 0.109, Holm 0.75 → 1; row 33 (F4, Test S RCC uniform) n 7 → 8, p 0.94 → 0.74, Holm 1 → 1.
      - The rows outside Holm (2, 11, 36) change only descriptively.
      - Mann–Whitney is unchanged. The RCC uniform mixed model is still "not converged".
    - **Evidence tables:** unchanged (7/7 byte-identical; see above).
- **30 October, msiPL Beta re-tune (Section 6.8):**
  - Amendment written at about 17:40 SAST. Code and tests committed by Codex as `a36ce869` (independent Linux run 71/71, chat 17:47).
  - **17:52 SAST (15:52 UTC), upload** (documented source upload from `code/msi`, `-n` first, clean committed HEAD `1866f3c8`, with the narrowing `--exclude='/tmp/'` for the two empty scratch folders): 12 files. These are the 8 item-2 files, `run_fair_scoring_tests.sh`, the committed Test R allow-list files (`summarise_test_r.py`, `test_test_r.py`; not uploaded before) and the untracked `.pym2aia_prefs.xml`.
  - **`sha256sum` vs HEAD:** 17/20 checked files match byte for byte. That covers the 11 tracked uploads plus the tuner, evaluators and `simple_baselines.py`.
  - The other 3 legacy msiPL dependencies (`baselines/msipl/LearnPeaks.py`, `Computational_Model_legacy.py`, `scripts/run_msipl_legacy_gbm.py`) differ **only in line endings**. The Windows working tree has CRLF or mixed endings, git stores LF, and git reports the files clean. The cluster copies equal the working tree, and after stripping CR they equal the HEAD blobs exactly (cluster and local). They are the same files that produced the saved legacy lists. Not changed.
  - **18:15 SAST (16:15 UTC), cluster test job 78779** (Zayd's OK; checklist in chat 17:53): `run_fair_scoring_tests.sh` on `batch`. Gate: `test_msipl_retune` 19/19, `test_ig_steps` 26/26 and `test_test_r` 26/26 run, none skipped.
    - **78779 COMPLETED 0:0** (5:54, mscluster129): main suite 311 tests OK, 4 skipped. `test_msipl_retune` 19/19 and `test_ig_steps` 26/26 ran and passed. `test_test_r` ran 25 and skipped 1: the byte-identity test, whose reference `test_r/decisions_20261017_local/` exists only locally (built locally, never uploaded). It passed locally and in the supervisor Linux run (52/52 and 71/71). The other 3 skips are the known local-artifact ones. S3PL suites 25 and 4 OK; empty `.err`.
  - **18:24 SAST (16:24 UTC), two CPU submissions on `batch`** (Zayd's OK; checklists in chat 18:23):
    - **78796:** GBM22_2 pilot sweep (`submit_msipl_retune.sh sweep 5`; 28G, 4 h).
    - **78797:** RCC_UH0505_12 `uniform_mean` cancer/normal sensitivity, `sbatch --wrap` (the unchanged evaluator with `--class-subset 0 1` on the 128-step rerun) → `fair_scoring_baselines/ig_steps_20261030/cancer_normal_bin_level_only/RCC_UH0505_12_seed1/uniform_mean/steps128`.
    - **78797 COMPLETED 0:0** (0:21), `complete`. Pulled at about 18:43 SAST: 6 new files (78797 output, `78779_*` test records); the running pilot's folder was excluded from the pull.
    - **RCC cancer/normal sensitivity regenerated** (composite `ig_steps_20261030/composite_root_rcc_cancer_normal/`: 15 saved arm summaries from `rcc_cancer_normal_sensitivity/bin_level_only` plus the 78797 arm; SHA-256 manifest) → `rcc_cancer_normal_sensitivity/decisions_20261030_ig_steps_local/` (unchanged `summarise_rcc_fair_scoring.py --sensitivity`, exit 0).
      - `uniform_mean` IG − posterior bin: −0.077 (n = 7; 1 positive, 6 negative) → **−0.054 (n = 8; 2 positive, 6 negative)**.
      - `central_only` is unchanged (−0.045; 3 positive, 5 negative). Descriptive, no verdict.
    - **Reproduction finding (Code's omission):** the 17 October RCC tables, primary and sensitivity, were built from the `with_approved_partitions` root. From that root they reproduce exactly (3/3 files each).
      - The 30 October regenerations (the primary at 16:16, without a prior reproduction check, and this sensitivity) used `bin_level_only` composites, because the IG rerun was fair-scored at bin level only.
      - Their bin-level columns are identical to 17 October for all 15 previously present run-arms; the verdicts (bin level only) are unaffected.
      - They lack the descriptive P1 "budget sensitivity" columns, which never enter a verdict. Posted to chat (18:45) with a proposed fix.
    - **Ruling 19:02:** the fix (like for like, D10), and **D38**: a reproduction check before every regeneration. "6/8" accepted.
    - **19:08 SAST (17:08 UTC), 78870** (Zayd's OK; `sbatch --wrap`, `batch`, 4G). The unchanged evaluator (hash matched HEAD in the same call) on the RCC_UH0505_12 `uniform_mean` 128-step rerun, under `with_approved_partitions` (`--partition-dir peak_partition_audit_rcc/RCC_UH0505_12 --partition-approval peak_partition_audit_rcc/partition_approval.json`), run twice:
      - primary → `ig_steps_20261030/with_approved_partitions/…/steps128`;
      - `--class-subset 0 1` → `ig_steps_20261030/cancer_normal_with_approved_partitions/…/steps128`.
      - The D38 reproduction check from that root was already done at about 18:43 (both 17 October tables identical, 3/3 files).
    - **78870 COMPLETED 0:0** (0:35): both `complete`, empty `.err`. **About 19:15 SAST pull:** 8 new files; the running pilot's folder was excluded; no tracked file changed.
    - **About 19:16 SAST, P1-complete regeneration (like for like):** composites `ig_steps_20261030/composite_root_rcc_p1/` and `composite_root_rcc_cancer_normal_p1/` (16 files each: 15 saved `with_approved_partitions` arm summaries plus the 78870 arm; SHA-256 manifests) → `rcc/decisions_20261030_ig_steps_p1_local/` and `rcc_cancer_normal_sensitivity/decisions_20261030_ig_steps_p1_local/` (unchanged summariser, exit 0).
      - **Stop check passed:** the bin-level columns are identical to the bin-only regenerations for all 16 rows in both tables, and the P1 columns are identical to 17 October for all 15 previously present rows. The verdicts are unchanged (centre and uniform "mixed / not resolved by the predeclared rule"; the sensitivity has no verdict).
      - **Changed P1 budget-sensitivity values** (descriptive, never in a verdict), IG − posterior, `uniform_mean`: primary −0.212 (n = 7, 0 positive) → −0.199 (n = 8, 0 positive); cancer/normal −0.084 (n = 7, 1 positive) → −0.062 (n = 8, 2 positive). `central_only` is unchanged (−0.179; −0.054). The new UH0505_12 uniform row at P1: IG 0.453, posterior 0.563, Moran's I 0.661, mean intensity 0.572 (primary).
      - **These `…_p1_local` tables supersede** the bin-only `…_20261030_ig_steps_local` RCC tables as the report source; the bin-only ones are kept as the record.
  - **Pilot 78796 cannot finish in 4 h (chat 21:48, correction 21:52).** At 21:44 SAST (19:44 UTC) it had run 3:19:58 of its 4:00:00 limit, still RUNNING with no output yet; m = 1 reproduction had passed, since there was no exit 5. Local timing of the legacy `LearnPeaks` at GBM size: about 10 s per Beta at 2.5, rising to about 127 s per Beta at 0 and below. Cause and fix are in the Section 6.8 implementation note. Codex commit `c625f52a`; supervisor ruling 21:51 (independent run 23/23); 78796 was not cancelled.
  - **21:54 SAST (19:54 UTC), upload** (documented source upload from `code/msi`, `-n` first, clean committed HEAD `f7bdc54a`, narrowing `--exclude='/tmp/'`): 3 files (`retune_msipl_beta.py`, `run_msipl_retune_sweep.sh`, `test_msipl_retune.py`), plus the timestamp of the untracked `.pym2aia_prefs.xml`.
    - **Git Bash note:** run under Git Bash, the excludes starting with `/` (`/tmp/`, `/data`) were path-converted and did not match in the preview. They were rerun with `MSYS_NO_PATHCONV=1`, and the second preview showed the expected list. Nothing was transferred before that.
    - **`sha256sum` vs HEAD:** 3/3 uploaded files match, as do `run_fair_scoring_tests.sh` and `tune_msipl_massnet_beta.py`. `LearnPeaks.py` differs only in line endings, as recorded at 17:52; CR-stripped it equals the HEAD blob.
  - **21:57 SAST (19:57 UTC), cluster test job 78981** (Zayd's OK; checklist in chat 21:56): `run_fair_scoring_tests.sh` on `batch`; hashes rechecked against HEAD in the same call. Gate: `test_msipl_retune` 23/23 run, none skipped.
  - **About 21:59 SAST (19:59 UTC), cancel, move and pilot** (Zayd's OK in the session; combined checklist in chat 21:58):
    - `scancel 78796`: **CANCELLED** at 3:34:11, with no outputs.
    - Echo first, then `mv -n results/baselines/msipl/retune_20261030/GBM/GBM22_2 → GBM22_2_78796_timeout`. The folder held only `retune_stdout.log` and the target did not exist. Kept as the record.
    - **Pilot 78983** (`submit_msipl_retune.sh sweep 5`, unchanged submitter; `batch`, 28G, 4 h; hashes matched HEAD `f7bdc54a` in the same call).
    - **Deviation:** the intended `afterok:78981` dependency did **not** attach. `sbatch` on this cluster ignored the `SBATCH_DEPENDENCY` input variable: `squeue %E` showed `(null)`. The task started at 19:59:21 UTC on a free node, before `scontrol update … Dependency=afterok:78981` could be applied ("Job is no longer pending").
      - The pilot therefore runs alongside the test job, not after it.
      - Its outputs count only if 78981 passes.
      - **Lesson:** like `SBATCH_EXCLUDE`, pass dependencies on the `sbatch` command line (`--dependency=`), then check `squeue -o %E` before relying on them.
  - **78981 COMPLETED 0:0** (8:40, mscluster143): 315 tests OK, 4 skipped, all needing local-only artifacts (the Test R decisions, two runtime-v2 tests, the S3PL shuffle control). S3PL 25/25 and 4/4. **Gate met:** `test_msipl_retune` 23/23 run, none skipped.
  - **78983 COMPLETED 0:0** (3:52, mscluster129; MaxRSS not recorded by this cluster).
    - Timings from the log: Beta-independent steps 4.4 s. The legacy check calls together took about 137 s, of which about 67–70 s each at 0.0 and −2.0 on real data. The 451-value sweep took 0.4 s.
    - `fast_path_check` was identical at 2.5, 1.05, 0.0 and −2.0 (counts 464, 1028, 27242, 27386).
    - `m1_reproduction` was identical (1028 peaks, max |Δm/z| 0).
    - `status: complete`.
  - **About 22:13 SAST (20:13 UTC), pull** (`-n` first): 19 new files under `results/` (the 78983 folder, the `GBM22_2_78796_timeout` record, `provenance/slurm_job_ids.txt`, the 78981 test records). No tracked file changed.
  - **22:16 SAST (20:16 UTC), sweep 78990** (Zayd's OK; checklist in chat 22:15): `submit_msipl_retune.sh sweep 0-4,6-23` (%6, `batch`, 28G, 4 h); hashes rechecked against HEAD `f7bdc54a` in the same call.
  - **78990, 22/23 COMPLETED 0:0** (GBM 2:51–7:27; CAC and RCC 4–6 s). None wrote `m1_reproduction.json` or `fast_path_check.json`.
    - **Task 2 (GBM12_1, mscluster144) stalled** on the HDF5 `Data` read from 20:20 UTC.
    - With Zayd's OK (22:4x) it was cancelled at 31:52 (22:48 SAST / 20:48 UTC). Its partial folder (only a 151-byte `retune_stdout.log`) was moved, echo first, with `mv -n` to `GBM/GBM12_1_78990_stalled`.
    - Index 2 was resubmitted alone as **79022**: the submitter's own `sbatch` line plus `--exclude=mscluster144` on the command line; `ExcNodeList` confirmed by `scontrol`; provenance line appended by hand; hashes matched HEAD in the same call. It started on mscluster129.
    - Node recorded in `cluster_node_issues.txt`.
  - **79022 COMPLETED 0:0** (3:19, mscluster129). Fast-path check identical at 2.5, 1.6, 0.0 and −2.0.
  - **About 22:57 SAST (20:57 UTC), pull** (`-n` first): 300 new files, all under `retune_20261030/` (23 sections × 13 files plus the stalled-run log), and an updated untracked `provenance/slurm_job_ids.txt`. No tracked file changed.
  - **Local check of all 24 `summary.json` files:**
    - all `complete` with 451 grid rows;
    - `fast_path_check` identical in 24/24;
    - `m1_reproduction` identical in 16/16 GBM/CAC.
  - **Flagged points** (predeclared: included and flagged; descriptive):
    - **`closest_outside_tolerance`, 7 points, all on GBM.** The target is below the grid's minimum count; Beta 2.5 is the grid end. GBM108_positive m 0.5 and 0.75; GBM12_1 m 0.5; GBM22_1 m 0.5; GBM39_1 m 0.5 and 0.75; GBM39_2 m 0.5.
    - **`msipl_cap`, 25 points.** CAC: 40TopL m 2.0. RCC: 24 points, where the grid maximum (1,054–1,308) is below K_bin in 6/8 runs. Those are MH0204_33, UH9812_03, UH9911_05 and UH9912_01 at m 0.75–2.0; UH0505_12 and UH9905_18 at m 1.0–2.0; and UH0710_33 at m 1.5–2.0. UH9610_15 has none.
    - **Correction (about 23:40):** the RCC grid maxima below K_bin are 1,054–1,289 (6 runs), not 1,054–1,308 as written above; 1,308 is UH0710_33, whose maximum exceeds its K_bin (1,212).
  - **23:01 SAST (21:01 UTC), scoring 79025** (Zayd's OK; checklist in chat 22:59): `submit_msipl_retune.sh score 0-23` (%6, `batch`, 8G, 2 h); hashes matched HEAD in the same call.
  - **79025 stopped at the gates (checked 23:09 SAST):** 4 COMPLETED, 19 FAILED (exit 1, all in the prefix gate), and task 1 (GBM108_negative) still running on mscluster144.
    - **16 GBM/CAC tasks:** "saved prefix legacy_msipl has no rebuilt ranking". The evaluator also stores the snapped legacy list in `rankings_prefix.npz`, and the scorer's gate treated it as a ranking. This is a scorer bug (Code's). The fix compares that entry with the snapped m = 1 list exactly; local tests 24/24; uncommitted for Codex.
    - **4 RCC tasks** (MH0204_33, UH0710_33, UH9911_05, UH9912_01): "oracle: rebuilt ranking differs from the saved prefix". This is the known CPU-model dependence. Their saved rankings came from 69565 on `bigbatch` mscluster71 or 76; the 4 that passed came from mscluster74, 77 and 55, and the rerun UH0505_12 uniform arm was on `batch`. The precedent is option (a) of 17 October: rerun on the node in `ranking_stage_runtime_rcc_bigbatch/provenance/task_node_map.txt`.
    - The failed tasks left only `scorer_stdout.log` in 20 `<section>_seed1/central_only/` folders. Nothing was read and nothing moved.
  - **Overnight, Zayd's pre-approval (chat 23:17 checklist A):**
    - `scancel 79025_1`: CANCELLED at 16:28 on mscluster144.
    - **23:18 SAST (21:18 UTC), upload** (documented command, `-n` first, `MSYS_NO_PATHCONV=1`, `--exclude=/tmp/`, plus `--exclude=/cluster_node_issues.txt`, the uncommitted local log): 2 files (`score_msipl_retune.py`, `test_msipl_retune.py`) and the prefs-file timestamp, from clean code HEAD `9f6909aa` (fix `199cb276`).
    - **`sha256sum` vs HEAD:** 5/5 match (with `run_fair_scoring_tests.sh`, `run_msipl_retune_scoring.sh` and `evaluate_fair_scoring_baselines.py`).
    - **Cluster test job 79056** was submitted in the same call.
    - **79056 COMPLETED 0:0** (5:42, mscluster129): 316 OK, 4 local-artifact skips; `test_msipl_retune` 24/24, none skipped; S3PL 25/25 and 4/4. `sacct` confirms the 69565 nodes.
    - **About 23:28 SAST (21:28 UTC), checklist B (chat 23:28):**
      - Echo first, then `mv -n` of the 20 failed `msipl_retune_20261030/<section>_seed1/central_only` folders (each only `scorer_stdout.log`) to `central_only_79025_failed`: 20 moved.
      - **79059:** GBM/CAC indices 0-15, `batch`, %6, `--exclude=mscluster144` (confirmed by `ExcNodeList`).
      - **RCC on their 69565 nodes** (`bigbatch`, `--nodelist`, confirmed by `ReqNodeList`): **79060** (16, MH0204_33, mscluster71), **79061** (18, UH0710_33, mscluster76), **79062** (22, UH9911_05, mscluster71), **79069** (23, UH9912_01, mscluster76).
      - Hashes matched HEAD in the same call. Provenance lines were appended by hand, since the submitter cannot pass `--exclude` or `--nodelist`.
    - **Checklist C (chat 23:28), two read-only CPU jobs** sent to `sbatch` on stdin with inline Python. No repository file was created on the cluster. Output folders were pre-created after a non-existence check.
      - **79057** (m/z axis of all 24 HDF5s → `results/diagnostics/mz_axis_20261030/mz_axis.json`): COMPLETED 0:0 in under 1 s on mscluster129.
      - **79058** (TIC, x, y and labels for GBM22_2, 160TopL and RCC_MH0204_33 → `results/diagnostics/dataset_figure_20261030/`): started on mscluster144.
    - **79082** (dataset-figure read, resubmitted with `--exclude=mscluster144` after 79058 stalled 7:48 on mscluster144 and was cancelled; the folder was empty): COMPLETED 0:0 in 0:31 on mscluster129.
    - **Pulls** (`-n` first; no tracked file changed): about 23:43 SAST, 111 new files (79059 tasks done by then, 79061/79069, 79057, 79082 and 79056 records; the running GBM12_2 folder excluded); about 07:15 SAST (31 October), 5 new files (GBM12_2 after 79059_3 COMPLETED in 13:20).
    - **79059 16/16 COMPLETED 0:0**; RCC 79061 and 79069 COMPLETED on mscluster76. **79060 and 79062 PENDING at 07:12** (mscluster71 runs another user's 3-day job).
    - **Summary stopped by its guard (chat 07:1x):** 8 RCC section-arms from 79025 carry the pre-fix `score_msipl_retune.py` (`c3050a3a`); the other 36 carry `a278ff0e`. No other hashed file differs. Clause 3 and the RCC table are not reported; a rescore of indices 17, 19, 20 and 21 needs Zayd's OK.
    - **31 October about 07:27 SAST (05:27 UTC), checklist D (Zayd's OK; chat 07:2x):**
      - `scancel 79060 79062` (pending, no output).
      - Echo first, then `mv -n` of the 8 pre-fix RCC section-arms (UH0505_12, UH9610_15, UH9812_03, UH9905_18 × 2 arms) to `<arm>_79025_prefix_code`: 8 moved.
      - **79295:** indices 17, 19, 20, 21 on `batch` (`--exclude=mscluster144`) with the fixed scorer.
      - **79296** (16, MH0204_33) and **79300** (22, UH9911_05) on `bigbatch --nodelist=mscluster79`, recorded as an i9-10940X; Zayd: the CPU model, not the node, matters. A gate failure there stops the line.
      - **All 6 COMPLETED 0:0**, gates passed: 79295 on `batch`; 79296 and 79300 on mscluster79 (i9-10940X).
      - **About 07:43 SAST, pull** (Zayd's OK; `-n` reviewed): 24 new files; the 8 committed pre-fix RCC `summary.json` replaced. Old against new: identical except the scorer code hash and runtime. The pre-fix copies are kept as `*_79025_prefix_code`.
      - **Summary** (committed `summarise_msipl_retune.py` `3fd2e4eb`) → `msipl_retune_20261030/decisions_20261031_local/`:
        - GBM both arms meet "IG beats legacy, robust to scoring" (clause 3 8/8 at every m).
        - CAC both arms do not: clause 3 is 5/8 at m 0.5 (centre +0.010, uniform +0.043); centre is also 7/8 at m 0.75.
        - Flagged: GBM 7 `closest_outside_tolerance` per arm; CAC 1 `msipl_cap`.
        - RCC count-matched: legacy 0.157, IG 0.367/0.368, IG > legacy 8/8; 6/8 runs capped (descriptive).

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

- **31 October, dataset figure support (read-only CPU jobs on `batch`, `--exclude=mscluster144`, stdin scripts using the committed `read_h5_metadata`; Zayd's OKs 07:4x and 08:0x):**
  - **79301:** per-pixel TIC and labels for all 24 sections → `results/diagnostics/dataset_contact_20261031/`. COMPLETED 0:0 in 3:00 on mscluster127; pulled about 07:53 SAST (25 new files).
  - **79303:** GBM base-peak intensity (max over m/z) and labels for the 8 GBM sections → `results/diagnostics/dataset_basepeak_gbm_20261031/`. COMPLETED 0:0 in 3:28; pulled about 08:12 SAST (9 new files).
  - **Findings:**
    - The GBM MassNet HDF5 spectra are TIC-normalised: TIC = 1 in every pixel (SD 2.5e-16), so GBM is shown by base peak.
    - CAC class 0 is the outer, border-touching region in 8/8 sections, with the highest mean TIC (100–139). It is background by position; "lowest TIC" does not hold.
    - CAC classes 1 and 2 (tumour / healthy) are not identifiable from the data or from S3PL.
    - RCC class 2 (unannotated) has the lowest TIC in 8/8 runs.
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


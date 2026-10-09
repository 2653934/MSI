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
  - **BIC plan approved as the specification with changes**, now written into Section 6 ("BIC run specification"): no GPU IG at any BIC or forced K; an optional, labelled CPU posterior-|PCC| sensitivity with no trigger or verdict; results per section-arm only, with no arm or collection verdict; and BIC runs only after the GBM108_positive decision table has been reviewed.

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

# Fair-scoring and simple-baseline protocol (v3.1, 9 October 2026)

Status: **protocol v3; implementation revised for cluster operation and provenance; nothing submitted.** No existing evidence, figure, table or report claim is replaced by anything here. This document supersedes the protocol parts of `docs/meetings/supervisor_review_2026-10-09_response_to_codex.md` wherever the two differ.

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
  - **IG and L2:** the saved bin lists in order, and their saved mSCF1 to 1e-12.
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

**Approval.** A reviewer writes `partition_approval.json` listing the approved partitions, their parameters and the per-section hashes. The scoring script refuses to run the peak-level analysis without it, and refuses again if any hash differs.

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

## 6. Gate (d): bounded GPU tests on development sections (helpers prepared; production script not modified)

**BIC-selected K** (CPU on saved latents; IG then needs GPU):

- Candidates K ∈ {1, …, 6}. StandardScaler, full covariance, `n_init` 20, `random_state` = the production seed, otherwise sklearn defaults identical to production.
- If ΔBIC < 10, choose the smaller K.
- **Failure rule (amended during implementation):** sklearn reports convergence only for the best of its `n_init` initialisations. A K whose best fit has not converged, or whose fit raises an error, is excluded and recorded. Per-initialisation convergence counts would need refits with `n_init` = 1 and different seeds, which would no longer reproduce the production fit, so they are not collected.
- **Provenance check:** refitting the production K on the saved latents must reproduce the saved assignments (ARI ≥ 0.999), or the script stops. On GBM108_positive/uniform_mean this check gave ARI 1.0. That is code validation only; the BIC outcome was not inspected.
- **If BIC selects K = 1, that is the primary result:** "no supported multi-cluster latent structure under BIC". A forced best-K ≥ 2 IG run may be reported only as a separately labelled sensitivity analysis and is never called BIC-selected IG.
- Balanced accuracy is not computed when K differs from the class count; ARI and NMI only.

**Attribution-pixel count** (the only variable changed):

- The production sample is preserved exactly. The same seeded generator (`sampling_seed + 700`, shared sequentially across components in label order) produces one permutation per component.
- Attribution pixels are positions 0–11, as in production; faithfulness pixels are positions 12–43, unchanged.
- The 48- and 192-pixel arms add positions 44 onward, so the sets are nested: 12 ⊂ 48 ⊂ 192.
- If a component has too few pixels, n = 12 + min(target − 12, available − 44), and the actual n is recorded. An arm whose capped n equals the next smaller arm's n is marked "not distinct". Fewer than 44 pixels in a component is an error, as in production.
- Aggregation stays |IG| as in production. **Signed versus absolute aggregation is a separate later ablation at n = 12.** Extra sampling seeds are a separately labelled replication, because changing the seed changes the production 12-pixel sample.

## 7. Decision thresholds

Unchanged from the previous response: 0.02 mSCF1 practical signal, per collection, seed 1.

- **IG adds value beyond its segmentation target:** IG − posterior-|PCC| (balanced) ≥ 0.02 in mean and > 0 in at least 6 of 8 sections, at bin level and under every approved partition.
- **Equivalent:** the mean difference is within ±0.02.
- **IG beats legacy, robust to scoring:** at least 7 of 8 sections at bin level, with the same direction in the K_bin collapse diagnostic, and the ordering stable across the budget multipliers. The collapse diagnostic is **not** a matched peak-level comparison; a matched one needs the Beta re-tune in Section 1.
- **Development-section GPU tests:** a change below 0.02 means the production setting stands. A change of 0.02 or more on both development sections triggers a predeclared 16-section rerun of that one setting only.

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
  - The partition audit requests 24 GB, 4 CPUs and 1 h.
  - The fair-scoring array task requests 16 GB, 4 CPUs and 2 h for both arms of one section.
  - Each task records GNU-time elapsed time and peak RSS when `/usr/bin/time` exists.
  - **Run the pilot index first (GBM22_2, the largest section)** and read `sacct --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode` before submitting the rest and before lowering or raising the requests.
- **Arrays.**
  - One task per section, scoring both arms as one independently auditable unit.
  - Concurrency is set at submission with `--max-concurrent N`. If omitted, Slurm and QOS limits apply.
  - The decision table is a separate job (`run_fair_scoring_summary.sh`). It refuses to mix results with different code, parameters or approvals, and gives no verdict for a collection with fewer than 8 sections.
- **Output roots.** Bin-level-only runs go to `fair_scoring_baselines/bin_level_only/`; runs with an approved partition go to `fair_scoring_baselines/with_approved_partitions/`.
- **No CUDA.** These jobs are CPU-only and use no CUDA preflight or GPU quarantine. Any later IG job (gate d) must use the real CUDA warm-up and read exclusions from `slurm_jobs/gpu_cuda_quarantine.txt`.
- **Environment compatibility.** `run_fair_scoring_tests.sh` runs the new test modules plus `test_peak_selection` and `test_evaluation` under `s3pl_env` (Python 3.11.5 per `environment.yml`). It records package versions in `results/validation/fair_scoring_env_tests/`. **It must pass before any real section is processed.** Local runs on Python 3.13 with NumPy 2.5 and sklearn 1.9, and on Python 3.11.17 with NumPy 1.26.4, sklearn 1.3.2 and SciPy 1.11.4 (an approximation of `s3pl_env`), both pass 44/44 tests. Neither establishes cluster compatibility.

**Submission order (after approval of this protocol and code):**

1. `sbatch slurm_jobs/run_fair_scoring_tests.sh`.
2. **Only after step 1 passes under the real `s3pl_env`:** `bash slurm_jobs/submit_peak_partition_audit.sh pilot`; check `sacct`, then submit `all`, optionally with `--max-concurrent N`.
3. Review the S1 verdict and the S2/S3 diagnostics, then write `partition_approval.json` or record a rejection.
4. `bash slurm_jobs/submit_fair_scoring.sh pilot`, then `all`. Add `--approval FILE` only for the approved-partition run.
5. `sbatch slurm_jobs/run_fair_scoring_summary.sh bin_level_only` (or `with_approved_partitions`).
6. Only then consider gate (d).

**Resolved before the audit (v3.1): S2 on CAC.** S2 is now descriptive and S1 (width < 0.5 Da) is the only hard rule. The decision was made on structural grounds (bin count depends on axis resolution), without seeing any real audit output. Code: `check_partition_sanity` returns S2 values under `diagnostics`; audit version 3. Tests: the chained-axis case still fails S1 but not S2, and a new test shows a many-bin group narrower than 0.5 Da passes.

## 10. Executions on real data so far (record)

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
| `patches/gate_d_attribution_total.patch` | **Not applied.** Opt-in `--attribution-total` for the IG script |
| `slurm_jobs/fair_scoring_sections.sh` | Shared ordered section list, input paths and pilot index |
| `slurm_jobs/run_fair_scoring_tests.sh` | `s3pl_env` compatibility test (synthetic data only) |
| `slurm_jobs/run_peak_partition_audit_array.sh`, `submit_peak_partition_audit.sh` | Partition-audit array on `batch` with 24 GB, plus its submitter |
| `slurm_jobs/run_fair_scoring_array.sh`, `submit_fair_scoring.sh` | Per-section scoring array on `batch` with 16 GB, plus its submitter |
| `slurm_jobs/run_fair_scoring_summary.sh` | Separate decision-table job |
| `slurm_jobs/check_fair_scoring_campaign.sh` | Login-safe status listing |
| Tests: `test_peak_groups.py`, `test_simple_baselines.py`, `test_gate_d_helpers.py`, `test_provenance.py`, `test_fair_scoring_pipeline.py` | 44 tests including the existing `test_peak_selection`. They add the S1-only width test, the three-class oracle, strict legacy, stale and bare-summary refusal, tampered-hash refusal before scoring, peak-level reconstruction, and the Slurm guard |

**Removed:** the v2 single-allocation jobs `slurm_jobs/audit_peak_partitions.sh` and `slurm_jobs/evaluate_fair_scoring_baselines.sh` (untracked, never submitted).

**Cluster note:** production jobs run `unittest discover` over the tests folder, so these tests will also run there, adding about 40 s.

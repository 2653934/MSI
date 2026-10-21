# S3PL seed sensitivity and the GBM reproduction gap

Status: 20 October 2026, 11:45 SAST. Started. The specification is protocol 18 Section 6.7 (copied verbatim from the supervisor chat, 20 October 10:53). The code facts below were checked from the code and saved records; nothing has been computed or submitted for this investigation.

## Question

Our S3PL GBM score is 0.30–0.34 (three initialisation seeds) against the published 0.496. In 7/8 sections the published value lies above all three of our seeds, and single sections swing a lot between seeds (GBM108_positive: 0.026 / 0.444 / 0.079). What causes the gap, and why do seeds change the result so much?

Candidate causes (Section 6.7):

1. initialisation and seed luck, including best-of-N reporting;
2. which part of the seed matters (weight initialisation, data order, GPU nondeterminism);
3. preprocessing: the paper says TIC, but the released helper does something else (see fact 4);
4. hyperparameters tuned on the test sections in the paper (investigation 19). Discussed in the report, not tested.

## Code facts (checked 20 October)

Sources: `code/msi/baselines/s3pl/train.py`, `main.py`, `utils/helpers.py`, `utils/data_source.py`, `utils/nonlocal_shuffle.py`, and the saved runs under `code/msi/results/baselines/s3pl/`, `code/msi/logs/s3pl/` and `code/msi/reproducibility/s3pl_*`.

1. **The released seed (`random_seed`)** seeds Python `random`, NumPy, `torch` and `torch.cuda` once (`train.py:45–48`). The same stream then drives, in order:
   - a NumPy permutation of the index list (`train.py:83–84`);
   - the model's weight initialisation (torch global RNG);
   - the mini-batch order: `SubsetRandomSampler` has no generator, so it draws from the torch global RNG *after* initialisation.

   So in the released code, initialisation and data order are entangled: one seed sets both.
   - No cuDNN flags are set anywhere (`cudnn.deterministic`, `cudnn.benchmark` and `use_deterministic_algorithms` are absent). Dropout is 0, so the forward pass draws no random numbers.
   - **Patch sampling.** The GBM input is HDF5 (`gbm_massnet/<section>.h5`). Its patches are deterministic, and missing neighbours are zero. CAC is imzML, read by m2aia's `SpectrumDataset`, which fills missing edge neighbours with `np.random.choice` at load time (global NumPy RNG). This is the code path the Test N wrapper re-derives.
2. **Separate seed streams already exist,** as an opt-in diagnostic (commit `3624b56b`):
   - `--initialization_seed` re-seeds torch just before the model is built;
   - `--sample_order_seed` seeds the index permutation and gives the sampler its own `torch.Generator`.

   Both must be set together. When neither is given, the released path runs unchanged. **However, no unit test covers this path or proves that the default path is bit-identical.** Also, a controlled run with init 1 / order 1 is *not* the released seed-1 run, because the streams differ.
3. **The saved GBM "seeds 1–3" are controlled runs,** not released-seed runs: initialisation seeds 1–3 with sample-order seed 1 (`comparisons/s3pl_gbm_stability_runtime/s3pl_gbm_seed_screen.csv`, investigation 16). The released-seed GBM runs are:
   - seed 1 in all 8 sections (jobs 53118–53125, `results/baselines/s3pl/massnet_gbm_summary_p3/`);
   - seeds 2 and 3 for GBM108_positive and GBM108_negative only (`reproducibility/s3pl_massnet/*_reference_spatial_max_seed{2,3}`).

   CAC released seeds 1–3 are complete for all 8 sections.
4. **Normalisation.** `reference_spatial_max` (the released default) takes `max` over axis 2 of the `(1, D, p, p)` patch. That axis is one *spatial* direction, so it is neither TIC nor a per-spectrum maximum, as investigation 11 already noted. Section 6.7 calls it "the per-spectrum maximum"; that wording needs correcting. `paper_tic` already exists as an option: each pixel in the patch is divided by its sum over m/z.
5. **Saved per run:**
   - the picked-peak list (`picked_peaks_*.csv`);
   - `metrics.json`;
   - `runtime_metrics.json` (training, evaluation and total seconds, GPU model, peak GPU memory);
   - the config log with `train_history`. This is the **last-batch** MSE per epoch, not an epoch mean; epoch means exist only in runs made with `--checkpoint_epochs`.

   These are present for the GBM init screen (24 runs), the GBM released seed 1 (8 runs), and the CAC released seeds 1–3 (24 runs).
6. **Bit-for-bit reproduction.** The saved repeat of released seed 1 on GBM108_positive (`GBM108_positive_p3_seed1_repeat1`) matches the original job 53118 in all 10 losses, in mSCF1 (0.033) and in the peak-list SHA-256. Both ran on an RTX 3090. One section with one repeat cannot rule out nondeterminism on other GPU types.
7. **Additional saved controlled runs:**
   - GBM108_positive has initialisation seeds 1–10 at order 1, and init 1 and init 2 each at order 2;
   - 25- and 50-epoch versions of init 1 and init 2.
8. **A paper-TIC GBM run already exists:** seed 1, all 8 sections (`reproducibility/s3pl_massnet/*_p3_paper_tic_seed1`). Part D is therefore **not blind for seed 1**. Its values were already saved, and Code saw them while taking this inventory.
9. **GPU time per run (saved `runtime_metrics.json`, all on an NVIDIA RTX 3090; excludes queue and job start-up):**

   | Run | Training (s) | Total, training + evaluation (s) |
   |---|---|---|
   | GBM p = 3, released, 10 epochs | 495–1,070 | 583–1,253 (mean about 916, i.e. 15 min) |
   | GBM paper-TIC | 282–601 | — |
   | CAC p = 9, released, 10 epochs | 41–63 | 53–84 |

10. **Cluster copies of the code (checked 20 October before any submission):** the 13 S3PL code and runner files on the cluster match HEAD once carriage returns are removed. Five of them are CRLF on the cluster: `config.json`, `data_configs.py`, `utils/helpers.py`, `utils/PeakEvaluation.py` and `model/Attention3DConvAutoencoder.py`. These are the copies that produced every saved S3PL run, so they are left unchanged (supervisor chat 11:58).
11. **GPU allocation:** `bigbatch` has no GPU Gres configured, so Slurm cannot reserve a GPU. Investigation 21 jobs are not exclusive. Each one uses `cuda:0`, refuses any GPU that is not an RTX 3090, and logs other GPU processes at start. GPU runtimes are therefore descriptive only.

## Plan and costs

See the chat entry of 20 October (Code → Supervisor, Investigation 21 code facts and plan). Order: A, then D and B, then C. A uses saved data only. B, C and D each need Zayd's OK and the pre-submission checklist.

## Summary of results, Parts A–D (21 October; for Codex review)

All four parts are complete and verified by the supervisor (chat 20 October 15:33 and 20:57; 21 October 14:21). The wording below is the supervisor's. Every score is S3PL's own in-job mSCF1 (the metric of the published 0.496 / 0.601), not the fair-scoring evaluator. Released settings throughout: 10 epochs, p3, z256, `reference_spatial_max`. Outputs are in `code/msi/results/diagnostics/s3pl_seed_investigation_21/` (`part_a_released/`, `part_b/`, `part_c/`, `part_d/`).

**Gates.**
- Released seed-1 repeat 72136 is bit-identical to the August job 53121, so saved released runs were reused.
- The CPU identity test of the opt-in seed flags (72625) passed, so the default path is unchanged.
- Disclosure beside A and B: "1/160 released runs returned 256 of 257 peaks (released distinct-m/z cut-off; CAC 240TopL seed 7)".

**B, the published values against our released seeds 1–10.**
- **Labels:** B1 (GBM) "outside our seed distribution", B2 (GBM) "not explained by seed selection alone"; B3 (CAC) the same two labels.
- **GBM:**
  - The published 0.496 is about 4.2 SD above our mean across 10 seeds (0.319 ± 0.042), and above every seed-level collection mean (max 0.374).
  - Taking the best of 10 seeds in every section reaches 0.434.
  - In 6/8 sections the published value is above all 10 of our seeds. The largest gap is GBM22_2: published 0.61, our maximum 0.365.
  - GBM108_negative and GBM39_2 are within our range.
  - Untested remaining candidates: the data version or preprocessing of those sections (not the TIC choice, per D), and the paper's tuned-on-test hyperparameters (cause 4, reported and not tested).
- **CAC:**
  - The published 0.601 is just outside our range (seed-level max 0.591), about 1.4 SD above our mean (0.547 ± 0.038).
  - Best of 10 reaches 0.5998.
  - This margin is within the published values' 2-decimal rounding (per-section mean 0.60125). So CAC is consistent with a favourable seed or best-of-several selection, but not shown to be.

**A, why seeds change the values** (released seeds, 8 sections × 10 seeds per collection; descriptive).
- About 52% of the variance is between sections, about 0–1% is a seed main effect, and about 47% is a section × seed interaction, in both collections. (ANOVA shares: GBM 0.526 / 0 / 0.474; CAC 0.523 / 0.008 / 0.469. The GBM mixed model did not converge.)
- Seeds don't shift whole collections; they flip particular sections between distinct outcomes:
  - GBM: GBM108_negative, GBM108_positive, GBM12_2 and GBM39_2;
  - CAC: 240TopL and 520TopL.
- Largest gaps are 0.20–0.45. In flipping sections the two outcomes select largely different peaks: J ≈ 0.01–0.12 for some seed pairs.
- Final training loss vs score shows no consistent relationship (r from −0.83 to +0.76).

**C, which part of the seed matters** (GBM108_positive, GBM108_negative and GBM12_2; 5 init seeds, 5 order seeds, 3 repeats).
- **Labels:** "initialisation dominant" (init SD ≥ 2× order SD in 2/3 sections) and "not dominated by nondeterminism" (0/3).
- **SDs, init / order / repeat:** GBM108_positive 0.222 / 0.0006 / 0; GBM108_negative 0.226 / 0.146 / 0; GBM12_2 0.128 / 0.010 / 0.
- **Repeats:** on the RTX 3090, rerunning the same seed is bit-identical (losses, scores and peak lists) in all 3 sections. GPU nondeterminism contributes nothing measurable.
- **What drives the seed effect: the weight initialisation.**
  - Varying the init (order fixed) moves GBM108_positive between about 0.02 and 0.45, and GBM12_2 between about 0.27 and 0.52, in two clusters.
  - Varying the order (init fixed) barely moves them (SD 0.0006 and 0.010).
- **Exception:** in GBM108_negative the data order also flips the outcome (0.36–0.41 vs 0.65). There both matter (ratio 1.55, below the 2× rule).
- **Bounded interpretation:** S3PL training under the released preprocessing has at least two distinct solutions in these sections, and the starting weights mostly decide which one it reaches. That is 3 sections × 5 seeds, descriptive.
- **Disclosure (Q5):** GBM108_positive's pattern was largely visible from saved runs before C.

**D, preprocessing** (GBM, 8 sections × seeds 1–3, paper TIC vs the released helper).
- **Label:** "does not explain; seed 1 existed before the predeclaration (0.289 vs 0.316) and was seen during the inventory; seeds 2–3 are blind".
- **Numbers:** collection means TIC 0.303 vs released 0.324. Paired TIC − released (n = 8): exact p = 0.742, Hodges–Lehmann −0.012 [−0.154, 0.099].
- TIC doesn't raise the GBM mean, so the paper's stated normalisation is not the cause of the gap.
- **Descriptive observation (not a rule result):**
  - Per-section seed SD is median 0.011 (0.008–0.018) with TIC, against 0.061 (0.027–0.229) with the released helper.
  - Under TIC every section sits in 0.25–0.36, and the flipping sections stop flipping.
  - The released preprocessing goes with much higher seed sensitivity, and it also gives the higher-scoring outcomes (GBM108_negative 0.58–0.66 vs about 0.31).
  - With TIC, the split seen in C disappears.

## Results

### Part A, preliminary (20 October; descriptive; saved runs only)

Output: `code/msi/results/diagnostics/s3pl_seed_investigation_21/part_a_preliminary/` (`runs.csv`, `sections.csv`, `jaccard_pairs.csv`, `variance.csv`, `summary.json`, `seed_scores_per_section.png`). Script: `code/msi/scripts/summarise_s3pl_seed_investigation_21.py --set preliminary`.

The two collections use different seed modes:
- GBM uses the controlled initialisation screen (init seeds 1–3, order seed 1).
- CAC uses released seeds 1–3.

The scores are S3PL's in-job mSCF1, recomputed unrounded. The primary decomposition will be the same analysis on released seeds 1–10 after Part B. Interpretation waits for the supervisor.

### Gate (GBM12_2 released seed-1 repeat)

- **Job 72135** failed before running S3PL, because the `--wrap` shell has no `source`.
- **The retry, 72136, passed.** It is bit-identical to job 53121 in all 10 losses, `mixed_f1`, mSCF1 and the peak-list SHA-256. Saved released runs are therefore reused.

### Part D (20 October; awaiting the supervisor's check)

Output: `code/msi/results/diagnostics/s3pl_seed_investigation_21/part_d/`.

- **Label:** "does not explain; seed 1 existed before the predeclaration (0.289 vs 0.316) and was seen during the inventory; seeds 2–3 are blind".
- **Collection means:** paper-TIC 0.303, released helper 0.324 (per-section means over seeds 1–3).
- **Paired TIC − released** (n = 8): exact p = 0.742, Hodges–Lehmann −0.012 [−0.154, 0.099].
- **Provenance note (Codex review 20:51):** `part_d/summary.json` was produced **before the short-list change**. Its recorded code hashes are:
  - `summarise_s3pl_investigation_21_bd.py` `4c4780ffb62177c1…`;
  - `summarise_s3pl_seed_investigation_21.py` `dca84cc0643c204b…`;
  - `paired_statistics.py` `7a5b79a8e5d8ba46…`.

  The committed code (`da3bddab`) has `e791516e2b621b1a…` and `68d4e70bccc66730…` for the two scripts; `paired_statistics.py` is unchanged. The D numbers are unchanged, because all 48 D runs have native peak counts, so the short-list rule never applies to them. The Part D output is kept as produced; it was not regenerated or edited.

### Part B (in progress)

- **Done:** chunks 1 and 2 (72139, 72190). In 72190, 6 CAC tasks failed on a race to create a shared output folder (a setup fault).
- **Stopped,** waiting for Zayd's OK on the fix; see the chat, 14:06.
- **15:35 (fix approved):** the submitter now checks that output folders exist, and all subfolders were created. My folder command also made 160 stray empty folders in `$HOME/msi`. Stopped before any submission; the cleanup needs Zayd's OK (chat 15:40).
- **15:38–20:33:** the cleanup was done, the 6 failed tasks were retried (72269), and chunks 72276, 72303 and 72440 ran with no failures. Released seeds 1–10 now exist for all 16 sections, and they were pulled at 20:33.
- **20:34: the summariser refused one run.** CAC 240TopL seed 7 returned 256 of 257 peaks. That is the released code's own cut-off: only 256 distinct m/z were ever selected. It is the only deviation in 160 runs. Stopped for a decision (chat 20:36).
- **20:39, decision (supervisor, option 1; Zayd's OK):** the run is kept, and the balanced 8 × 10 design stands.
  - **The rule:** a run may hold fewer peaks than `num_GT_peaks` only if that number equals its logged distinct-selection count. That count is recorded for all 140 tasks in `reproducibility/s3pl_investigation_21/provenance/selection_counts.tsv`. A count above native, or any other shortfall, is refused.
  - **Reported beside Parts A and B:** "1/160 released runs returned 256 of 257 peaks (released distinct-m/z cut-off; CAC 240TopL seed 7)".
  - **Disclosure:** Code saw this run's in-job mSCF1 (0.143) in its Slurm log on the cluster before any summary was computed. The rule was decided on validity: the released code keeps all of its distinct selections when there are fewer than the target. **The decision would be the same for any score value.**

### Part C (21 October; verified by the supervisor at 14:21)

Output: `code/msi/results/diagnostics/s3pl_seed_investigation_21/part_c/` (`runs.csv`, `sections.csv`, `summary.json`). Script: `code/msi/scripts/summarise_s3pl_investigation_21_c.py`. Runs: 72626 (19/19), plus the saved runs listed in the task manifest. The identity gate passed in 72625 on CPU, after 72595 failed on a test-code bug that Codex fixed in `178720e8`. Labels and numbers are in the summary above.

- **Note on the aggregation string:** `summary.json` records `nondeterminism_aggregation` as ">= 2 of 3 sections (Code's reading; Section 6.7 does not specify; per-section values reported)". The output is kept as generated. The dated clarification in protocol 18 Section 6.7, written on 21 October at 08:58 SAST before any Part C run, confirmed this reading (supervisor chat 20 October 21:11). The clarification also records that a repeat SD of 0 never counts toward nondeterminism and that an SD of 0 never makes a component dominant.

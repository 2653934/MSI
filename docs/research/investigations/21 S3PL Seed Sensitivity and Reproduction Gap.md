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

## Plan and costs

See the chat entry of 20 October (Code → Supervisor, Investigation 21 code facts and plan). Order: A, then D and B, then C. A uses saved data only. B, C and D each need Zayd's OK and the pre-submission checklist.

## Results

### Part A, preliminary (20 October; descriptive; saved runs only)

Output: `code/msi/results/diagnostics/s3pl_seed_investigation_21/part_a_preliminary/` (`runs.csv`, `sections.csv`, `jaccard_pairs.csv`, `variance.csv`, `summary.json`, `seed_scores_per_section.png`). Script: `code/msi/scripts/summarise_s3pl_seed_investigation_21.py --set preliminary`.

The two collections use different seed modes:
- GBM uses the controlled initialisation screen (init seeds 1–3, order seed 1).
- CAC uses released seeds 1–3.

The scores are S3PL's in-job mSCF1, recomputed unrounded. The primary decomposition will be the same analysis on released seeds 1–10 after Part B. Interpretation waits for the supervisor.

### Gate (GBM12_2 released seed-1 repeat)

Job 72135 failed before running S3PL: the `--wrap` shell has no `source`. Not retried; see protocol 18 Section 10.

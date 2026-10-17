# Spatial-msiPL Honours project — guidance for Claude Code

This is Zayd's Honours research repository: unsupervised peak learning for mass spectrometry imaging (MSI). Read this file at the start of every session. Read the linked documents before changing methods, results or claims.

## Where things live

- `code/msi/`: the executable workspace. It is mirrored to the cluster at `/home-mscluster/zsuliman/msi/` (`$HOME/msi` there).
  - `src/spatial_msipl/`: package code. Tests are in `src/spatial_msipl/tests/` (unittest).
  - `scripts/`: Python entry points.
  - `slurm_jobs/`: job and submit scripts.
  - `results/`: cluster-generated artifacts (JSON, CSV, NPZ, figures).
- `docs/research/`: the durable scientific record. Start with `README.md`, `01 Results Record.md`, and `18 Fair Scoring and Simple Baselines Protocol.md` (the current protocol).
- `docs/meetings/`: supervisor reviews (`supervisor_review_2026-10-09*.md`) and the progress checklist.
- `report/draft/`: the LaTeX report being rebuilt. `report/final/` stays empty until the final audit.
- Raw data and checkpoints exist only on the cluster: `/datasets/zsuliman/msi_data/` and `/datasets/zsuliman/msi_checkpoints/`.

## Current work (state at 18:30 SAST, 16 October 2026: final round A–G complete and read; RCC is GO, its specification is in protocol 18 Section 6.1, and the RCC code is written and tested locally; nothing RCC submitted; experiments end Tuesday 20 October)

Protocol 18 (v3.2) is the governing document. Section 6 holds the gate (d) specification, Section 6.1 the final-round and RCC specifications, Section 7.1 the rule gaps, and Section 10 the full execution log. The Notion task is "22. Fair-scoring gate".

### Wording rule for every predeclared verdict (supervisor 16 Oct 17:36)
No rule has a "worse" category and none is added. Report the rule result exactly as labelled, then the numbers beside it: "does not meet the 'helps' rule (labelled mixed); below real 3×3 in 6/8 GBM sections, mean −0.035 at bin level and −0.034 under P1." Where "equivalent" hides a one-sided P1 pattern, add it ("equivalent; P1 −0.018, 1/8 positive"). For IG vs posterior use the Section 7.1 wording.

### Gates (a)/(b), fair scoring: complete
- Decision tables: bin level 66097 (`bin_level_only/summary_66097/`), approved partitions 66238 (`with_approved_partitions/summary_66238/`).
- IG is below posterior-|PCC| in all 32 section-arms at bin level (GBM −0.225/−0.233; CAC −0.078/−0.047); under P1 one exception (CAC uniform_mean 280TopL). Neither predeclared verdict applies (Section 7.1).
- IG vs legacy: positive 8/8 in every arm at bin level and in the collapse diagnostic; budget-stability clause not assessable, so 2 of 3 clauses met.
- **Do not change the report headline or research questions yet** (supervisor). Provisional framing: on GBM, label-free GMM + correlation ranking approaches the oracle; on CAC it is only comparable to mean intensity and Moran's I; IG underperforms the correlation ranking in both.

### Gate (d), attribution-pixel count: CLOSED. Production n=12 stands in both arms (chat 2026-10-10 09:45).

### Earlier 15 October results (confirmed)
- **BIC 68496:** K = 6 (largest candidate) in all four section-arms. Wording: "BIC does not support the production K; it selects the largest candidate (K = 6), with no minimum within the predeclared range; descriptive only. The production K equals the number of annotated classes, so the segmentation is label-free in training and ranking but class-informed in its component count." Never write "six clusters".
- **S3PL CAC seed 2 (68500/68501):** two-seed rule supported (8/8 in both seeds, +0.413 / +0.438), always with the harder-target and sample-order caveats.
- **B and C1:** `runtime_all_sections.csv` and `training_curves_*` in `current_evidence/` (S3PL `train_history` is last-batch MSE).

### Final round A–G: complete and confirmed (supervisor 16 Oct 17:36; protocol 18 Section 10, 16 October)
Decision table: `results/diagnostics/fair_scoring_baselines/extra_arms/decisions_20261016_local/decisions.json`. Values: mean IG mSCF1 difference at K_bin, positive sections /8, bin / P1.
- **A, attention vs uniform_mean:** equivalent on GBM (+0.011, 6/8 / +0.010, 6/8) and CAC (−0.006, 4/8 / −0.005, 2/8). A(b) reproduction passed 16/16.
- **G1 vs attention:** GBM "mixed; below standard attention in 7/8 sections, mean −0.039 / −0.040"; CAC equivalent. G1 vs G2 equivalent on both. G3: +0.021 (160TopL), −0.011 (GBM22_2), rule not met.
- **G mechanism:** "Centre masking did not make attention selective: median normalised entropy 0.998–0.999, against 0.98–0.999 without masking. On GBM, masked attention scored below standard attention."
- **E:** p7 and p9 GBM "mixed", below 3×3 (−0.035, 2/8 at both scales; confirmation-only about −0.03); CAC equivalent (CAC p7: "equivalent; P1 −0.018, 1/8 positive"). p5 descriptive: GBM −0.018, CAC −0.006.
- **IG vs own posterior-|PCC|:** 0/8 positive in all 14 extra collection-arms (GBM −0.22 to −0.29, CAC −0.05 to −0.08).
- **C2 (descriptive):** S3PL quality falls with longer training (CAC 0.591 → 0.336, GBM 0.316 → 0.212 from epoch 10 to 100); epoch 10 best in 15/16 (exception GBM108_positive). Report S3PL at 10 epochs as the comparison and the 100-epoch curve as sensitivity; the 10-epoch protocol is effectively an early-stopping choice with no label-free signal to pick it. Never per-section best.
- **C3:** not run (accepted by the supervisor 15 Oct 19:37).

### RCC (item D → RCC run): GO; specification approved with conditions (supervisor 16 Oct 17:36)
- **Feasibility 68805: GO** (`results/validation/rcc_feasibility/go_no_go.json`). 8 runs (MH0204_33, UH0505_12, UH0710_33, UH9610_15, UH9812_03, UH9905_18, UH9911_05, UH9912_01), 972–3,564 px, 10,200 bins (m/z 150–1000), all audit `valid`. Labels cancer 0, normal 1, unannotated 2. HDF5s at `/datasets/zsuliman/msi_data/rcc_cardinal/RCC_<run>.h5`.
- **NA caveat on every RCC number** (supervisor 16 Oct 18:34): "unannotated class, 45–78% of pixels; the dataset's own Cardinal workflow treats these pixels as background (`rcc_nobg`), but this was not independently verified". **Limitation beside the RCC results:** "per the dataset documentation, UH0505_12 and UH9905_18 contain heterogeneous tumour with large normal-looking areas" (descriptive; no exclusion). The sensitivity table caption says the oracle, ceilings and P1 groups follow the cancer/normal subset (confirmed). A GMM component under 44 px means "not done", with no fallback; an arm with fewer than 8 runs gets "incomplete; no verdict" plus per-run values with n. A future STALE (exit 3) on GBM/CAC is expected (the evaluator hashes changed at `d35d063`), not a fault.
- **Approved specification (written into protocol 18 Section 6.1, item D step 2):** `central_only` and `uniform_mean`, 100 epochs, seed 1, all 8 runs as confirmation; GMM K = 3 (class-informed, disclosed); **K_bin = released S3PL target `num_GT_peaks` from `baselines/s3pl/data_configs.py` (≈ our |R@0.5|; the paper uses PCC 0.5 for RCC; spec correction, supervisor 16 Oct 19:47; `released_target_budget.json`, matched evaluation in `peak_evaluation_released_target/`). The first |R@0.4| budget (`reference_budget.json`, pilot `peak_evaluation/`) is a superseded record only**; unchanged fair-scoring evaluator with all baselines and the oracle; primary test posterior-|PCC| vs IG under Section 7 per arm. Secondary, descriptive: "sensitivity, cancer/normal classes only" via an **opt-in class-subset parameter, default path bit-identical with a test proving it**, same rankings and same K_bin. P1 only if the structural audit's S1 passes on RCC, else bin level only; no P3. Legacy msiPL not run ("legacy msiPL not run on RCC (requires count tuning)"). Confirm the run-to-patient mapping before scoring; group runs that share a patient. Out of scope: attention, larger windows, masking, S3PL.
- **Patients:** 8 runs = 8 subjects (CardinalWorkflows vignette: "each matched pair of tissues belonging to the same subject are on the same slide (i.e., the same run)"); `RCC_PATIENT` in `summarise_rcc_fair_scoring.py`. The vignette calls the NA-removed object `rcc_nobg`; this is documentary only, and the NA caveat stands.
- **Code (uncommitted, tested locally):** opt-in `--no-legacy`/`--reference-budget`/`--class-subset` in `evaluate_fair_scoring_baselines.py`; `--no-legacy` in `evaluate_spatial_msipl_attributed_peaks.py`; `compute_reference_budget.py`; `summarise_rcc_fair_scoring.py`; `slurm_jobs/rcc_sections.sh`, `run_rcc_preparation.sh` (CPU: budget + partition audit), `run_rcc_campaign.sh` (GPU: train, IG, matched eval; 0–7 central_only, 8–15 uniform_mean), `run_rcc_fair_scoring.sh p1|bin-only` (CPU: primary + cancer/normal sensitivity), `submit_rcc.sh prep|pilot|rest|fair`. Tests: `test_rcc_pipeline.py` (10; bit-identity against the frozen pre-change copies in `tests/fixtures/pre_rcc/`). The evaluator code hashes change, so rerunning a saved GBM/CAC result now reports STALE by design.
- **Order:** spec ✓ → code and tests ✓ (commit `d35d063`, 13 files matched on the cluster) → show Zayd the diff ✓ → Zayd commits and syncs, `sha256sum` check → cluster test job (`run_fair_scoring_tests.sh`, `test_rcc_pipeline` must run, not skip) → `submit_rcc.sh prep` → read the RCC partition audits, reviewer writes `peak_partition_audit_rcc/partition_approval.json` (P1 only, only if S1 passes in 8/8) → `pilot` (tasks 2,3,10,11) → `rest` → `fair p1|bin-only` → `summarise_rcc_fair_scoring.py` locally after the sync (primary and `--sensitivity`). If not done by Tuesday 20 October, report RCC as incomplete; don't extend.

- **Overnight 16–17 Oct (state at 23:55 SAST; details in the supervisor chat 22:07–23:53 and protocol 18 Section 10):** RCC campaign done.
  - `central_only` 8/8: rule fall-through, IG below posterior in 0/8 (−0.156). `uniform_mean` 7/8: incomplete, no verdict; UH0505_12 IG `needs_more_ig_steps`.
  - Decision tables are in `fair_scoring_baselines/rcc*/decisions_20261016_local/`.
  - S3PL CAC seeds 2/3 and S3PL-RCC (0.441/0.427/0.406 vs 0.470) done; legacy msiPL RCC 7/8 (0.160 vs 0.159); RCC BIC K = 6 everywhere; ion export done.
  - **17 Oct morning (chat 07:03–07:39):** legacy UH0505_12 retry 69625 done (0.139 vs 0.14; count not reached); legacy RCC 8/8, mean 0.157. RCC verdict now bin level only, P1 = budget sensitivity (protocol 18 Section 6.1 amendment); tables in `decisions_20261017_local/` (the 16 Oct ones superseded; verdicts unchanged). `summarise_s3pl_seed_runs.py` fails closed on provenance (numbers unchanged).
  - **Test S (protocol 18 Section 6.2, predeclared 08:04; results due Mon 19 Oct 08:00 SAST):** Cardinal check posted 08:14 (σ matches; Cardinal's per-pixel adaptive scale used instead of the median λ). Code and 25 tests written, uncommitted for Codex (chat 08:28). After Codex commits: upload, cluster test job, checklist, `SBATCH_PARTITION=bigbatch bash slurm_jobs/submit_spatial_segmentation_s.sh` (24 CPU tasks), pull, `summarise_spatial_segmentation_s.py`, results entry.
  - **Open:** the supervisor's ruling on CAC P1 being singleton groups (08:14 point 3).

### Next
Times: the cluster logs in UTC; Zayd is on SAST (UTC+2). Quote both. **Take dates from the local clock:** in Git Bash use `TZ=SAST-2 date` (Git Bash ignores `TZ=Africa/Johannesburg` and prints UTC), or PowerShell `Get-Date`.
1. Finish the RCC order above; each `sbatch` with Zayd's OK and the job IDs posted to the chat. `batch` has been down since 13 October; CPU jobs go to `bigbatch` with Zayd's OK (`SBATCH_PARTITION=bigbatch`).
2. Still in force: no new claims in `report/draft/` or `planning/claim_map.md` until Hairong has responded (meeting Monday 19 October). Slurm email is not used; track jobs with `sacct`.
3. The cluster-access details are in `docs/operations/cluster_sync.md`. Claude does not inspect the keys.

## Scientific rules

- Predeclared rules and thresholds are fixed before results are seen. Never tune a rule, partition, budget, seed or threshold after looking at outcomes. Propose a change as a new, separately labelled analysis.
- Never overwrite or silently reuse results. The scripts refuse stale outputs (exit code 3); move them aside instead of forcing.
- Every number in the report must map to a saved artifact. Report effect sizes and per-section results.
- GBM has 8 sections from 4 patients, so never treat sections as independent patients.
- Development sections (GBM108_positive, GBM22_2, 160TopL, 40TopL) are not confirmation evidence.
- Use spatial-agreement language, not biological-identity claims. Name the measured resource behind every efficiency claim.
- The legacy msiPL list is not K_peak-matched. Peak-level IG-vs-legacy is a collapse diagnostic only.

## Cluster rules

- **No scientific computation on the login node.** File checks and `sbatch` only. HDF5 reading, model loading and scoring happen inside Slurm jobs.
- **Partitions:** CPU jobs use `--partition=batch` with small memory requests (the fair-scoring tasks peak below 1 GB). `bigbatch` is reserved for long training or demonstrated high memory. **If `batch` is down,** CPU jobs may go to `bigbatch` only with Zayd's OK. Set the partition at submit time (`--partition=bigbatch` or `SBATCH_PARTITION=bigbatch`), don't edit the script, and log the move in protocol 18 Section 10. This happened on 15 October: `batch` has been down since 13 October 07:05 UTC.
- **Python:** use `$HOME/miniconda3/envs/s3pl_env/bin/python` (Python 3.11.5, NumPy 2.4.6, sklearn 1.9.0) and set the thread environment variables.
- **Pre-submission checklist for any new training job (added 16 Oct after the RCC streaming-loader error).** Every new or edited job script that calls `train_spatial_msipl_production.py` must pass `--cache-spectra`. The streaming default stays only for reproducing the frozen pre-October baselines; streaming once made GBM runs 11 h instead of about 23 min. A unit test (`test_training_jobs_use_cached_loader`) enforces this. Before the first `sbatch` of any campaign, also check and state in the chat: (1) the loader; (2) the expected time per run vs `--time`, from a comparable earlier run; (3) the partition and GPU quarantine; (4) where outputs go, and that they don't overwrite earlier results. The supervisor checks the same four items when approving a spec.
- **GPU jobs** (for example Integrated Gradients) must do the real CUDA warm-up and exclude the nodes listed in `code/msi/slurm_jobs/gpu_cuda_quarantine.txt`. Record new node failures in `code/msi/cluster_node_issues.txt`.
- **Arrays:** use one array task per section. Make concurrency a submit-time option, and use `sbatch --parsable` to print the real job ID.
- **Sync:** follow `docs/operations/cluster_sync.md`. Run rsync from `code/msi`, preview with `-n`, and never use `--delete`.
- **Who does what on the cluster:**
  - **Claude may run rsync itself (Zayd's permission, 16 October 2026), under these rules only:**
    - Use only the commands in `docs/operations/cluster_sync.md`, run from `code/msi`.
    - Always run the identical command with `-n` first, check the file list, then run it for real.
    - Never use `--delete`. Never touch `/datasets` (raw data or checkpoints).
    - **Upload (local → cluster):** only from a clean, committed HEAD. `git status` must show no uncommitted code. Afterwards, run the `sha256sum` check of the changed files against HEAD. Never upload uncommitted code.
    - **Download (cluster → local):** only into `code/msi/results/` and `code/msi/reproducibility/`, and only for jobs that have finished. Slurm logs under `logs/` stay on the cluster. Hand-written files under `results/` are excluded from the pull (list in `cluster_sync.md`); if a preview would change any committed local file, stop and ask.
      - Before pulling, the working tree must have no uncommitted edits under `results/`; the pull overwrites them (see the 15 October note below).
      - After pulling, check `git status`/`git diff`. Then re-run `build_current_evidence_tables.py` if results changed.
    - **Log every sync** in protocol 18 Section 10: time (SAST), direction, paths and file count.
    - If anything looks wrong (an unexpected file list in `-n`, files outside the allowed folders, local edits being overwritten), stop and tell Zayd instead of syncing.
  - Commits stay with Zayd/Codex.
  - **Overnight queue and temporary commit permission** (Zayd, 2026-10-16 22:07 SAST; valid until **Saturday 17 October 12:00 SAST**). The work list, priorities, specs and gates are in the supervisor chat entry "2026-10-16 22:07 … Overnight queue". Within that list only:
    - **You may commit locally** (never push, never amend or rewrite earlier commits). Only when: every relevant test passes, including bit-identity of any shared default path; the change matches the chat spec; and you post a diff summary (files, test counts, commit hash) to the chat before uploading. One commit per item, message prefixed `[overnight]`. Zayd/Codex review all `[overnight]` commits in the morning.
    - You may submit, sync and continue along the list under the same rules and stop conditions as the RCC standing approval below. The RCC campaign always has priority for GPU slots. Stay within 6 running jobs.
    - Anything not on the list, any change to an existing scientific default, or any failed gate: stop, post in the chat and do not commit.
  - **Standing approval for the RCC campaign** (Zayd, 2026-10-16 18:56 SAST; valid until the end of Tuesday 20 October). You may submit, sync and continue **without asking Zayd at each step**, but only along the predeclared sequence in protocol 18 Section 6.1 (RCC) and the supervisor chat:
    1. cluster test job;
    2. `submit_rcc.sh prep`;
    3. P1 decision;
    4. pilot (UH9610_15 and UH0710_33, both arms);
    5. the remaining runs;
    6. fair scoring;
    7. summary.
    - **Gates you must check yourself:** the test job passes with `test_rcc_pipeline` run, not skipped. The pilot completes with valid IG and evaluation before the rest is submitted.
    - **P1 decision is mechanical:** write `peak_partition_audit_rcc/partition_approval.json` approving P1 only if S1 passes, citing the S1 rule; otherwise score bin-only. No other criterion. P3 never.
    - **Allowed without asking:** retrying only the failed indices after a CUDA warm-up or node failure (quarantine the node first, as before), and the syncs under the rsync rules above.
    - **Stop and notify Zayd (push notification if Remote Control is on), and post to the supervisor chat, if:**
      - any code or specification change is needed;
      - a failure is anything other than a node or CUDA failure;
      - the same index fails twice;
      - a result file is missing or invalid;
      - a reproduction check fails;
      - something is outside the plan.

      Never improvise a fix while running unattended.
    - Log every submission, sync and decision in protocol 18 Section 10, and post a short INFO entry to the supervisor chat at each stage. Commits stay with Zayd/Codex; the RCC code must be committed before the first upload.
  - Claude may poll `squeue`/`sacct`, read **short** logs on the cluster (unit-test logs, Slurm `.out`/`.err`), and run file checks such as `sha256sum`.
  - Scientific results (`summary.json`, decision tables, CSVs) are read **only from local files, after the download sync**. They are never read on the cluster.
  - Every `sbatch` and every cluster file move needs Zayd's explicit OK.
  - Before submitting, check that the cluster copies of changed files match the local commit (compare `sha256sum`).
- **SSH from this machine:** use WSL, which has the passwordless key: `wsl.exe -e ssh -o BatchMode=yes zsuliman@146.141.21.100 '...'`. Git Bash has no key and no rsync. For multi-line remote commands, pipe a heredoc to `ssh ... bash -s`. The login node sometimes drops connections; before retrying a submit, check `sacct` to see whether the job was already created.
- **The artifact pull overwrites locally edited files under `results/`.** On 15 October it replaced the edited `results/publication/current_evidence/README.md` with the older cluster copy. After every pull, check `git status`/`git diff` for local `results/` edits and restore them (commit them first so `git checkout` can recover them). Re-run `build_current_evidence_tables.py` after a pull.
- **Concurrent array tasks** can race when creating a shared parent folder (66114: `mkdir: Already exists`). Create shared output folders before submitting.
- **Timing:** read the authoritative timing with `sacct -j <id> --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode`.

## Supervisor and the supervisor chat

A separate Claude session (Cowork) acts as Zayd's **research supervisor**. It reviews the plans, code, results and wording. You communicate with it through **`docs/supervision/supervisor_chat.md`**, which is tracked in git. Read that file's "How this works" section, then follow it.

- **At the start of every session,** read the latest entries. Act on any `OPEN` item addressed to Code.
- **Post an entry (Code → Supervisor) when:**
  - a run, gate or evaluation finishes;
  - a predeclared rule or plan can't be followed as written;
  - a result could change the thesis framing;
  - you need approval, a decision or clarification.
- **After posting a request, stop that line of work** and tell Zayd: "Posted to supervisor chat: <topic>." Supervisor notes may also arrive pasted into this chat. Treat those the same way: follow them, answer yes or no point by point, and stop where they say to stop.
- **The supervisor's approval does not replace Zayd's OK.** Every `sbatch`, cluster file move and commit still needs Zayd's explicit OK.
- **Decisions belong in protocol 18 (Sections 6 and 10) or the research docs, not only in the chat.**

## Working style

- Zayd makes git commits himself. Do not commit or push unless asked.
- Line endings: `.gitattributes` forces LF for `*.py` and `*.sh`. Check with `git ls-files --eol`; `grep -c $'\r'` is unreliable in Git Bash.
- Leave the unrelated modified files alone (line-ending changes in older scripts and runtime CSVs).
- Run the relevant unittest modules before proposing a cluster run. Locally, h5py may be missing, so the pipeline tests may need the cluster test job (`slurm_jobs/run_fair_scoring_tests.sh`).
- Explain plainly; Zayd is an Honours student. When a result changes the thesis, say so directly and propose the honest framing.

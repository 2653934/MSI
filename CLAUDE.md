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

## Current work (state at 16:00 SAST, 15 October 2026: final experiment round coded and tested locally, nothing submitted yet; experiments end Tuesday 20 October)

Protocol 18 (v3.2) is the governing document. Its Section 6 holds the gate (d) run specification and its amendments, Section 7.1 the rule gaps, and Section 10 the full execution log. The Notion task is "22. Fair-scoring gate".

### Gates (a)/(b), fair scoring: complete
- **Runs:** bin level was array 66053 (pilot 66045), with decision table 66097 in `fair_scoring_baselines/bin_level_only/summary_66097/`. Approved partitions were array 66114 plus 66179 (a GBM108_negative rerun after a folder race), with decision table 66238 in `with_approved_partitions/summary_66238/`.
- **Result:** IG is below posterior-|PCC| in **all 32 section-arms** at bin level (GBM −0.225/−0.233; CAC −0.078/−0.047). Under P1 there is one exception: CAC uniform_mean 280TopL. **Neither predeclared verdict applies** (Section 7.1): the rules have no "IG worse" category, so `decisions.json` prints "mixed / not resolved", which is a fall-through, not a mixed result. Use the wording in Section 7.1, and do not add a verdict category after the fact.
- **IG vs legacy:** positive in 8/8 sections in every arm at bin level and in the collapse diagnostic. The budget-stability clause cannot be assessed, so report it as 2 of 3 clauses met.
- **Do not change the report headline or research questions yet** (supervisor). The provisional framing: on GBM, the label-free GMM segmentation plus a correlation ranking approaches the oracle; on CAC it is only comparable to mean intensity and Moran's I; IG underperforms the correlation ranking in both. Spatial context was not tested by this gate.

### Gate (d), attribution-pixel count (12/48/192): CLOSED. Production n=12 stands in both arms; no 16-section rerun (supervisor confirmed, chat entry 2026-10-10 09:45)
- **Specification:** protocol 18 Section 6, decided before any gate (d) output.
  - Sections: GBM108_positive and 40TopL. Both arms (central_only, uniform_mean), with the rule applied per arm.
  - Reproduction gate: an identical K_bin bin set plus the saved mSCF1 to 1e-12; order is recorded but not gating.
  - Run-validity checks: IG status `valid`; run signature equal to n=12; GMM labels aligned to production with a matching reference SHA-256.
  - Trigger: change ≥ +0.02 on **both** sections for that arm. Resources: `batch` with `--exclusive`, 8G for CAC, 24G for GBM.
- **Code:** `slurm_jobs/run_gate_d_pixel_count_ig.sh`, `submit_gate_d_pixel_counts.sh pilot|gbm [--counts LIST] [--arms LIST]`, `run_gate_d_evaluation.sh SECTION ARM [n12-only]` (n12-only runs `scripts/check_gate_d_n12_reproduction.py`), `run_gate_d_summary.sh`, `scripts/evaluate_gate_d_pixel_counts.py`, `scripts/summarise_gate_d_pixel_counts.py` and `scripts/check_gate_d_uniform_consistency.py`. The IG script has the opt-in flags `--attribution-total` and `--align-gmm-labels-to-production`; alignment failure exits with code 5.
- **History:**
  - Attempt 1 (66286–66291) failed at the unit-test step because `scripts/` was missing from `PYTHONPATH`; this was fixed.
  - Attempt 2 (66293–66298): the central_only GMM components came out renumbered by the GPU refit, so different attribution pixels were sampled. That led to the label-alignment amendment. The outputs were moved, not deleted, to `gate_d_pixel_counts/superseded_label_order/40TopL_seed1/`.
  - Attempt 3, aligned (commit `3a9599d`): tests 66324 passed 83/83; IG 66325–66330; evaluations 66331/66332. All passed.
  - GBM108_positive, staged (commits `6ee2b1e`, `945836a`; 59 cluster files matched `HEAD` by sha256sum). Tests 66389 passed 86/86 with none skipped.
    - Stage 1: IG n=12 66390/66391 valid, identity alignment, about 7 min each; checks 66392/66393 **passed in both arms** (uniform_mean's version-1 risk did not occur). No scores were read.
    - Stage 2: IG 66399 (central_only n=48), 66400 (central_only n=192), 66401 (uniform_mean n=48), 66402 (uniform_mean n=192), all started 21:10 UTC (23:10 SAST).
  - `sacct` MaxRSS is blank for gate (d) jobs and `seff` is not installed, so peak memory is not available.
- **40TopL results** (in `gate_d_pixel_counts/40TopL_seed1/<arm>/evaluation/summary.json`):
  - The uniform_mean consistency check **passed** (identity mapping, max difference 0.0). The central_only permutation was {0→0, 1→2, 2→1}.
  - Change at K_bin: central_only n=48 −0.001, **n=192 +0.024**; uniform_mean n=48 −0.008 (value −0.0085), n=192 +0.003.
  - IG − posterior-|PCC| stays negative at every n (−0.02 to −0.07).
  - **So uniform_mean cannot trigger. central_only n=192 depends on GBM108_positive central_only n=192.** That is a single section, single seed, just over the threshold, with bin-set Jaccard about 0.8 between counts.

### Final experiment round (supervisor chat 15 Oct 13:00, 13:30, 15:35, 15:51; experiments end Tuesday 20 October)
Specifications are in protocol 18 Section 6.1, and the log is in Section 10 ("Final experiment round").
- **State at 16:00 SAST, 15 October:** nothing has been submitted yet; the 15:51 review fixes (dates, this section, memory requests) are made. Everything below is coded and tested locally and waits for Zayd's commit, sync and per-`sbatch` OK. `batch` is down, so `bigbatch` is approved (CPU jobs via `SBATCH_PARTITION=bigbatch`).
- **B and C1 are done:** `scripts/build_runtime_and_training_curves.py` produces `runtime_all_sections.csv` and `training_curves_*` in `current_evidence/`. Note that the S3PL `train_history` is the last-batch MSE, not an epoch mean.
- **A:** the GBM attention evaluations used the old counts. The approved fix is `check_saved_list_reproduction.py`, then re-evaluation at K_bin into `peak_evaluation_tuned_count/`, then the unchanged evaluator. Run with `submit_fair_scoring_extra_arm.sh attention pilot|all`; the summariser is `summarise_fair_scoring_arms.py`.
- **G:** centre masking with p = 0.5 (`train_vae(centre_mask_probability)`). The zeroed centre also serves as the attention query, which the supervisor confirmed. Run with `submit_centremask_campaign.sh` (34 tasks), then fair scoring with `submit_fair_scoring_extra_arm.sh <G arm>`.
- **C2:** S3PL 100 epochs, with logging-only `--checkpoint_epochs` in `baselines/s3pl/train.py`. Run with `submit_s3pl_e100.sh`; evaluate with `evaluate_s3pl_epoch_checkpoints.py`.
- **E:** first the audit with `--windows 3 5 7 9` (`AUDIT_WINDOWS`/`AUDIT_OUTPUT_ROOT` on `audit_spatial_msipl_data_contract.sh`). The E training spec is written only after the audit passes.
- **D:** `rcc_env` exists (Cardinal 3.12.1). Run `run_rcc_feasibility.sh`; the go/no-go goes in `results/validation/rcc_feasibility/go_no_go.json`, due by the end of Friday 16 October.
- **C3:** only if GPU time remains.

### Next
Times: the cluster logs in UTC; Zayd is on SAST (UTC+2). Quote both. **Take dates from the local clock:** in Git Bash use `TZ=SAST-2 date` (Git Bash ignores `TZ=Africa/Johannesburg` and prints UTC), or PowerShell `Get-Date`.

Governing entries: supervisor chat of 15 October 13:00 (round A–F), 13:30 (item G), 15:35 (answers) and 15:51 (code review). Specifications are in protocol 18 Section 6.1.
1. Zayd commits and syncs. Then check `sha256sum` against `HEAD` on the cluster.
2. Run the cluster test job `run_fair_scoring_tests.sh` on `bigbatch`. `test_fair_scoring_arms`, `test_centre_masking` and `test_neighbourhood` must show as run and passed, not skipped.
3. Submit in order, each with Zayd's OK, posting the job IDs to the chat: A pilot → A all → G pilot (160TopL G1) → G rest → C2 → E audit → E → C3 if time allows. D runs in parallel; its go/no-go is due by the end of Friday 16 October.
4. Still in force: no new claims in `report/draft/` or `planning/claim_map.md` until Hairong has responded (meeting Monday 19 October). Slurm email is not used; track jobs with `sacct`.

**Completed earlier (15 October; synced, logged and confirmed by the supervisor):**
- **BIC 68496:** K = 6 (the largest candidate) in all four section-arms. Wording: "BIC does not support the production K; it selects the largest candidate (K = 6), with no minimum within the predeclared range; descriptive only. The production K equals the number of annotated classes, so the segmentation is label-free in training and ranking but class-informed in its component count." Never write "six clusters".
- **S3PL CAC seed 2 (68500/68501):** the two-seed rule is supported (8/8 sections in both seeds, +0.413 / +0.438). Always give the harder-target and sample-order caveats with it.
- The cluster-access details in `docs/operations/cluster_sync.md` are filled in. Claude still does not inspect the keys.

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
- **GPU jobs** (for example Integrated Gradients) must do the real CUDA warm-up and exclude the nodes listed in `code/msi/slurm_jobs/gpu_cuda_quarantine.txt`. Record new node failures in `code/msi/cluster_node_issues.txt`.
- **Arrays:** use one array task per section. Make concurrency a submit-time option, and use `sbatch --parsable` to print the real job ID.
- **Sync:** follow `docs/operations/cluster_sync.md`. Run rsync from `code/msi`, preview with `-n`, and never use `--delete`.
- **Who does what on the cluster:**
  - **Zayd does all rsync himself, in both directions.** Tell him exactly what to sync and give the real command, not only the `-n` preview.
  - Claude may poll `squeue`/`sacct`, read **short** logs on the cluster (unit-test logs, Slurm `.out`/`.err`), and run file checks such as `sha256sum`.
  - Scientific results (`summary.json`, decision tables, CSVs) are read **only after Zayd syncs them**, from local files.
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

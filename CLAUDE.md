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

## Current work (state at end of 9 October 2026, after the supervisor report was drafted)

Protocol 18 (v3.2) is the governing document. Its Section 6 holds the gate (d) run specification and its amendments, Section 7.1 the rule gaps, and Section 10 the full execution log. The Notion task is "22. Fair-scoring gate".

### Gates (a)/(b), fair scoring: complete
- **Runs:** bin level was array 66053 (pilot 66045), with decision table 66097 in `fair_scoring_baselines/bin_level_only/summary_66097/`. Approved partitions were array 66114 plus 66179 (a GBM108_negative rerun after a folder race), with decision table 66238 in `with_approved_partitions/summary_66238/`.
- **Result:** IG is below posterior-|PCC| in **all 32 section-arms** at bin level (GBM −0.225/−0.233; CAC −0.078/−0.047). Under P1 there is one exception: CAC uniform_mean 280TopL. **Neither predeclared verdict applies** (Section 7.1): the rules have no "IG worse" category, so `decisions.json` prints "mixed / not resolved", which is a fall-through, not a mixed result. Use the wording in Section 7.1, and do not add a verdict category after the fact.
- **IG vs legacy:** positive in 8/8 sections in every arm at bin level and in the collapse diagnostic. The budget-stability clause cannot be assessed, so report it as 2 of 3 clauses met.
- **Do not change the report headline or research questions yet** (supervisor). The provisional framing: on GBM, the label-free GMM segmentation plus a correlation ranking approaches the oracle; on CAC it is only comparable to mean intensity and Moran's I; IG underperforms the correlation ranking in both. Spatial context was not tested by this gate.

### Gate (d), attribution-pixel count (12/48/192): 40TopL done and logged; GBM108_positive approved in stages (supervisor, 9 October), not yet run
- **Specification:** protocol 18 Section 6, decided before any gate (d) output.
  - Sections: GBM108_positive and 40TopL. Both arms (central_only, uniform_mean), with the rule applied per arm.
  - Reproduction gate: an identical K_bin bin set plus the saved mSCF1 to 1e-12; order is recorded but not gating.
  - Run-validity checks: IG status `valid`; run signature equal to n=12; GMM labels aligned to production with a matching reference SHA-256.
  - Trigger: change ≥ +0.02 on **both** sections for that arm. Resources: `batch` with `--exclusive`, 8G for CAC, 24G for GBM.
- **Code:** `slurm_jobs/run_gate_d_pixel_count_ig.sh`, `submit_gate_d_pixel_counts.sh pilot|gbm`, `run_gate_d_evaluation.sh SECTION ARM`, `run_gate_d_summary.sh`, `scripts/evaluate_gate_d_pixel_counts.py`, `scripts/summarise_gate_d_pixel_counts.py` and `scripts/check_gate_d_uniform_consistency.py`. The IG script has the opt-in flags `--attribution-total` and `--align-gmm-labels-to-production`; alignment failure exits with code 5.
- **History:**
  - Attempt 1 (66286–66291) failed at the unit-test step because `scripts/` was missing from `PYTHONPATH`; this was fixed.
  - Attempt 2 (66293–66298): the central_only GMM components came out renumbered by the GPU refit, so different attribution pixels were sampled. That led to the label-alignment amendment. The outputs were moved, not deleted, to `gate_d_pixel_counts/superseded_label_order/40TopL_seed1/`.
  - Attempt 3, aligned (commit `3a9599d`): tests 66324 passed 83/83; IG 66325–66330; evaluations 66331/66332. All passed.
- **40TopL results** (in `gate_d_pixel_counts/40TopL_seed1/<arm>/evaluation/summary.json`):
  - The uniform_mean consistency check **passed** (identity mapping, max difference 0.0). The central_only permutation was {0→0, 1→2, 2→1}.
  - Change at K_bin: central_only n=48 −0.001, **n=192 +0.024**; uniform_mean n=48 −0.008 (value −0.0085), n=192 +0.003.
  - IG − posterior-|PCC| stays negative at every n (−0.02 to −0.07).
  - **So uniform_mean cannot trigger. central_only n=192 depends on GBM108_positive central_only n=192.** That is a single section, single seed, just over the threshold, with bin-set Jaccard about 0.8 between counts.

### Next
1. Done 9 October: the 40TopL outcomes, the consistency PASS, the supervisor's descriptive additions (budget consistency of the central_only n=192 gain, the IG − posterior-|PCC| gap by budget, 25–36 of 315 bins changing) and the supervisor's decisions are logged in protocol 18 Section 10. `docs/meetings/` is gitignored, so Section 10 is the record.
2. Done 9 October: the supervisor report `docs/meetings/supervisor_report_2026-10-09_gate_d_40TopL.md` was sent and approved. Answers: (1) GBM108_positive approved **in stages**; (2) not stopping; (3) BIC kept, after the pixel-count result, with a plan drafted first.
3. **Staging change: approved by the supervisor (chat entry 22:55, 9 October) as drafted. Uncommitted, not synced, nothing submitted.** The submitter could not stage by n, so the smallest change was made:
   - `submit_gate_d_pixel_counts.sh`: `--counts` and `--arms` options; a count above 12 is refused unless `<arm>/n12_reproduction/summary.json` has status `passed` (a grep on the `atomic_write_json` format; switch to `json.load` if that format changes).
   - `run_gate_d_evaluation.sh SECTION ARM n12-only` runs the new `scripts/check_gate_d_n12_reproduction.py` (n=12 validity checks plus the reproduction gate only). It imports the evaluator and does **not** modify it, so the evaluator code hash, which the summariser compares across sections, stays identical to 40TopL's.
   - Three new tests in `test_fair_scoring_pipeline.py`. Not yet run: they need h5py, so they need the cluster test job, where they must show as run and passed.
   - A validity failure (ValueError before scoring) writes no `n12_reproduction/summary.json`. Post its error text to the supervisor chat.
4. Stages, after Zayd's commit and sync, a `sha256sum` match, and the cluster test job passing, with Zayd's OK for each `sbatch`:
   - **Stage 1:** `bash slurm_jobs/submit_gate_d_pixel_counts.sh gbm --counts 12`, then `sbatch slurm_jobs/run_gate_d_evaluation.sh GBM108_positive <arm> n12-only` for each arm. Post yes/no per arm (from the exit code and status only, plus `sacct` Elapsed and MaxRSS) to `docs/supervision/supervisor_chat.md`. **Do not read scores.**
   - **Stage 2:** `--counts 48,192 --arms central_only` if central_only reproduced; add uniform_mean only if it reproduced. Otherwise uniform_mean gets no verdict (no fallback; the decision table will show it as "missing").
   - **Then:** both full evaluations (`run_gate_d_evaluation.sh GBM108_positive <arm>`), `run_gate_d_summary.sh`, and the decision table exactly as the rule gives it, posted to the supervisor chat. Report back before anything else.
   - A timeout is a failed run: report it, do not silently resubmit. GBM IG time at n=192 is untested (limits 4h/4h/8h).
5. BIC: the specification was approved with changes and is in protocol 18 Section 6 ("BIC run specification"). It is descriptive per section-arm with no verdict, and runs **no GPU IG** at any BIC or forced K. An optional labelled CPU "BIC-K segmentation sensitivity, descriptive" uses posterior-|PCC|; drop it and tell the supervisor if it needs more than a small script. **It runs only after the GBM108_positive decision table has been posted and reviewed; write the job script then.**
6. Uncommitted (Zayd commits): `CLAUDE.md`, protocol 18 (Sections 6 and 10), `docs/supervision/` (chat and staging diff), the synced `results/diagnostics/gate_d_pixel_counts/40TopL_seed1/`, `results/validation/fair_scoring_env_tests/66324_*`, and the item 3 staging change.

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
- **Partitions:** CPU jobs use `--partition=batch` with small memory requests (the fair-scoring tasks peak below 1 GB). `bigbatch` is reserved for long training or demonstrated high memory.
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

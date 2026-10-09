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

## Current work (9–11 October 2026)

The fair-scoring gate in protocol 18 (v3.2) is in progress. The Notion task is "22. Fair-scoring gate".

- **Done:**
  - environment test (jobs 66006 and 66044);
  - partition audit of all 16 sections;
  - `code/msi/results/diagnostics/peak_partition_audit/partition_approval.json` (approved; do not edit it);
  - the GBM22_2 pilot (job 66045).
- **Next:**
  1. `bash slurm_jobs/submit_fair_scoring.sh all` (bin-level).
  2. The same command with `--approval results/diagnostics/peak_partition_audit/partition_approval.json`.
  3. The two `run_fair_scoring_summary.sh` jobs.
  4. Apply the predeclared decision rules in protocol Section 7.
- **Pilot signal, one section only, not a verdict:** posterior-|PCC| and Moran's I beat production IG at bin level on GBM22_2. Report the collection verdicts exactly as the predeclared rules give them.

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
- **Timing:** read the authoritative timing with `sacct -j <id> --format=JobID,State,Elapsed,MaxRSS,ReqMem,NodeList,ExitCode`.

## Working style

- Zayd makes git commits himself. Do not commit or push unless asked.
- Leave the unrelated modified files alone (line-ending changes in older scripts and runtime CSVs).
- Run the relevant unittest modules before proposing a cluster run. Locally, h5py may be missing, so the pipeline tests may need the cluster test job (`slurm_jobs/run_fair_scoring_tests.sh`).
- Explain plainly; Zayd is an Honours student. When a result changes the thesis, say so directly and propose the honest framing.

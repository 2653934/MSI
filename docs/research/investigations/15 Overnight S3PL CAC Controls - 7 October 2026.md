# Overnight S3PL CAC controls — 7 October 2026

## Research question

The existing frozen S3PL CAC checkpoint lost about 0.040 mSCF1 on average when every neighbour was replaced with the centre spectrum at inference. That shows input sensitivity, **not** that real neighbours helped it learn or explain its advantage over the VAE. Tonight's two complementary campaigns narrow that distinction.

## Campaign A: retrained centre-tiled input

- Cluster jobs: **65413** (160TopL pilot) and **65414** (the other seven sections, released only if the pilot succeeds). Earlier pilot 65411 failed in a preflight check because historical logs omitted the default `reference_spatial_max` setting; no model training occurred in that attempt. Its stranded dependent array 65412 was cancelled.
- Same original S3PL architecture, 10 epochs, patch size 9, seed 1, reference spatial-max normalisation and real-patch reconstruction target. Only the model **input** changes: after normalisation, every patch position receives a copy of the unchanged centre spectrum. The trained model is also evaluated with that input. Separate checkpoint/result names end in `_train_tile_centre`.
- Each CAC section uses the predeclared matched peak count: 40TopL 315, 160TopL 210, 200TopL 221, 240TopL 255, 280TopL 245, 360TopL 247, 400TopL 133, 520TopL 232. No masks enter training or peak selection; masks are used for post-hoc mSCF1.
- If the real-input model consistently beats this retrained control, that supports a **training benefit from neighbour-specific input** under this exact architecture and objective. A single seed is still limited; it does not by itself prove the S3PL–VAE gap's cause. The reference normalisation happens before tiling, so the unchanged centre value may still reflect neighbouring intensities through its scale.
- [Training runner](../../../code/msi/slurm_jobs/run_s3pl_cac_trained_centre_control.sh), [submission](../../../code/msi/slurm_jobs/submit_s3pl_cac_trained_centre_control.sh), [completion checker](../../../code/msi/slurm_jobs/check_s3pl_cac_trained_centre_control.sh).

## Campaign B: frozen spatial-arrangement checks

- Submit with `bash slurm_jobs/submit_s3pl_cac_frozen_topology.sh` after syncing the new code to the cluster. It runs 160TopL as a pilot and releases the other seven independent jobs only if the pilot succeeds. Record the returned job IDs here: **pending submission**.
- Reuse each original real-patch 10-epoch CAC checkpoint. Within each section and on the same node, evaluate (1) a fresh real input, (2) a 90-degree rotated normalised patch, and (3) a fixed one-position cyclic shift **within each Chebyshev-distance ring**. The centre spectrum is untouched. Rotation preserves all values and geometric adjacency; the ring shift preserves each radius's spectral multiset but disrupts its ordering. All arms retain the same matched peak count and mSCF1 scoring code.
- Compare the intervention scores and selected-m/z overlap against the fresh real run. Record any drift between that fresh real run and the historical matched-count result; do not silently substitute one for the other.
- These are **post-training out-of-distribution sensitivity tests**. Score changes would show that the frozen model cares about position or orientation; they cannot establish that spatial context improved training or explain a cross-model score gap. Edge zero positions also move. Do not present these as spatial-benefit ablations.
- [Interventions and evaluator](../../../code/msi/scripts/evaluate_s3pl_cac_frozen_topology.py), [array runner](../../../code/msi/slurm_jobs/audit_s3pl_cac_frozen_topology.sh), [completion checker](../../../code/msi/slurm_jobs/check_s3pl_cac_frozen_topology.sh). Reports will be in `code/msi/results/diagnostics/s3pl_cac_frozen_topology/`; all raw evaluation directories have distinct names.

## Morning checklist

From `~/msi` on the cluster:

```bash
squeue -u "$USER" -o '%.18i %.24j %.2t %.10M %.24R'
bash slurm_jobs/check_s3pl_cac_trained_centre_control.sh
bash slurm_jobs/check_s3pl_cac_frozen_topology.sh
```

If a campaign is incomplete, inspect `sacct -X -j <job-id> --format=JobID,State,Elapsed,NodeList,ExitCode` and that job's `.out`/`.err` files before any resubmission. The frozen audit can be rerun safely when a report is missing; it skips already valid reports with the same checkpoint and config hashes. Do not compare partial campaigns as if they were eight-section results.

## First synced outcome (partial)

Jobs 65413_1, 65414_0 and 65414_2 completed the retrained control and wrote matched-count metrics. Their original real-patch versus retrained centre-input mSCF1 values are: 160TopL **0.495 vs 0.130**, 40TopL **0.715 vs 0.177**, and 200TopL **0.665 vs 0.356**. Counts match within each section (210, 315 and 221 respectively). This is a large preliminary difference, **not** yet an eight-section result. Because the centre-only input was still trained to reconstruct a real neighbourhood, the loss target contains information unavailable from that input; the gap may partly reflect this harder reconstruction task rather than only useful peak-discriminative spatial structure.

The five other allocations, 65414_3 through 65414_7, failed the CUDA warm-up **before model or data load**. No failure in their training or scoring code has been observed. Identify their nodes with `sacct` and retry only these five indices with the failing node(s) excluded. No frozen-topology result files were present in the first local sync; confirm whether that separate array was submitted before interpreting its status.

The follow-up `sacct` check identified **mscluster82 for all five CUDA failures**. It has been added to the production CUDA quarantine list. The appropriate recovery is an array containing only indices 3–7; do not rerun the three completed controls.

The topology checker later reported three valid section reports: 40TopL real/rotated/ring-shift mSCF1 **0.715/0.715/0.714**, 160TopL **0.495/0.494/0.495**, and 200TopL **0.665/0.662/0.665**. After the JSON reports arrived locally, selected-m/z overlaps with fresh real were **311/315 and 311/315** for 40TopL, **208/210 and 209/210** for 160TopL, and **220/221 and 221/221** for 200TopL (rotation and ring shift respectively). The 40TopL fresh real set differs from its historical matched-count set by two selected peaks, flagged by the checker. Thus the first three frozen checkpoints' rankings are largely insensitive to these particular position rearrangements; neither the remaining five sections nor the training effect are settled. Do not infer general position invariance or spatial irrelevance.

The synced logs show topology array 65422_3 through 65422_7 also stopped at CUDA warm-up, before model or data load; 65422_0 and 65422_2 completed. Check their nodes with `sacct`, then retry only indices 3–7 using the updated quarantine. The six patch-invariant unit tests passed in each topology allocation before the CUDA check.

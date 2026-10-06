# Two-week investigation plan: Spatial-msiPL and S3PL

**Period:** 28 September–11 October 2026 (ten working days, with the final weekend as contingency)  
**Reason for change:** At the 28 September meeting, Hairong asked us to investigate the weak or mixed spatial effect more thoroughly, test other neighbourhood window sizes, explain S3PL's higher CAC peak quality and shorter observed runtime, and audit our implementation before treating a negative result as reliable.

**Notion tracking:** [Two-week Spatial-msiPL investigation](https://app.notion.com/p/3e9946087a7d8131b3b2d4abd3808025), with dated tasks 12–19.

## Decision we need to support

By the next review, we should be able to say whether the current spatial result reflects (a) an implementation or evaluation error, (b) a poor choice of neighbourhood scale or aggregation, (c) a real dataset-dependent limit of this model, or (d) a combination of these. A failed hypothesis is acceptable if the tests and limits are explicit. We cannot prove software is flawless; we can establish which claims survive targeted tests and independent checks. A critical defect would require correcting and rerunning the affected comparison before using it in the report.

The current evidence is the starting point, **not the conclusion**: at tuned, matched peak counts, uniform context versus centre-only IG changes mean mSCF1 by −0.0067 on GBM (5/8 spatial wins) and +0.0310 on CAC (8/8 spatial wins). CAC S3PL averages 0.5915 against our uniform-context IG's 0.5595; its 10-epoch convolutional protocol differs from our 100-epoch dense VAE. The GBM S3PL reproduction gap is unresolved. These observations motivate the investigation; they do not establish why they occurred.

## Rules for this investigation

1. **Audit before retraining.** Freeze the current code revision, configurations, source files, masks, and published result package. Record every new run's commit, dataset checksum or immutable source path, parameters, seed, node/GPU, job ID, and result directory.
2. **Keep explanations separate.** Test model correctness, spatial information, window size, attribution, and computational cost separately. Do not infer a cause from one aggregate mSCF1 table.
3. **Predeclare comparisons.** Choose pilot sections, primary metrics, resource limits, and promotion criteria before inspecting new outcomes. Use expert masks for evaluation and diagnostics only, never to train the VAE/GMM or tune on the final validation sections.
4. **Use paired evidence.** For each section, compare identical source spectra, masks, peak budgets, scoring code, and attribution settings. Show per-section changes, not only means or p-values. Treat sections as paired units, not independent patients.
5. **Keep results recoverable.** New window experiments get distinct result and checkpoint roots. Existing 3×3 runs and historical figures are never overwritten. Cluster node failures are recorded separately from model failures.

## Workstream A — Verify the implementation (highest priority)

The original neighbour builder and aggregators assumed exactly eight slots; the current implementation now supports 1×1, 3×3 and 5×5 uniform windows in [preprocessing.py](../../code/msi/src/spatial_msipl/preprocessing.py), [neighbourhood.py](../../code/msi/src/spatial_msipl/neighbourhood.py), and [model.py](../../code/msi/src/spatial_msipl/model.py). The contextual model also has a wider first encoder layer than the centre-only model. Both facts affect the interpretation of prior comparisons.

### A1. Data and spatial mapping audit

- Independently reconstruct coordinate-to-spectrum and coordinate-to-mask mappings for a complete CAC section, partial-coverage `280TopL`, and representative GBM sections. Check orientation, one-based coordinates, duplicate/missing pixels, non-square shapes, and edges/corners.
- For each window, verify that only measured pixels enter the context, missing positions have zero weight, the centre is excluded from the neighbour set, and neighbour counts/coordinates match a simple independent reference implementation.
- Compare raw, TIC-normalised, and S3PL-normalised input distributions; check zero spectra, finite values, scale, and whether the same ion image is evaluated against the same mask coordinates.
- Save small visual audits: one central pixel with its window overlaid on the tissue grid, its valid-neighbour mask, and before/after normalisation spectra.

**Pass condition:** automated edge/coverage/orientation tests and a manual visual spot-check agree for the selected sections; no training labels enter preprocessing.

### A2. Model, loss, and training audit

- Check tensor dimensions and parameter counts for centre-only, capacity-matched zero-context, 3×3 uniform, and 5×5 uniform inputs. Verify that the decoder always reconstructs the central spectrum and that invalid neighbours cannot affect output or gradients.
- Numerically cross-check the implemented reconstruction and KL loss against a small independent calculation; confirm the intended beta, reduction, output normalisation, batch-normalisation mode, and gradient flow. Audit the training/evaluation split semantics and label use.
- Test a tiny synthetic problem that the VAE can overfit; compare a continuous run with checkpoint/resume at the same epoch and seed. Record any expected numerical tolerance.
- Inspect scripts for silent fallback behaviour, stale checkpoints, configuration mismatches, duplicated samples, or a result marked complete when only part of the pipeline ran.

**Pass condition:** tests and a signed audit note identify no unresolved result-changing defect. If one is found, log affected artifacts and rerun only those after the fix.

### A3. Attribution and scoring audit

- Recalculate a tiny GMM posterior and Integrated Gradients result independently; check component mapping, IG completeness tolerance, baseline choice, aggregation over central/neighbour paths, ranking, ties, and matched peak-count truncation.
- Independently recompute PCC, four F1 thresholds, and mSCF1 from a small saved example, including constant ion images and partial coverage. Confirm no use of expert labels before final scoring except the documented post-hoc component mapping.
- Repeat the key aggregate calculations from raw section-level files and compare exact values with the publication tables.

**Pass condition:** an audit report links each claim to raw results and a test or independent recomputation; all differences are explained or flagged.

## Workstream B — Test the spatial hypothesis at more than one scale

### B1. Generalise the window safely

- Parameterise an odd square window instead of assuming eight slots. Compare **1×1** (centre-only), **3×3** (eight possible neighbours; existing frozen reference), and **5×5** (24 possible neighbours). A 7×7 window is optional only if the 5×5 pilot is informative and fits the resource budget.
- Keep the **uniform aggregate output at one spectrum of length D**, so the 3×3 and 5×5 contextual VAEs have the same encoder shape and parameter count. Retain the existing narrower centre-only model, and add a **zero-context 2D-input control** to separate access to neighbour data from the extra first-layer capacity.
- Add a spatial-specificity control that shuffles or swaps neighbour spectra while preserving the input shape and approximate intensity distribution. Apply it only under a clearly specified, reproducible rule; do not let evaluation masks drive the shuffle.
- Extend edge, missing-pixel, checkpoint-configuration, resume, and attribution tests for variable slot counts before model-training submission.

**Implementation checkpoint (1 October):** configurable windows, the 2D-wide zero-context control, and seeded nonlocal shuffled context are in the code. Cluster job 62284 passed all 30 preprocessing, model, window, attribution, checkpoint/resume, and shuffled-context tests. CUDA warnings in stderr did not fail this CPU-only suite; GPU availability must still be checked on the pilot's assigned node. The zero-context model has the same *stored parameter count* as uniform context, but weights attached to constant-zero context cannot learn from data. The [test log](../../code/msi/logs/window-tests-62284.err) is the operational record; these tests are not research-quality results.

### B2. Diagnose what the window contains

- Plot valid-neighbour counts for each radius, especially on partial-coverage CAC and irregular GBM grids.
- Measure, as **post-hoc diagnostics**, how often a window crosses expert tissue boundaries and how spectrum similarity changes with distance. These analyses can explain dilution or boundary mixing but must not be used to choose the primary model from validation labels.
- Check whether the uniform average suppresses informative peaks or is dominated by background/normal regions. Inspect representative ion images and selected-peak changes, not just aggregate scores.

### B3. Staged experiment

1. **Pilot:** preselect one GBM and one CAC development section with valid existing 3×3 results. Train 5×5 uniform and zero-context controls with the same preprocessing, 100 epochs, seed, batch size, latent size, loss, and downstream GMM/IG settings as the frozen 3×3 run. Reuse the 3×3 checkpoint only after its metadata passes the audit. Record train, inference, attribution, evaluation, and peak memory separately.
2. **Pilot decision:** inspect per-section mSCF1, F1 at all four thresholds, deterministic reconstruction, GMM agreement, deletion faithfulness, and resource use. Before running, write the minimum meaningful gain and the acceptable faithfulness/cost trade-off in the run manifest. A pilot result is exploratory and cannot support a collection-wide claim.
3. **Confirmation:** if the pilot is sound and informative, run the smallest predeclared held-out section set that can test the same direction in both collections. Expand to all remaining sections only if the compute budget permits and the resulting claim requires it. If a section fails because of CUDA/node problems, repeat that section without changing the scientific settings.
4. **Stability:** repeat a promising window comparison across training seeds on at least one representative section before claiming the effect is robust. If time is short, report seed-1 section-level evidence explicitly and leave multi-seed generalisation open.

**Outcome categories:** larger window helps; smaller window helps; neither helps; effect depends on coverage/boundaries/dataset; or the result is inconclusive due to resource or audit limits. Each category needs a figure and a clear uncertainty statement.

**Predeclared development pilot (1 October; before training/evaluation):** use `GBM108_positive` and `40TopL`, seed 1, and compare their existing 3×3 uniform/centre-only checkpoints with three new arms: 5×5 uniform, 3×3 zero-context, and 3×3 shuffled-context. The shuffled arm keeps the centre and measured-slot mask fixed, but maps each slot through a seed-1701 global measured-pixel permutation to a source *outside that centre's local window*; the exact source map is hashed in the checkpoint. All new arms use 100 epochs, batch 128, hidden width 512, latent width 5, learning rate 0.001, and no explicit spatial loss. The primary exploratory quality comparison is matched-count mSCF1 (530 GBM; 315 CAC), with the four constituent F1 thresholds shown rather than hidden. A change of at least **0.02 absolute mSCF1** is a practical signal worth confirming on other sections, **not** a significance test or a claim from these two development sections. Interpretation also requires a valid IG completeness check, nontrivial deletion-faithfulness advantage over random, deterministic reconstruction, and separately reported training/attribution time and peak memory. If quality improves only at a large resource cost, report the cost rather than promoting a simple "better" claim. Do not choose a winner using these development masks and then count these same sections as independent confirmation.

**Full-section extension (1 October; after the 40TopL pilot, before inspecting the other section outcomes):** run the same three fixed arms on the remaining seven CAC and all eight GBM sections, with seed 1 and each section's previously frozen matched peak count. The completed 40TopL pilot remains *development* evidence, not independent confirmation; `GBM108_positive` is also a preselected development section even though its new-arm runs are still pending. All other sections are confirmation evidence. An array caps concurrent jobs at three, so this is parallel without an unbounded burst of exclusive-node requests. GBM training uses the opt-in in-memory float32 loader because the earlier full-run equivalence experiment reproduced all final weights and loss histories for the historical arms while sharply reducing HDF5 reread time; each new-arm GBM job first requires exact sample equality between cached and streaming inputs on its own section. CAC retains streaming input. Loader choice must be reported separately in runtime comparisons, and the new-arm parity checks do not by themselves prove equal training trajectories. If a configuration fails or times out, rerun only its array index with unchanged scientific settings. A collection-wide result is still a **single-seed, section-level** result, not a multi-seed or independent-patient estimate; the four GBM patients supply two sections each. The confirmatory comparison stays the same: matched-count mSCF1 and its four F1 components, reconstruction, GMM/IG diagnostics and faithfulness, and training/evaluation cost. No arm is selected from the 40TopL score and silently relabelled as prespecified confirmation.

Cluster sequence from `~/msi`: submit training with `bash slurm_jobs/submit_spatial_window_campaign.sh` and monitor with `bash slurm_jobs/check_spatial_window_campaign.sh`. Evaluation can now start for any completed, unevaluated arms using `bash slurm_jobs/submit_spatial_window_campaign_evaluation.sh`; this permits CAC evaluation while GBM training continues. Rerunning that launcher later selects newly trained GBM arms without duplicating completed CAC evaluations. Both arrays use the same fixed index mapping; failed individual indices can be resubmitted with `sbatch --array=INDEX slurm_jobs/run_spatial_window_campaign_array.sh` (or its evaluation counterpart) after checking that no copy is still active. No jobs are launched by editing these files locally: code must first be synced to `~/msi` on the cluster.

**Outcome checkpoint (3 October):** all 48 new-arm local artifact sets are complete, including training, reconstruction, valid attribution and matched-count peak evaluation. Across the seven confirmation sections per collection, real 5x5 did not outperform frozen real 3x3 on mean mSCF1, while shuffled 3x3 was approximately tied with real 3x3. See the [results record](01%20Results%20Record.md#spatial-window-and-context-controls-3-october-2026) for the four-arm values and limits. Workstream B's next task is to inspect section-level and tissue-boundary diagnostics, then decide whether any spatial-specific effect warrants targeted multi-seed confirmation. The finished seed-1 campaign is not a mechanism explanation by itself.

**Follow-on gate (6 October, before new results):** The completed 16-section frozen-attention ranking swap is mixed on CAC and usually favours shuffled input on GBM, but the checkpoint was trained with real neighbours. First screen the input-distribution caveat without retraining: on the already-used exploratory sections `160TopL` and `GBM22_2`, sample up to 512 measured centres per section (sample seed 20261006), recreate the exact seed-1701 shuffle verified by its saved source-slot hash, and compare centre–context cosine and half-L1 distributions for real versus shuffled input. Use no masks, model, GPU, GMM, IG or peak scoring. An observed shift supports caution about the frozen intervention; overlapping distributions on these two statistics cannot prove it is in distribution. These two outcome-known sections are exploratory, not independent confirmation. Only after reading this check should we decide whether a small, matched real-versus-shuffled *training-seed* repeat is informative; do not silently launch a new full-section campaign.

## Workstream C — Explain the S3PL gap and runtime

### C1. Code and protocol comparison

- Trace S3PL's [training](../../code/msi/baselines/s3pl/train.py), [model](../../code/msi/baselines/s3pl/model/Attention3DConvAutoencoder.py), [data source](../../code/msi/baselines/s3pl/utils/data_source.py), normalisation, peak selection, and evaluation against our dense contextual VAE. Produce a one-page table of input shape, spatial receptive field, spectral handling, objective, parameter count, optimiser, batch size, epochs, peak budget, and mask treatment.
- Separate **CAC's observed S3PL advantage** from the **unresolved GBM reproduction gap**. Check which claims come from our measured run, the released implementation, or a figure estimated from the paper; do not treat them as the same evidence.
- On identical CAC sections, compare selected-peak overlap, F1 by PCC threshold, and representative ion images. Determine whether S3PL's margin is broad or concentrated in particular thresholds/sections. Test normalisation or other one-factor explanations only after the code audit identifies a plausible mechanism.

### C2. Comparable cost accounting

- On the same GPU class and representative section, with cold/warm and I/O conditions recorded, measure **data loading/preprocessing, one training epoch and full training, checkpointing, peak extraction/IG, evaluation, and end-to-end wall time**. Synchronise CUDA around GPU timing and report variability from repeats.
- Report parameter count, peak **allocated** GPU tensor memory, reserved GPU memory if available, batch size, samples or pixels processed per second, and checkpoint size. Distinguish GPU computation from cluster queue wait and node failure; neither is model runtime.
- Compare the actual reproduced protocols (S3PL 10 epochs, our VAE 100 epochs) and a diagnostic equal-work budget (for example time/steps or a learning curve). An epoch count alone is not equal work across architectures. We will describe architecture, preprocessing, and attribution overhead as measured contributors rather than declare a single causal explanation without profiling.

**Pass condition:** a reproducible phase-level table and at least one runtime breakdown plot support every performance claim. If hardware cannot be matched, stratify by GPU/node and avoid direct speed ratios.

## Ten-working-day schedule

| Date | Main work | Checkpoint |
|---|---|---|
| Mon 28 Sep | Freeze questions, run manifest, existing artifacts and claim register | Current evidence and unresolved questions listed |
| Tue 29 Sep | Data/coordinate/mask and window reference tests | A1 audit and visual spot-check |
| Wed 30 Sep | Model/loss/checkpoint plus IG/scoring independent checks | A2–A3 audit; critical defects triaged |
| Thu 1 Oct | Implement variable windows and capacity/spatial controls with tests | B1 code review and synthetic tests |
| Fri 2 Oct | Resource canary, predeclare pilot sections/criteria, submit limited pilot | Verified job configuration and monitoring |
| Mon 5 Oct | Evaluate pilot and spatial diagnostics; profile S3PL code path | Pilot table, window maps, S3PL protocol matrix |
| Tue 6 Oct | Investigate observed pilot failures or submit focused confirmation | Decision log with unchanged test protocol |
| Wed 7 Oct | Complete confirmation/seed checks; matched runtime breakdown | Per-section and per-phase outputs |
| Thu 8 Oct | Recompute claims; make uncertainty, ablation, and cost figures | Claim–evidence ledger and limitation list |
| Fri 9 Oct | Write findings and options for Hairong; freeze reproducible package | Two-week review memo with answer to each question |
| 10–11 Oct | Queue/failure buffer only | No silent expansion of experiment scope |

Cluster scheduling is uncertain. If it consumes the buffer, prioritise **audit → 3×3 versus 5×5 plus controls → S3PL phase timing → synthesis**. A missing confirmation run becomes an explicit limitation, not a substituted result.

## Claim–evidence ledger required for the final memo

The first bounded entry is the [spatial-context claim–evidence ledger](investigations/13%20Spatial%20Context%20Claim-Evidence%20Ledger.md),
covering the completed 16-section frozen attention interventions. The wider
GBM/CAC scoring and S3PL claims below remain to be reconciled.

For every substantive sentence in the results/discussion, record: **claim; precise comparison; section/seed count; raw result path; script and code revision; metric definition; uncertainty; alternative explanation; status** (`supported`, `mixed`, `refuted`, or `not tested`). Include at least these claims:

- Spatial context improves peak selection on CAC but not consistently on GBM.
- Changing neighbourhood radius alters spatial information and peak rankings.
- Any benefit is spatial rather than merely extra encoder capacity or a shuffled-context artifact.
- The implementation correctly aligns spectra, coordinates, masks, loss, checkpoints, attribution and evaluation.
- S3PL has higher CAC mSCF1 under matched peak counts; identify where its margin comes from.
- S3PL's observed shorter CAC runtime is explained by a measured phase breakdown under the stated protocols.
- The GBM S3PL reproduction gap remains resolved or unresolved with its exact evidence.

**Final deliverables:** implementation audit with tests and defect log; window-size protocol and results; visual tissue/window diagnostics; S3PL protocol and runtime comparison; updated result figures; claim–evidence ledger; and a short decision memo for Hairong identifying which model claim is supported, which failed, and what remains uncertain.

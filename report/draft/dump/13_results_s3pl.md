# Results: S3PL

### C069 CAC matched-count S3PL versus IG
- Statement: Under their native evaluated protocols and matched final counts, S3PL seed 1 scores above uniform-context IG on CAC.
- Numbers: S3PL 0.5915 vs IG 0.5595; difference +0.032; S3PL wins 6/8.
- Label: descriptive
- Source: `docs/research/investigations/12 CAC S3PL Gap Diagnostics.md`; `docs/research/investigations/14 Primary Results Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Architectures, objectives, normalisation, epochs and selectors differ; does not establish intrinsic superiority.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C070 CAC gap diagnostics
- Statement: S3PL's CAC lead is concentrated at lower PCC thresholds and comes from method-exclusive selected bins.
- Numbers: S3PL−IG: +0.0476 at 0.3, +0.0460 at 0.4, +0.0294 at 0.5, +0.0048 at 0.6; about 79% of selected m/z values shared.
- Label: descriptive
- Source: `docs/research/investigations/12 CAC S3PL Gap Diagnostics.md`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 5.5.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: Locates the score gap but does not causally explain it.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C071 Centre-tiled S3PL controls
- Statement: Removing neighbour-specific input during training makes S3PL collapse toward the random floor under its patch-reconstruction objective.
- Numbers: Real 0.591 vs centre-tiled 0.179 seed 1 and 0.153 seed 2; real higher 8/8 in both seeds.
- Label: "supported"
- Source: `code/msi/results/publication/current_evidence/s3pl_cac_seed_rule.json`; `docs/research/investigations/15 Overnight S3PL CAC Controls - 7 October 2026.md`.
- Verified by supervisor: yes: 2026-10-15
- Caveats: Strong intervention also makes the real patch target unattainable; it shows dependence on neighbour input, not correct topology.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C072 Test N shuffled-neighbour S3PL
- Statement: Correct local placement gives only an inconsistent advantage over retrained nonlocal shuffled neighbours on CAC.
- Numbers: Real−shuffled +0.039 seed 1 (≥0.02 in 4/8), +0.040 seed 2 (3/8); shuffled about 0.55 vs real about 0.59.
- Label: "mixed"
- Source: protocol 18 Section 6.5; `code/msi/results/diagnostics/s3pl_cac_shuffle_control/decisions_20261017_local/`; supervisor chat 2026-10-20 11:31.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: F5 Holm 0.63/0.64, not statistically supported; report seed aggregates per C025.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C073 S3PL training length
- Statement: Longer S3PL training worsens peak quality; the released 10-epoch checkpoint is not an unfair handicap.
- Numbers: Mean CAC 0.591→0.336 and GBM 0.316→0.212 from epoch 10 to 100; epoch 10 best in 15/16 sections, exception GBM108_positive.
- Label: descriptive
- Source: protocol 18 Section 10 item C2; `code/msi/results/publication/current_evidence/training_curves_s3pl.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.3.
- Verified by supervisor: yes: 2026-10-16 17:36
- Caveats: Report fixed 10 epochs; never select per-section best checkpoints. No label-free early-stopping signal was identified.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C074 Ten-seed S3PL distributions
- Statement: Published GBM and CAC collection means both lie outside the ten released-seed collection-mean distributions; best-of-k selection up to k=10 does not explain either.
- Numbers: GBM 0.3193 ± 0.0419, range 0.2260–0.3735 vs 0.496; CAC 0.5470 ± 0.0377, range 0.4960–0.5910 vs 0.601.
- Label: "outside our seed distribution"; "not explained by seed selection alone"
- Source: `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`; supervisor chat 2026-10-20 20:57.
- Verified by supervisor: yes: 2026-10-20 20:57
- Caveats: S3PL in-job mSCF1; paper values rounded; one short CAC list disclosed.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C075 Investigation 21 preprocessing
- Statement: Paper-style TIC normalisation does not explain the GBM reproduction gap and removes the visible released-helper split rather than raising the collection mean.
- Numbers: TIC 0.303 vs released helper 0.324; difference −0.021; n=8, 5 up/3 down; exact p=0.742; HL −0.012 [−0.154, 0.099], r=−0.167.
- Label: "does not explain; seed 1 existed before the predeclaration (0.289 vs 0.316) and was seen during the inventory; seeds 2–3 are blind"
- Source: `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`; supervisor chat 2026-10-20 15:33.
- Verified by supervisor: yes: 2026-10-20 15:33
- Caveats: Released seed 1 differs from the controlled initialisation-screen seed 1.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C076 Investigation 21 source of seed variation
- Statement: On three high-variance GBM sections, initialisation dominates data order overall, and repeated same-seed runs are not dominated by GPU nondeterminism.
- Numbers: Init/order SD: GBM108_positive 0.2220/0.00056, GBM108_negative 0.2264/0.1463, GBM12_2 0.1278/0.0103; init ≥2× order in 2/3; repeat SD 0 in 3/3.
- Label: "initialisation dominant"; "not dominated by nondeterminism"
- Source: `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`; supervisor chat 2026-10-21 14:21.
- Verified by supervisor: yes: 2026-10-21 14:21
- Caveats: 3 sections ×5 seeds, descriptive; GBM108_positive's pattern was largely visible before Part C.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C077 S3PL multi-solution interpretation
- Statement: Under released preprocessing S3PL reaches at least two distinct solutions on the tested sections, mostly selected by starting weights; in GBM108_negative data order also matters.
- Numbers: Init ranges: GBM108_positive about 0.02–0.45; GBM12_2 about 0.27–0.52; GBM108_negative order outcomes about 0.36–0.41 vs 0.65, init/order ratio 1.55.
- Label: descriptive
- Source: supervisor chat 2026-10-21 14:21; `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`.
- Verified by supervisor: yes: 2026-10-21 14:21
- Caveats: Bounded to three selected sections; not a universal optimisation claim.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

# Computational considerations

### C031 Cache speed-up
- Statement: Caching a section once removed repeated HDF5 access and reduced the audited 100-epoch uniform run from 40,608.9 s to 1,355.4 s with identical losses and final state.
- Numbers: Uniform 29.96×; centre 40,178.6→1,309.0 s, 30.69×; one-time cache 12.80–14.17 s.
- Label: descriptive
- Source: `docs/research/investigations/10 GBM Training Runtime Investigation.md`; `code/msi/results/publication/current_evidence/runtime_all_sections_v2.csv`; supervisor chat 2026-10-20 10:44.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: Likely I/O mechanism, not separately measured; implementation speed-up, not a changed scientific result.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C032 Runtime profile
- Statement: Data preparation dominated streaming batches; caching reduced mean batch preparation from about 24.6 s to 0.72 s.
- Numbers: 24.580→0.721 s/batch; centre streaming transfer 0.163 s, forward 0.0018 s, loss 0.0085 s, backward 0.0126 s.
- Label: descriptive
- Source: `docs/research/investigations/10 GBM Training Runtime Investigation.md` jobs 61461 and 61464.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: One audited section/hardware path.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C033 Collection training times
- Statement: Cached 100-epoch VAE training is slower than 10-epoch S3PL on collection medians, but practical after caching.
- Numbers: GBM VAE centre/uniform 31.7–34.0/32.5–34.6 min vs S3PL 13.7; CAC 1.3–1.4 vs 0.9; RCC 2.2 vs 1.6.
- Label: descriptive
- Source: `code/msi/results/publication/current_evidence/runtime_all_sections_v2.csv`; `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.4.
- Verified by supervisor: yes: 2026-10-20 10:44
- Caveats: Epoch-summed training, not equal work or full workflow; seeds/nodes differ.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C034 Native workflow repeats
- Statement: In three 160TopL RTX 3060 repeats, the complete VAE workflow used less wall time and sampled memory than S3PL; this does not establish intrinsic efficiency.
- Numbers: S3PL 151.18/173.90/173.87 s; VAE 135.30/121.63/121.87 s; S3PL RSS 1.31–1.32 GiB, GPU 315 MiB; VAE RSS 1.15–1.18 GiB, GPU 237 MiB.
- Label: descriptive
- Source: `docs/research/investigations/16 S3PL GBM Stability and Runtime Synthesis.md`; `docs/research/investigations/14 Primary Results Claim-Evidence Ledger.md`.
- Verified by supervisor: yes: 2026-10-19 update
- Caveats: One section/hardware configuration and unequal objectives/epochs.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C035 Ranking-stage timing
- Statement: From a fixed segmentation, posterior correlation takes about a second or less while IG takes seconds to minutes; timed rankings reproduce saved rankings exactly where comparable.
- Numbers: Median seconds GBM/CAC/RCC: posterior 1.12/0.028/0.12; Moran 8.4/0.18/0.80; mean 0.10/0.003/0.014; oracle 1.5/0.08/0.27; IG 770/6.0/417. RCC 28/28 comparable hashes identical.
- Label: descriptive
- Source: `docs/meetings/2026-10-19_update/results_chapter_draft.md` Section 6.4; `code/msi/results/diagnostics/ranking_stage_runtime/`; `code/msi/results/diagnostics/ranking_stage_runtime_rcc_bigbatch_shared/`; supervisor chat 2026-10-20 10:46.
- Verified by supervisor: yes: 2026-10-20 10:46
- Caveats: IG includes GMM fit and faithfulness checks; CPU models differ; RCC nodes shared, not exclusive.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C036 Bit-identity gates
- Statement: Cached VAE audits were exactly equal in losses and weights; S3PL same-seed RTX 3090 repeats were bit-identical in losses, score and peak list on all three tested sections.
- Numbers: VAE 2/2 arms exact; S3PL 3/3 sections, repeat SD=0.
- Label: descriptive
- Source: `docs/research/investigations/10 GBM Training Runtime Investigation.md`; `docs/research/investigations/21 S3PL Seed Sensitivity and Reproduction Gap.md`; supervisor chat 2026-10-21 14:21.
- Verified by supervisor: yes: 2026-10-21 14:21
- Caveats: Hardware/path-specific reproducibility, not model validity.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C037 Cluster lessons and incidents
- Statement: `bigbatch` lacks GPU Gres; CPU exact reproduction is model-specific; avoid `--exclusive` on busy bigbatch; pre-create shared array output folders.
- Numbers: Investigation 21 Part B had 6 early NFS directory-race failures, then targeted retries; S3PL RTX 3090 repeats were bit-identical.
- Label: descriptive
- Source: `CLAUDE.md`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Section 10.
- Verified by supervisor: yes: current-state guidance reviewed 2026-10-21 14:41
- Caveats: Operational provenance, not scientific effects.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

### C038 Environment disclosure
- Statement: GPU jobs used real CUDA warm-up and quarantine exclusions; cluster scoring and local statistics record their distinct environments and hashes.
- Numbers: Cluster Python 3.11.5, NumPy 2.4.6, sklearn 1.9.0; Section 6.6 tests 14/14.
- Label: descriptive
- Source: `CLAUDE.md`; `docs/research/18 Fair Scoring and Simple Baselines Protocol.md` Sections 8–10; supervisor chat 2026-10-20 11:34.
- Verified by supervisor: yes: 2026-10-20 11:31
- Caveats: Results are not silently mixed across environments or roots.
- Placement: [ ] BODY  [ ] APPENDIX  [ ] CUT

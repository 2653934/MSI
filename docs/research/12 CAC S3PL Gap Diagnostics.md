# Where does the matched-count CAC S3PL quality gap occur?

Status: all-eight-section frozen-result diagnostic complete locally; representative raw ion-image job prepared but **not yet run**. This extends the [S3PL architecture and runtime audit](11%20S3PL%20Architecture%20and%20Runtime%20Audit.md). No model was retrained or re-evaluated.

## What was compared

For each of the eight CAC sections, this analysis reads the existing matched-count S3PL `metrics.json` and selected-peak CSV, and our frozen uniform-context IG `summary.json` and selected-peak CSV. It verifies that each list has exactly the section's matched peak budget and that the source mSCF1 values agree with the existing aggregate CSV. Peak overlap is an **exact selected m/z-value match** on the same section, not an approximate tolerance window or a molecule identification. The methods' training, normalisation and ranking protocols remain different even though the final peak count is matched.

The four mixed-class F1 values are indexed by PCC threshold $t \in \{0.3,0.4,0.5,0.6\}$. Positive differences below mean S3PL scored higher. The section mSCF1 is the mean over those four thresholds. S3PL's saved mSCF1 is rounded to three decimals; threshold-level F1 is retained at full stored precision, so small differences in the displayed aggregates are expected.

## Findings from the frozen artifacts

| PCC threshold | Mean S3PL − uniform IG mixed F1 | S3PL wins / IG wins / ties (8 sections) |
|---|---:|---:|
| 0.3 | +0.0476 | 6 / 1 / 1 |
| 0.4 | +0.0460 | 6 / 1 / 1 |
| 0.5 | +0.0294 | 6 / 2 / 0 |
| 0.6 | +0.0048 | 4 / 1 / 3 |

The mean matched-count mSCF1 difference is about +0.032 for S3PL, with wins on six of eight sections. The largest S3PL lead is **360TopL (+0.078)**; the largest IG lead is **520TopL (+0.012 in IG's direction)**. In 360TopL, S3PL's advantage is especially visible at 0.3 and 0.4 (+0.101 and +0.122). At 520TopL, the two methods tie at 0.3/0.4 but IG leads at 0.5/0.6. Thus S3PL's aggregate advantage is **not uniform across PCC thresholds**. These are descriptive paired observations, not evidence of a causal mechanism or a new significance test.

The two matched-size selected lists share **69.9%–84.6%** of their m/z values by section (mean of section fractions: **79.4%**). For example, 360TopL shares 187 of 247 peaks (75.7% of each list), whereas 520TopL shares 191 of 232 (82.3%). High overlap alongside different F1 means the non-shared selections may matter, but it does **not** prove that those peaks alone explain the gap: the reported F1 is a set-level metric, thresholds change the reference-positive bins, and the methods can rank shared peaks differently. A targeted scored swap or counterfactual selection analysis would be needed to isolate the contribution of the exclusive subset.

![Matched-count S3PL versus uniform IG score by section and threshold](../../results/model-comparisons/cac_s3pl_ig_thresholds.png)

![Matched-count selected m/z overlap](../../results/model-comparisons/cac_s3pl_ig_peak_overlap.png)

Machine-readable [diagnostics JSON](../../code/msi/results/comparisons/s3pl_cac_gap_diagnostics/diagnostics.json) includes every section's score difference, threshold differences, shared counts, Jaccard values, and rank-ordered method-exclusive m/z lists. The reproducible [analysis script](../../code/msi/scripts/analyse_s3pl_cac_gap.py) reads the frozen files and writes these figures; it does not use expert masks to choose or train peaks.

## Next visual check: raw ion images

The optional CPU-only [cluster job](../../code/msi/slurm_jobs/visualise_s3pl_cac_gap_ions.sh) reads the existing CAC HDF5 adapters, not checkpoints. It draws expert-class maps and raw log-intensity ion images for the **first three highest-ranked peaks unique to each method** on 360TopL (largest S3PL lead) and 520TopL (largest IG lead). Choosing sections by observed outcomes makes this an **exploratory illustration**, not a held-out validation. Choosing images by rank rather than PCC avoids picking visually favourable ions from each list. The mask is displayed only after selection and never enters training or ranking.

After syncing the new script and job to `~/msi`, submit:

```bash
cd ~/msi
sbatch slurm_jobs/visualise_s3pl_cac_gap_ions.sh
```

Then inspect `logs/cac-gap-ions-<jobid>.out` and `.err` and sync back `results/comparisons/s3pl_cac_gap_diagnostics/`. The intended new files are `360TopL_exclusive_ion_images.png` and `520TopL_exclusive_ion_images.png`. The panels use **individual colour scales** and show spatial pattern, not directly comparable absolute intensity. Missing grid locations are grey; the class map is post-hoc reference context. If the ion images are uninformative, do not infer a mechanism from appearance alone.

## What remains to test before explaining the gap

This analysis identifies **where** S3PL's score lead occurs, not **why**. Plausible contributors include its different patch-reconstruction objective, reference normalisation, learned spatial convolution, per-pixel attention aggregation, and ranking strategy. The next controlled comparison should change one factor at a time while freezing the section, peak budget and evaluator. In particular, the normalisation difference documented in the preceding audit is testable without claiming beforehand that it causes the observed pattern.

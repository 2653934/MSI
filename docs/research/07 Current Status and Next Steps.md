# Current Status and Next Steps

Last updated: 2026-09-20

## Current state

Completed:

- CAC and GBM inspection, masks and visualisation.
- Legacy msiPL reproduction on both collections.
- S3PL CAC runs and documented MassNet GBM reproduction gap.
- Spatial-msiPL preprocessing, model, tests and development experiments.
- Frozen uniform-mean choice.
- Whole-GBM uniform-mean and centre-only training.
- Whole-GBM reconstruction comparison.
- `GBM108_positive` Integrated Gradients pilot and sampling stability.

Running:

- Canary job `56971`: `GBM108_negative`, 458 matched peaks.
- Purpose: validate both the scientific pipeline and adaptive CUDA failover.

Not yet complete:

- Attribution/evaluation on the remaining six non-development GBM sections.
- Whole-GBM attribution aggregate.
- Frozen Spatial-msiPL validation on CAC.
- Final cross-dataset synthesis and dissertation-ready writing.

## Immediate decision tree

### If canary job 56971 completes

Run:

```bash
cd ~/msi
bash slurm_jobs/submit_spatial_msipl_gbm_attribution.sh
```

The submission script skips completed evaluations, submits only missing
sections and schedules the aggregate summary after successful dependencies.

### If CUDA warm-up fails

The same job should record the node and requeue. Check:

```bash
cat logs/gbm-ig-56971.failed_nodes
squeue -j 56971
```

If Slurm rejects automatic requeue, the `.err` log will say so. That is an
infrastructure limitation, not a model result.

## Whole-GBM attribution analysis

The aggregate will report, per section and overall:

- Integrated Gradients mSCF1;
- legacy msiPL mSCF1;
- first-layer L2 mSCF1;
- IG minus legacy effect;
- win/loss counts;
- paired Wilcoxon result;
- GMM balanced accuracy, ARI and NMI;
- peak budgets matched to each legacy section.

### Interpretation gate

If IG consistently beats legacy msiPL and L2, the supported claim is that the
spatial nonlinear representation improves peak selection even though it does
not consistently improve reconstruction.

If effects are mixed, report the heterogeneity and examine whether it tracks
GMM-mask agreement, class imbalance or coverage. Do not tune each validation
section until it becomes positive.

## CAC validation

After the GBM method is evaluated, freeze all choices before moving to CAC:

- uniform-mean neighbourhood;
- central-only control;
- five-dimensional latent space and matched training controls;
- label-free clustering, adapted to three classes;
- nonlinear attribution and matched peak evaluation;
- reconstruction and computational-cost comparison.

CAC is a generalisation test, not another development set. Any unavoidable
dataset-specific change—such as three GMM components instead of two—must be
defined from dataset structure rather than outcome tuning.

## Final outputs

The final research package should contain:

1. Dataset and mask validation figure.
2. msiPL and S3PL reproduction table.
3. Neighbourhood development comparison.
4. Whole-GBM centre-only versus uniform reconstruction figure.
5. Whole-GBM matched peak-selection figure.
6. Faithfulness and representative ion-image figure.
7. CAC generalisation figure.
8. Runtime, parameter and GPU-memory table.
9. Limitations covering small section count, transductive unsupervised training,
   paper/release ambiguity and cluster infrastructure.

## Expected remaining sequence

```text
canary
  -> remaining GBM attribution
  -> aggregate and interpret GBM
  -> frozen CAC production and evaluation
  -> cross-dataset statistics and figures
  -> methods/results/discussion writing
```

The experimental scope should narrow after the whole-GBM attribution result.
New experiments should answer a clear unresolved question, not merely search
for a better-looking score.

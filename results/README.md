# Results gallery

Start here when you want to *see* the research results. This folder is a small, curated set of figures copied from `code/msi/results/`; it is not another cluster output directory. The originals, JSON/CSV metrics, per-section figures, logs, and reproducibility records remain under [`code/msi/results/`](../code/msi/results/). Nothing in that directory was moved or deleted.

These are snapshots, not automatically updated copies. If a plot is regenerated, check its underlying metrics and then refresh the corresponding image here. Do not treat an older gallery image as newer evidence than its source.

## The main story

1. [Peak quality across methods](key-findings/figure_1_primary_peak_quality.png) — the matched-count primary comparison for GBM and CAC. [Source and numbers](../code/msi/results/publication/current_evidence/README.md).
2. [Effect of spatial context by section](key-findings/figure_2_context_effect_by_section.png) — context helps consistently on CAC, but not consistently on GBM. This conclusion is about the tested uniform-mean context, not every possible neighbourhood model.
3. [Explanation-method ablation](key-findings/figure_3_explanation_ablation.png) — compare nonlinear Integrated Gradients with first-layer L2 and tuned legacy msiPL. First-layer L2 is a simple comparator, not the full legacy LearnPeaks method.
4. [Training-seed stability](key-findings/figure_4_seed_stability.png) — the targeted three-seed GBM108-positive check, not a whole-dataset multi-seed result.
5. [Selected-peak overlap](key-findings/figure_5_context_peak_overlap.png) — how much centre-only and contextual selections agree.
6. [S3PL on CAC](key-findings/figure_s1_s3pl_contextual_cac.png) — an architecture benchmark with matched evaluation peak counts; its training protocol is still different (10 epochs).

The accompanying numeric tables are in [aggregate results](../code/msi/results/publication/current_evidence/aggregate_method_results.csv) and [section-level results](../code/msi/results/publication/current_evidence/section_level_results.csv). Read those before quoting a value from a plot.

## What the datasets look like

- GBM MassNet: [mask overview](datasets/gbm_massnet_overview_masks.png) · [measured-pixel coverage](datasets/gbm_massnet_overview_coverage.png)
- CAC: [mask overview](datasets/cac_overview_mask.png) · [measured-pixel coverage](datasets/cac_overview_coverage.png)

For individual sections, ion images, and TIC overlays, browse [GBM visualisations](../code/msi/results/visualisations/gbm_massnet/) and [CAC visualisations](../code/msi/results/visualisations/cac/).

## More detailed comparisons

- [GBM reconstruction](model-comparisons/reconstruction_validation.png) — centre-only versus spatial model reconstruction across sections.
- [GBM selected peaks](model-comparisons/attributed_peak_validation.png) and [context attribution control](model-comparisons/context_attribution_control.png).
- [CAC peak selection](model-comparisons/cac_peak_selection_comparison.png) and [CAC computational comparison](model-comparisons/cac_computational_comparison.png).
- [S3PL GBM runtime diagnostics](model-comparisons/runtime_diagnostics.png). Compare training protocols and input sizes before interpreting a runtime ratio.

Detailed per-run evidence remains in [`code/msi/results/experiments/`](../code/msi/results/experiments/) and [`code/msi/results/comparisons/`](../code/msi/results/comparisons/). Model architecture diagrams are in [`report/final/figures/architecture_panels/`](../report/final/figures/architecture_panels/).

## Local-versus-cluster boundary

`results/` here is a **sibling** of `code/msi/`. Our [documented upload command](../docs/operations/cluster_sync.md) is run from `code/msi/`, so this gallery is outside its transfer source and will not be uploaded to the cluster. If you ever run `rsync` from the outer repository root, explicitly add `--exclude='/results/'` or the gallery would be included. The cluster-generated files still download into `code/msi/results/`, not here.

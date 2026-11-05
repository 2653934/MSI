"""Build images/qualitative_example.pdf: what each ranking selects on one GBM section
(plan: report/draft/planning/qualitative_figure_plan.md, agreed 4 Nov).

Section (rule fixed before rendering): GBM, uniform_mean arm, training seed 1 (the only
seed with K = 6 models); the 8 sections sorted by IG minus posterior correlation mSCF1 at
class K (K = 2), bin level at K_bin, ascending, ties alphabetical; the 4th is drawn. The
script recomputes the order from the production summaries and refuses if it is not
SECTION, and cross-checks it against the label-free K decision table.

Panels and sources (paths relative to code/msi/results/):
1. Expert mask: diagnostics/dataset_contact_20261031/<section>.npz (x, y, labels, tic;
   job 79301), palette of images/dataset_overview.pdf (normal blue, tumour orange).
2. GMM hard segmentation, K = 2 (production):
   experiments/spatial_msipl_gmm_integrated_gradients/<section>_seed1/uniform_mean/
   coordinates_and_gmm.npz (sha256 checked against the fair-scoring provenance).
3. GMM hard segmentation, K = 6 (label-free K, P18 Section 6.10):
   experiments/label_free_k_20261104/<section>_seed1/uniform_mean/steps64/attribution/
   coordinates_and_gmm.npz; colours from cluster_colour in
   code/msi/scripts/run_spatial_msipl_gmm_integrated_gradients.py (read, not copied).
Panels 4-5 (dropped from the drawn figure, still checked and printed):
4. Top-ranked bin under posterior correlation (posterior_abs_pcc_balanced) and
5. Top-ranked bin under IG (integrated_gradients), both at class K: rankings from
   diagnostics/fair_scoring_baselines/bin_level_only/<section>_seed1/uniform_mean/
   rankings_prefix.npz (same full-ranking hashes as the current IG-steps composite
   summary); ion values and per-class raw PCC from
   visualisations/qualitative_example/<section>_seed1_uniform_mean_ion_images.npz,
   written on the cluster by the committed scripts/export_rcc_ion_images.py (read-only
   CPU job). The script checks that the exported bins are the saved top-ranked bins and
   that the IG bin is rank 1 of the saved IG list
   experiments/spatial_msipl_gbm_tuned_count_evaluation/<section>_seed1/uniform_mean/
   ig_matched_<K_bin>_bins.csv.

Ion images are divided by the per-pixel TIC (GBM spectra are already TIC-normalised, so
TIC = 1 to 1e-15), clipped at their own 99th percentile and drawn with one colour map;
unmeasured grid positions are blank. |PCC| is with the tumour mask over measured pixels,
recomputed here and checked against the exported reference PCC. ARI is between the hard
segmentation and the expert mask. Prints every value it draws.
Run: python report/draft/figures/qualitative_example.py
"""

import ast
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from sklearn.metrics import adjusted_rand_score  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MSI = ROOT / "code" / "msi"
RESULTS = MSI / "results"
DIAGNOSTICS = RESULTS / "diagnostics"
COMPOSITE = (DIAGNOSTICS / "ig_steps_20261030" / "composite_root" / "results" / "diagnostics"
             / "fair_scoring_baselines" / "bin_level_only")
FAIR = DIAGNOSTICS / "fair_scoring_baselines" / "bin_level_only"
LABEL_FREE = RESULTS / "experiments" / "label_free_k_20261104"
DECISIONS = (DIAGNOSTICS / "fair_scoring_baselines" / "label_free_k_20261104"
             / "decisions_20261104_local" / "per_section.csv")
IG_SCRIPT = MSI / "scripts" / "run_spatial_msipl_gmm_integrated_gradients.py"
OUTPUT = ROOT / "report" / "draft" / "images" / "qualitative_example.pdf"
PREVIEW = ROOT / "report" / "draft" / "planning" / "tmp_rt" / "qualitative_example.png"

GBM = ["GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2", "GBM22_1", "GBM22_2",
       "GBM39_1", "GBM39_2"]
ARM, SEED, POSITION = "uniform_mean", 1, 4
SECTION = "GBM39_2"   # the 4th by the rule above; the script refuses if it is not
IG, CORRELATION = "integrated_gradients", "posterior_abs_pcc_balanced"
MASK = {1: ("normal", "#0072B2"), 2: ("tumour", "#E69F00")}   # as dataset_overview.py
TUMOUR = 2
ION_CMAP = "magma"
plt.rcParams.update({"font.size": 5.5, "font.family": "DejaVu Sans", "savefig.dpi": 300})


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cluster_colours():
    """CLUSTER_COLOURS from the IG script, read with ast so torch is not imported."""
    for node in ast.parse(IG_SCRIPT.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and node.targets[0].id == "CLUSTER_COLOURS":
            return ast.literal_eval(node.value)
    raise ValueError("CLUSTER_COLOURS not found")


def cluster_colour(component, palette):
    return palette[int(component) % len(palette)]   # same rule as the IG script


def select_section():
    with DECISIONS.open(encoding="utf-8") as handle:
        table = {row["section"]: row for row in csv.DictReader(handle)
                 if row["collection"] == "GBM" and row["arm"] == ARM}
    differences = {}
    for section in GBM:
        summary = json.loads((COMPOSITE / f"{section}_seed{SEED}" / ARM / "summary.json")
                             .read_text(encoding="utf-8"))
        if summary["status"] != "complete":
            raise ValueError(f"{section}: production summary not complete")
        scores = summary["bin_level"]
        ig, correlation = scores[IG]["1.0"]["mSCF1"], scores[CORRELATION]["1.0"]["mSCF1"]
        row = table[section]
        if (abs(float(row["production_ig"]) - ig) > 1e-12
                or abs(float(row["production_correlation"]) - correlation) > 1e-12):
            raise ValueError(f"{section}: decision table and production summary differ")
        if int(row["label_free_k"]) != 6:
            raise ValueError(f"{section}: no K = 6 model")
        differences[section] = (ig - correlation, ig, correlation)
    order = sorted(GBM, key=lambda s: (differences[s][0], s))
    print("Selection: IG minus correlation mSCF1, class K, bin level, ascending")
    for rank, section in enumerate(order, 1):
        difference, ig, correlation = differences[section]
        print(f"  {rank}. {section}: {difference:+.4f} (IG {ig:.4f}, correlation "
              f"{correlation:.4f})")
    if order[POSITION - 1] != SECTION:
        raise SystemExit(f"rule selects {order[POSITION - 1]}, not {SECTION}")
    return order


def grid(x, y, values):
    """Same convention as dataset_overview.py; unmeasured positions stay NaN."""
    x, y = x - x.min(), y - y.min()
    image = np.full((y.max() + 1, x.max() + 1), np.nan)
    image[y, x] = values
    return image


def load_segmentation(path, x, y):
    data = np.load(path)
    if not (np.array_equal(data["x"].astype(int), x) and np.array_equal(data["y"].astype(int), y)):
        raise ValueError(f"{path}: coordinates differ from the mask")
    return data["component"].astype(int)


def pearson(a, b):
    a, b = a - a.mean(), b - b.mean()
    return float((a @ b) / np.sqrt((a @ a) * (b @ b)))


def main():
    select_section()
    run = f"{SECTION}_seed{SEED}"
    contact = np.load(DIAGNOSTICS / "dataset_contact_20261031" / f"{SECTION}.npz")
    x, y = contact["x"].astype(int), contact["y"].astype(int)
    labels, tic = contact["labels"].astype(int), contact["tic"].astype(float)
    if sorted(np.unique(labels).tolist()) != sorted(MASK):
        raise ValueError("unexpected mask classes")

    production = RESULTS / "experiments" / "spatial_msipl_gmm_integrated_gradients" / run / ARM
    composite = json.loads((COMPOSITE / run / ARM / "summary.json").read_text(encoding="utf-8"))
    provenance = composite["provenance"]["source_artifacts"]["coordinates_and_gmm"]["sha256"]
    if sha256(production / "coordinates_and_gmm.npz") != provenance:
        raise ValueError("production GMM file differs from the fair-scoring provenance")
    k2 = load_segmentation(production / "coordinates_and_gmm.npz", x, y)
    label_free = LABEL_FREE / run / ARM / "steps64"
    k6 = load_segmentation(label_free / "attribution" / "coordinates_and_gmm.npz", x, y)
    if len(np.unique(k2)) != 2 or len(np.unique(k6)) != 6:
        raise ValueError(f"components: K=2 has {np.unique(k2)}, K=6 has {np.unique(k6)}")

    fair = json.loads((FAIR / run / ARM / "summary.json").read_text(encoding="utf-8"))
    for method in (IG, CORRELATION):
        if fair["rankings"][method] != composite["rankings"][method]:
            raise ValueError(f"{method}: saved ranking differs from the current composite")
    prefixes = np.load(FAIR / run / ARM / "rankings_prefix.npz")
    top = {method: int(prefixes[method][0]) for method in (IG, CORRELATION)}
    with (RESULTS / "experiments" / "spatial_msipl_gbm_tuned_count_evaluation" / run / ARM
          / f"ig_matched_{fair['K_bin']}_bins.csv").open(encoding="utf-8") as handle:
        first = next(csv.DictReader(handle))
    if int(first["rank"]) != 1 or int(first["bin_index"]) != top[IG]:
        raise ValueError("IG top bin differs from the saved IG list")

    export_path = (RESULTS / "visualisations" / "qualitative_example"
                   / f"{run}_{ARM}_ion_images.npz")
    if not export_path.exists():
        raise SystemExit(f"missing {export_path}: run the cluster export first")
    export = np.load(export_path)
    if not (np.array_equal(export["x"].astype(int), x) and np.array_equal(export["y"].astype(int), y)):
        raise ValueError("export coordinates differ from the mask")
    classes = export["class_values"].tolist()
    ions = {}
    for method in (IG, CORRELATION):
        bins = export[f"{method}__bins"]
        if not np.array_equal(bins, prefixes[method][:len(bins)]):
            raise ValueError(f"{method}: exported bins differ from the saved ranking")
        values = export[f"{method}__ion_values"]
        values = values[:, 0] if values.shape[0] == len(x) else values[0]
        image = values.astype(float) / tic
        pcc = abs(pearson(image, (labels == TUMOUR).astype(float)))
        reference = abs(float(export[f"{method}__pcc_per_class"][0, classes.index(TUMOUR)]))
        if abs(pcc - reference) > 1e-4:   # float32 export vs float64 reference
            raise ValueError(f"{method}: |PCC| {pcc} differs from the exported {reference}")
        ions[method] = (image, float(export[f"{method}__mz"][0]), pcc)

    ari = {2: adjusted_rand_score(labels, k2), 6: adjusted_rand_score(labels, k6)}
    palette = cluster_colours()
    fig, axes = plt.subplots(1, 3, figsize=(3.4, 1.35), gridspec_kw={"wspace": 0.06})
    values = sorted(MASK)
    axes[0].imshow(grid(x, y, np.searchsorted(values, labels)),
                   cmap=ListedColormap([MASK[v][1] for v in values]),
                   vmin=-0.5, vmax=len(values) - 0.5, interpolation="nearest")
    for axis, k, components in ((axes[1], 2, k2), (axes[2], 6, k6)):
        axis.imshow(grid(x, y, components),
                    cmap=ListedColormap([cluster_colour(c, palette) for c in range(k)]),
                    vmin=-0.5, vmax=k - 0.5, interpolation="nearest")
    # Ion panels were dropped (4 Nov): a single rank-1 bin is not what mSCF1 scores, and on
    # this section IG's rank-1 bin has the higher |PCC| although correlation's full list
    # scores higher. The ion checks above still run and their values are printed.
    titles = ("Expert mask", "GMM, K = 2", "GMM, K = 6 (BIC)")
    notes = ("normal / tumour", f"ARI {ari[2]:.2f}", f"ARI {ari[6]:.2f}")
    for axis, title, note in zip(axes, titles, notes):
        axis.set_title(title, fontsize=7, pad=2)
        axis.text(0.5, -0.04, note, transform=axis.transAxes, ha="center", va="top",
                  fontsize=6.5, linespacing=1.1)
        axis.set_xticks([])
        axis.set_yticks([])
        for spine in axis.spines.values():
            spine.set_visible(False)

    print(f"Section {SECTION}: ARI K=2 {ari[2]:.4f}, K=6 {ari[6]:.4f}")
    for method in (CORRELATION, IG):
        image, mz, pcc = ions[method]
        print(f"  {method}: bin {top[method]}, m/z {mz:.4f}, |PCC| tumour {pcc:.4f}")
    fig.savefig(OUTPUT, bbox_inches="tight", pad_inches=0.01)
    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PREVIEW, bbox_inches="tight", pad_inches=0.01, dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()

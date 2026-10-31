"""Build images/dataset_overview.pdf: one representative section per collection, picked
by Zayd from report/draft/planning/dataset_contact_sheet.pdf (2026-10-31).
Top row: GBM base-peak intensity (its HDF5 spectra are TIC-normalised, so TIC = 1);
CAC and RCC total ion current. Bottom row: annotation. Unmeasured grid positions are
blank. CAC class 0 is background (the outer region in every section; S3PL names the
classes tumour, healthy tissue and background); classes 1 and 2 are tumour and healthy
tissue in an undocumented order. RCC: cancer, normal and the unannotated class (grey).

Sources: code/msi/results/diagnostics/dataset_contact_20261031/<section>.npz (job 79301;
x, y, tic, labels) and dataset_basepeak_gbm_20261031/<section>.npz (job 79303; x, y,
base_peak, labels), read on the cluster with the committed read_h5_metadata and pulled.
Run: python report/draft/figures/dataset_overview.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DIAGNOSTICS = ROOT / "code" / "msi" / "results" / "diagnostics"
TIC = DIAGNOSTICS / "dataset_contact_20261031"
BASE_PEAK = DIAGNOSTICS / "dataset_basepeak_gbm_20261031"
OUTPUT = ROOT / "report" / "draft" / "images" / "dataset_overview.pdf"
GBM_SECTION = "GBM22_2"   # Zayd's pick from the base-peak page (2026-10-31)
# Okabe-Ito colours (colour-blind safe); grey for background and unannotated pixels.
PANELS = (
    ("GBM", "base-peak intensity", BASE_PEAK, "base_peak",
     {1: ("normal", "#0072B2"), 2: ("tumour", "#E69F00")}),
    ("CAC", "total ion current", TIC, "tic",
     {0: ("background", "#BBBBBB"), 1: ("tumour/healthy\n(class 1)", "#0072B2"),
      2: ("tumour/healthy\n(class 2)", "#009E73")}),
    ("RCC", "total ion current", TIC, "tic",
     {0: ("cancer", "#E69F00"), 1: ("normal", "#0072B2"), 2: ("unannotated", "#BBBBBB")}),
)
SECTIONS = {"GBM": GBM_SECTION, "CAC": "40TopL", "RCC": "RCC_UH0505_12"}
plt.rcParams.update({"font.size": 7, "font.family": "DejaVu Sans", "savefig.dpi": 300})


def grid(x, y, values):
    """Place per-pixel values on the measured grid; unmeasured positions stay NaN."""
    x, y = x - x.min(), y - y.min()
    image = np.full((y.max() + 1, x.max() + 1), np.nan)
    image[y, x] = values
    return image


def main():
    if SECTIONS["GBM"] is None:
        raise SystemExit("set GBM_SECTION to Zayd's pick first")
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 2.6),
                             gridspec_kw={"hspace": 0.18, "wspace": 0.75})
    for column, (collection, measure, folder, key, classes) in enumerate(PANELS):
        section = SECTIONS[collection]
        record = json.loads((folder / "summary.json").read_text(encoding="utf-8"))[section]
        data = np.load(folder / f"{section}.npz")
        x, y = data["x"].astype(int), data["y"].astype(int)
        labels = data["labels"].astype(int)
        if record["pixels"] != len(labels):
            raise ValueError(f"{section}: pixel count differs from the job summary")
        values = sorted(classes)
        if sorted(np.unique(labels).tolist()) != values:
            raise ValueError(f"{section}: labels {np.unique(labels)} differ from {values}")
        intensity = grid(x, y, data[key])
        top, bottom = axes[0, column], axes[1, column]
        top.imshow(intensity, cmap="magma", vmin=np.nanpercentile(intensity, 1),
                   vmax=np.nanpercentile(intensity, 99), interpolation="nearest")
        top.set_title(f"{collection} ({section.replace('RCC_', '')})", fontsize=7)
        top.text(0.0, -0.04, measure, transform=top.transAxes, ha="left", va="top",
                 fontsize=6, color="#444444")
        bottom.imshow(grid(x, y, np.searchsorted(values, labels)),
                      cmap=ListedColormap([classes[v][1] for v in values]),
                      vmin=-0.5, vmax=len(values) - 0.5, interpolation="nearest")
        bottom.legend(handles=[Patch(color=classes[v][1], label=classes[v][0]) for v in values],
                      loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False,
                      fontsize=5.5, handlelength=1.0, borderaxespad=0)
        for axis in (top, bottom):
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_visible(False)
    fig.savefig(OUTPUT, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

"""Build images/dataset_overview.pdf: one representative section per collection
(GBM22_2, 160TopL, RCC_MH0204_33; supervisor chat 2026-10-30 12:58 item 4).
Top row: total ion current per measured pixel. Bottom row: expert annotation.
Unmeasured grid positions are blank; RCC unannotated pixels are grey.

Source: code/msi/results/diagnostics/dataset_figure_20261030/<section>.npz (x, y,
tic, labels), read on the cluster from the HDF5 inputs with the committed
read_h5_metadata and pulled. Run: python report/draft/figures/dataset_overview.py
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
DATA = ROOT / "code" / "msi" / "results" / "diagnostics" / "dataset_figure_20261030"
OUTPUT = ROOT / "report" / "draft" / "images" / "dataset_overview.pdf"
# Okabe-Ito colours (colour-blind safe); grey for the RCC unannotated class.
PANELS = (
    ("GBM22_2", "GBM (GBM22\\_2)", {1: ("normal", "#0072B2"), 2: ("tumour", "#E69F00")}),
    ("160TopL", "CAC (160TopL)", None),
    ("RCC_MH0204_33", "RCC (MH0204\\_33)", {0: ("cancer", "#E69F00"), 1: ("normal", "#0072B2"),
                                           2: ("unannotated", "#BBBBBB")}),
)
CAC_COLOURS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")
plt.rcParams.update({"font.size": 7, "font.family": "DejaVu Sans", "savefig.dpi": 300})


def grid(x, y, values):
    """Place per-pixel values on the measured grid; unmeasured positions stay NaN."""
    x, y = x - x.min(), y - y.min()
    image = np.full((y.max() + 1, x.max() + 1), np.nan)
    image[y, x] = values
    return image


def main():
    record = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    fig, axes = plt.subplots(2, 3, figsize=(7.0, 2.6),
                             gridspec_kw={"hspace": 0.12, "wspace": 0.55})
    for column, (section, title, classes) in enumerate(PANELS):
        data = np.load(DATA / f"{section}.npz")
        x, y = data["x"].astype(int), data["y"].astype(int)
        labels = data["labels"].astype(int)
        tic = grid(x, y, data["tic"])
        top = axes[0, column]
        top.imshow(tic, cmap="magma", vmin=np.nanpercentile(tic, 1),
                   vmax=np.nanpercentile(tic, 99), interpolation="nearest")
        top.set_title(title.replace("\\_", "_"), fontsize=7)
        if classes is None:   # CAC: numeric classes as released (names not documented)
            classes = {int(v): (f"class {int(v)}", CAC_COLOURS[i])
                       for i, v in enumerate(sorted(np.unique(labels)))}
        values = sorted(classes)
        if sorted(np.unique(labels).tolist()) != values:
            raise ValueError(f"{section}: labels {np.unique(labels)} differ from {values}")
        index = np.searchsorted(values, labels)
        mask = grid(x, y, index)
        bottom = axes[1, column]
        bottom.imshow(mask, cmap=ListedColormap([classes[v][1] for v in values]),
                      vmin=-0.5, vmax=len(values) - 0.5, interpolation="nearest")
        bottom.legend(handles=[Patch(color=classes[v][1], label=classes[v][0]) for v in values],
                      loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False,
                      fontsize=5.5, handlelength=1.0, borderaxespad=0)
        for axis in (top, bottom):
            axis.set_xticks([])
            axis.set_yticks([])
            for spine in axis.spines.values():
                spine.set_visible(False)
        if record[section]["pixels"] != len(labels):
            raise ValueError(f"{section}: pixel count differs from the job summary")
    fig.savefig(OUTPUT, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()

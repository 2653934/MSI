"""Planning aid (Zayd 2026-10-31): TIC and annotation side by side for all 24 sections,
one page per collection, so a representative section per dataset can be picked.
Writes report/draft/planning/dataset_contact_sheet.pdf (a GBM base-peak page follows the GBM TIC page,
since the GBM HDF5 is TIC-normalised; job 79303); also prints mean TIC per class
(the CAC class evidence). Source: code/msi/results/diagnostics/dataset_contact_20261031/
<section>.npz (x, y, tic, labels), read on the cluster with the committed
read_h5_metadata (job 79301) and pulled. Labels are shown as numeric codes, as stored.
Run: python report/draft/figures/dataset_contact_sheet.py
"""

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "code" / "msi" / "results" / "diagnostics" / "dataset_contact_20261031"
BASE_PEAK = ROOT / "code" / "msi" / "results" / "diagnostics" / "dataset_basepeak_gbm_20261031"
OUTPUT = ROOT / "report" / "draft" / "planning" / "dataset_contact_sheet.pdf"
COLLECTIONS = {
    "GBM": ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2", "GBM22_1",
            "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
COLOURS = ("#0072B2", "#E69F00", "#009E73", "#CC79A7")   # Okabe-Ito, by sorted label code
plt.rcParams.update({"font.size": 7, "font.family": "DejaVu Sans"})


def grid(x, y, values):
    x, y = x - x.min(), y - y.min()
    image = np.full((y.max() + 1, x.max() + 1), np.nan)
    image[y, x] = values
    return image


def border_fraction(x, y, mask):
    edge = (x == x.min()) | (x == x.max()) | (y == y.min()) | (y == y.max())
    return float(np.mean(edge[mask]))


def main():
    record = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    class_stats = {}
    # Pages: (title, sections, folder, intensity key). GBM base peak (job 79303) follows the
    # GBM TIC page because the GBM HDF5 spectra are TIC-normalised.
    pages = [("GBM", COLLECTIONS["GBM"], DATA, "tic"),
             ("GBM base-peak intensity", COLLECTIONS["GBM"], BASE_PEAK, "base_peak"),
             ("CAC", COLLECTIONS["CAC"], DATA, "tic"),
             ("RCC", COLLECTIONS["RCC"], DATA, "tic")]
    base_record = json.loads((BASE_PEAK / "summary.json").read_text(encoding="utf-8"))
    with PdfPages(OUTPUT) as pdf:
        for collection, sections, folder, key in pages:
            fig, axes = plt.subplots(4, 4, figsize=(8.27, 11.0))
            note = ("\nGBM HDF5 spectra are already TIC-normalised: TIC = 1 in every pixel, "
                    "so the left images show rounding noise only" if collection == "GBM" else "")
            what = "base-peak intensity (max over m/z)" if key == "base_peak" else "TIC"
            fig.suptitle(f"{collection}: {what} (left) and annotation (right) per section;\n"
                         f"labels are the stored numeric codes{note}", fontsize=9)
            for index, section in enumerate(sections):
                data = np.load(folder / f"{section}.npz")
                x, y = data["x"].astype(int), data["y"].astype(int)
                tic, labels = data[key], data["labels"].astype(int)
                if (base_record if key == "base_peak" else record)[section]["pixels"] != len(labels):
                    raise ValueError(f"{section}: pixel count differs from the job summary")
                codes = sorted(np.unique(labels).tolist())
                image = grid(x, y, tic)
                left, right = axes[index // 2, 2 * (index % 2)], axes[index // 2, 2 * (index % 2) + 1]
                left.imshow(image, cmap="magma", vmin=np.nanpercentile(image, 1),
                            vmax=np.nanpercentile(image, 99), interpolation="nearest")
                right.imshow(grid(x, y, np.searchsorted(codes, labels)),
                             cmap=ListedColormap(COLOURS[:len(codes)]), vmin=-0.5,
                             vmax=len(codes) - 0.5, interpolation="nearest")
                left.set_title(section, fontsize=7, loc="left")
                stats = {}
                for code in codes:
                    member = labels == code
                    stats[code] = {"pixels": int(member.sum()),
                                   "mean_tic": float(tic[member].mean()),
                                   "median_tic": float(np.median(tic[member])),
                                   "border_fraction": border_fraction(x, y, member)}
                if key == "tic":
                    class_stats[section] = stats
                measure = "base peak" if key == "base_peak" else "TIC"
                right.legend(handles=[Patch(color=COLOURS[i], label=(
                    f"{code}: {stats[code]['pixels']} px, {measure} {stats[code]['mean_tic']:.3g}"))
                    for i, code in enumerate(codes)], loc="upper center",
                    bbox_to_anchor=(0.5, -0.02), frameon=False, fontsize=5, ncol=1)
                for axis in (left, right):
                    axis.set_xticks([])
                    axis.set_yticks([])
            fig.tight_layout(rect=(0, 0, 1, 0.97))
            pdf.savefig(fig)
            plt.close(fig)
    (DATA.parent / "dataset_contact_20261031_class_stats.json").write_text(
        json.dumps(class_stats, indent=2) + "\n", encoding="utf-8")
    for section, stats in class_stats.items():
        print(section, {c: (s["pixels"], round(s["mean_tic"], 3), round(s["border_fraction"], 2))
                        for c, s in stats.items()})


if __name__ == "__main__":
    main()

"""Build three report figures from committed, locally saved results only
(supervisor chat 2026-10-30 20:16 and 20:20: seed-averaged where three seeds exist).

1. images/05_ig_minus_correlation_by_section.png: IG minus posterior-|PCC| per section
   and arm, mean of the three training seeds, bin level at K_bin. Source:
   test_r/decisions_20261030_ig_steps_local/section_table.csv (IG-steps reruns included).
2. images/17_all_neighbourhood_variants.png: collection mean IG and posterior-|PCC|
   per neighbourhood variant (GBM, CAC). Centre-only and uniform 3x3: mean of three
   seeds (same source as 1); other variants exist for seed 1 only (open markers):
   extra_arms/decisions_20261016_local/section_table.csv.
3. images/vae_vs_pca.png: per section, VAE posterior-|PCC| averaged over three seeds
   minus PCA-5 posterior-|PCC| (same GMM K and ranking), bin level. Source:
   segmentation_control_V/decisions_20261030_with_test_r_ig_steps_local; the values
   are checked against its decisions.json (1e-12).

The file names are the ones the report already includes; the images/ folder comes
first on its graphicspath. Run: python report/draft/figures/seed_averaged_figures.py
"""

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
IMAGES = ROOT / "report" / "draft" / "images"
DIAG = ROOT / "code" / "msi" / "results" / "diagnostics"
FSB = DIAG / "fair_scoring_baselines"
TEST_R = FSB / "test_r" / "decisions_20261030_ig_steps_local" / "section_table.csv"
EXTRA = FSB / "extra_arms" / "decisions_20261016_local" / "section_table.csv"
TEST_V = DIAG / "segmentation_control_V" / "decisions_20261030_with_test_r_ig_steps_local"
SECTIONS = {
    "GBM": ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2", "GBM22_1",
            "GBM22_2", "GBM39_1", "GBM39_2"),
    "CAC": ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"),
    "RCC": ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"),
}
CENTRE, UNIFORM = "#8a8a85", "#2a78d6"
IG_COLOUR, CORR_COLOUR = "#2a78d6", "#e8692f"
COLLECTION_COLOURS = {"GBM": "#2a78d6", "CAC": "#e8692f", "RCC": "#1aa37a"}
plt.rcParams.update({"font.size": 7, "axes.spines.top": False, "axes.spines.right": False,
                     "savefig.dpi": 300, "font.family": "DejaVu Sans"})


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def seed_mean_rows():
    """{(collection, section, arm): (IG seed mean, posterior seed mean)}, bin level."""
    values = {}
    for row in read_csv(TEST_R):
        if row["scale"] == "bin":
            key = (row["collection"], row["section"], row["arm"])
            values.setdefault(key, []).append((float(row["ig_mSCF1"]),
                                               float(row["posterior_mSCF1"])))
    if any(len(v) != 3 for v in values.values()) or len(values) != 48:
        raise ValueError("expected 48 section-arms with three seeds each")
    return {k: tuple(np.mean(v, axis=0)) for k, v in values.items()}


def label(section):
    return section.replace("RCC_", "")


def ig_minus_correlation(seed_means):
    fig, ax = plt.subplots(figsize=(3.4, 4.6))
    y, ticks, labels, separators = 0.0, [], [], []
    for collection in ("GBM", "CAC", "RCC"):
        for section in SECTIONS[collection]:
            for offset, arm, colour in ((-0.19, "central_only", CENTRE),
                                        (0.19, "uniform_mean", UNIFORM)):
                ig, corr = seed_means[(collection, section, arm)]
                ax.barh(y + offset, ig - corr, height=0.36, color=colour, linewidth=0)
            ticks.append(y)
            labels.append(label(section))
            y += 1
        separators.append((y - 0.5, collection, y - 4.5))
        y += 0.6
    for boundary, collection, middle in separators:
        ax.text(-0.355, middle, collection, rotation=90, va="center", ha="center",
                fontsize=7, fontweight="bold")
        if collection != "RCC":
            ax.axhline(boundary + 0.3, color="#bbbbbb", linewidth=0.5)
    ax.axvline(0, color="black", linewidth=0.6)
    ax.set_yticks(ticks, labels, fontsize=6)
    ax.invert_yaxis()
    ax.set_xlim(-0.37, 0.03)
    ax.set_xticks([-0.3, -0.2, -0.1, 0.0])
    ax.set_xlabel("IG minus posterior correlation (mSCF1)")
    ax.grid(axis="x", color="#e5e5e5", linewidth=0.5)
    ax.set_axisbelow(True)
    handles = [plt.Rectangle((0, 0), 1, 1, color=CENTRE), plt.Rectangle((0, 0), 1, 1, color=UNIFORM)]
    fig.legend(handles, ["Centre-only VAE", "Uniform-context VAE"], loc="lower center",
               ncol=2, frameon=False, fontsize=6)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(IMAGES / "05_ig_minus_correlation_by_section.png")
    plt.close(fig)


VARIANTS = (("Centre only", "central_only"), ("Uniform 3x3", "uniform_mean"),
            ("Uniform 5x5", "uniform_p5"), ("Uniform 7x7", "uniform_p7"),
            ("Uniform 9x9", "uniform_p9"), ("Attention 3x3", "attention"),
            ("Attention + centre masking", "attention_centremask_p50"),
            ("Uniform + centre masking", "uniform_centremask_p50"))


def neighbourhood_variants(seed_means):
    extra = {}
    for row in read_csv(EXTRA):
        extra.setdefault((row["collection"], row["arm"]), {})[row["section"]] = (
            float(row["bin:integrated_gradients"]), float(row["bin:posterior_abs_pcc_balanced"]))
    fig, axes = plt.subplots(1, 2, figsize=(3.4, 2.5), sharey=True)
    for ax, collection in zip(axes, ("GBM", "CAC")):
        for position, (name, arm) in enumerate(VARIANTS):
            if arm in ("central_only", "uniform_mean"):
                pairs = [seed_means[(collection, s, arm)] for s in SECTIONS[collection]]
                filled = True
            else:
                per_section = extra[(collection, arm)]
                if sorted(per_section) != sorted(SECTIONS[collection]):
                    raise ValueError(f"{collection}/{arm}: sections incomplete")
                pairs = list(per_section.values())
                filled = False
            ig, corr = np.mean(pairs, axis=0)
            ax.plot([ig, corr], [position, position], color="#dddddd", linewidth=2.5,
                    zorder=1, solid_capstyle="round")
            for value, colour in ((ig, IG_COLOUR), (corr, CORR_COLOUR)):
                ax.scatter(value, position, s=16, zorder=2, linewidths=0.9,
                           color=colour if filled else "white", edgecolors=colour)
        ax.set_title(f"{collection} (8 sections)", fontsize=7)
        ax.set_xlim(0.4, 0.82)
        ax.grid(axis="x", color="#e5e5e5", linewidth=0.5)
        ax.set_axisbelow(True)
        ax.set_xticks([0.4, 0.5, 0.6, 0.7, 0.8])
    axes[0].set_yticks(range(len(VARIANTS)), [name for name, _ in VARIANTS], fontsize=6)
    axes[0].invert_yaxis()
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=IG_COLOUR, markersize=4),
               plt.Line2D([], [], marker="o", linestyle="", color=CORR_COLOUR, markersize=4),
               plt.Line2D([], [], marker="o", linestyle="", color="#777777", markersize=4,
                          markerfacecolor="white")]
    fig.legend(handles, ["IG", "Posterior correlation", "One training seed (others: 3)"],
               loc="lower center", ncol=3, frameon=False, fontsize=5.5,
               bbox_to_anchor=(0.55, -0.01))
    fig.supxlabel("Collection mean mSCF1 (bin level)", fontsize=7, y=0.09)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(IMAGES / "17_all_neighbourhood_variants.png")
    plt.close(fig)


def vae_vs_pca():
    rows = read_csv(TEST_V / "section_table.csv")
    decisions = json.loads((TEST_V / "decisions.json").read_text(encoding="utf-8"))
    fig, ax = plt.subplots(figsize=(3.4, 1.8))
    rng = np.random.default_rng(0)
    for position, collection in enumerate(("GBM", "CAC", "RCC")):
        values = [float(r["bin:vae_seed_mean_1_3"]) - float(r["bin:pca5_posterior_abs_pcc_balanced"])
                  for r in rows if r["collection"] == collection]
        saved = decisions[collection]["descriptive"]["d_vae_seed_mean_minus_pca5"]["bin"]["per_section"]
        if len(values) != 8 or not np.allclose(sorted(values), sorted(saved), atol=1e-12, rtol=0):
            raise ValueError(f"{collection}: seed-mean differences do not reproduce decisions.json")
        colour = COLLECTION_COLOURS[collection]
        ax.scatter(values, position + rng.uniform(-0.13, 0.13, len(values)), s=12,
                   color=colour, edgecolors="white", linewidths=0.4, zorder=2)
        mean = float(np.mean(values))
        ax.plot([mean, mean], [position - 0.28, position + 0.28], color=colour, linewidth=1.6,
                zorder=3)
        positive = sum(v > 0 for v in values)
        ax.text(0.43, position, f"{mean:+.3f} ({positive}/8)", va="center", fontsize=6.5)
    ax.axvline(0, color="#888888", linewidth=0.6)
    ax.set_yticks(range(3), ["GBM", "CAC", "RCC"])
    ax.invert_yaxis()
    ax.set_xlim(-0.32, 0.42)
    ax.set_xlabel("VAE (mean of 3 seeds) minus PCA-5, posterior-correlation mSCF1")
    ax.grid(axis="x", color="#e5e5e5", linewidth=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(IMAGES / "vae_vs_pca.png", bbox_inches="tight")
    plt.close(fig)


def main():
    seed_means = seed_mean_rows()
    ig_minus_correlation(seed_means)
    neighbourhood_variants(seed_means)
    vae_vs_pca()


if __name__ == "__main__":
    main()

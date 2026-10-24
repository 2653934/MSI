"""Investigation 21 figure: per-section S3PL mSCF1 over released seeds 1-10.

Reads the saved Part B and Part A (released) section tables, checks that they
agree, and plots GBM and CAC as two panels with the published per-section values
marked. Scores are S3PL's in-job mSCF1, not the fair-scoring evaluator.
"""

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SEED_COLOUR = "#2a78d6"
PUBLISHED_COLOUR = "#eb6834"
INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"


def load(root):
    part_b = pd.read_csv(root / "part_b" / "sections.csv")
    part_a = pd.read_csv(root / "part_a_released" / "sections.csv")
    merged = part_b.merge(part_a, on=["collection", "section"], suffixes=("", "_a"))
    if len(merged) != len(part_b) or len(part_b) != 16:
        raise SystemExit("Part B and Part A (released) do not cover the same 16 sections")
    for _, row in merged.iterrows():
        scores = np.array(json.loads(row["seed_scores"]))
        sorted_a = np.array(json.loads(row["sorted_scores"]))
        if len(scores) != 10 or not np.allclose(np.sort(scores), sorted_a, atol=1e-6):
            raise SystemExit(f"seed scores disagree for {row['section']}")
        if not np.isclose(scores.mean(), row["mean"]):
            raise SystemExit(f"mean disagrees for {row['section']}")
    return part_b


def panel(ax, frame, title):
    frame = frame.sort_values("section", key=lambda s: s.map(_section_key)).reset_index(drop=True)
    rng = np.random.default_rng(21)
    for i, row in frame.iterrows():
        scores = np.array(json.loads(row["seed_scores"]))
        x = i + rng.uniform(-0.16, 0.16, size=scores.size)
        ax.scatter(x, scores, s=22, color=SEED_COLOUR, alpha=0.8, linewidths=0.6,
                   edgecolors="#fcfcfb", zorder=3)
        ax.plot([i - 0.28, i + 0.28], [scores.mean()] * 2, color=SEED_COLOUR, lw=2,
                solid_capstyle="round", zorder=4)
        ax.scatter([i], [row["published"]], marker="D", s=70, facecolors="none",
                   edgecolors=PUBLISHED_COLOUR, linewidths=2, zorder=5)
    ax.set_xticks(range(len(frame)))
    ax.set_xticklabels(frame["section"], rotation=35, ha="right", fontsize=8, color=MUTED)
    ax.set_title(title, loc="left", fontsize=10, color=INK)
    ax.set_ylim(0, 0.85)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="y", labelsize=8, colors=MUTED, length=0)
    ax.tick_params(axis="x", length=0)


# Same section order as the other publication figures (audit_spatial_publication_aggregate.py).
ORDER = ["GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2", "GBM22_1", "GBM22_2",
         "GBM39_1", "GBM39_2", "40TopL", "160TopL", "200TopL", "240TopL", "280TopL",
         "360TopL", "400TopL", "520TopL"]


def _section_key(name):
    return ORDER.index(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path("results/diagnostics/s3pl_seed_investigation_21"))
    parser.add_argument("--out", type=Path, required=True,
                        help="output path without extension; .png and .pdf are written")
    args = parser.parse_args()

    sections = load(args.root)
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8), sharey=True, constrained_layout=True)
    for ax, collection in zip(axes, ["GBM", "CAC"]):
        frame = sections[sections["collection"] == collection]
        means = np.array([json.loads(s) for s in frame["seed_scores"]]).mean(axis=0)
        panel(ax, frame, f"{collection}: seed-level mean {means.mean():.3f} ± {means.std(ddof=1):.3f}; "
                         f"published {frame['published'].mean():.3f}")
    axes[0].set_ylabel("S3PL mSCF1 (in-job evaluator)", fontsize=9, color=MUTED)
    handles = [
        plt.Line2D([], [], marker="o", ls="", color=SEED_COLOUR, label="Released seed (1–10)"),
        plt.Line2D([], [], color=SEED_COLOUR, lw=2, label="Mean of 10 seeds"),
        plt.Line2D([], [], marker="D", ls="", markerfacecolor="none", markeredgecolor=PUBLISHED_COLOUR,
                   markeredgewidth=2, label="Published value"),
    ]
    axes[1].legend(handles=handles, loc="lower right", fontsize=8, frameon=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(args.out.with_suffix(f".{ext}"), dpi=200)


if __name__ == "__main__":
    main()

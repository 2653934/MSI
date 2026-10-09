#!/usr/bin/env python3
"""Build patient-grouped GBM report artifacts from the audited section table."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "code/msi/results/publication/current_evidence/section_level_results.csv"
OUTPUT_ROOT = ROOT / "results/report"
REPORT_IMAGE = ROOT / "report/draft/images/gbm_patient_grouped_effects.png"
REPORT_TABLE = ROOT / "report/draft/tables/gbm_patient_summary.tex"

PATIENT_ORDER = ("108", "12", "22", "39")
SECTION_PATIENT = {
    "GBM108_positive": "108",
    "GBM108_negative": "108",
    "GBM12_1": "12",
    "GBM12_2": "12",
    "GBM22_1": "22",
    "GBM22_2": "22",
    "GBM39_1": "39",
    "GBM39_2": "39",
}
METHODS = (
    ("legacy_msipl", "Legacy msiPL"),
    ("central_ig", "Centre-only IG"),
    ("spatial_ig", "Uniform-context IG"),
)


def read_sections() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    with SOURCE.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            if raw["collection"] != "GBM":
                continue
            section = raw["section"]
            if section not in SECTION_PATIENT:
                raise ValueError(f"Unmapped GBM section: {section}")
            row: dict[str, object] = {
                "patient": SECTION_PATIENT[section],
                "section": section,
                "matched_peaks": int(raw["matched_peaks"]),
            }
            for key, _ in METHODS:
                row[key] = float(raw[key])
            row["context_delta"] = float(raw["context_delta"])
            rows.append(row)
    if set(row["section"] for row in rows) != set(SECTION_PATIENT):
        raise ValueError("The authoritative table does not contain exactly the expected GBM sections")
    return rows


def patient_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["patient"])].append(row)

    summaries: list[dict[str, object]] = []
    for patient in PATIENT_ORDER:
        sections = grouped[patient]
        if len(sections) != 2:
            raise ValueError(f"Expected two sections for patient {patient}, found {len(sections)}")
        summary: dict[str, object] = {
            "patient": patient,
            "sections": ";".join(str(row["section"]) for row in sections),
            "section_count": len(sections),
        }
        for key, _ in METHODS:
            summary[f"mean_{key}"] = float(np.mean([float(row[key]) for row in sections]))
        summary["mean_context_delta"] = float(
            np.mean([float(row["context_delta"]) for row in sections])
        )
        summaries.append(summary)
    return summaries


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_latex(path: Path, summaries: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{GBM mSCF1 averaged within each patient. Each patient contributes two tissue sections. With only four patient groups, these summaries are descriptive and no formal significance test is reported.}",
        r"\label{tab:gbm_patient_summary}",
        r"\small",
        r"\begin{tabular}{@{}lrrrr@{}}",
        r"\toprule",
        r"Patient & Legacy & Centre IG & Context IG & $\Delta$ context \\",
        r"\midrule",
    ]
    for row in summaries:
        lines.append(
            f"{row['patient']} & {row['mean_legacy_msipl']:.3f} & "
            f"{row['mean_central_ig']:.3f} & {row['mean_spatial_ig']:.3f} & "
            f"{row['mean_context_delta']:+.3f} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def plot(rows: list[dict[str, object]], summaries: list[dict[str, object]]) -> None:
    REPORT_IMAGE.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.8))

    patient_colours = dict(zip(PATIENT_ORDER, ("#4c78a8", "#59a14f", "#f28e2b", "#e15759")))
    ordered = sorted(rows, key=lambda row: (PATIENT_ORDER.index(str(row["patient"])), str(row["section"])))
    x = np.arange(len(ordered))
    for index, row in enumerate(ordered):
        colour = patient_colours[str(row["patient"])]
        centre = float(row["central_ig"])
        context = float(row["spatial_ig"])
        axes[0].plot([index - 0.12, index + 0.12], [centre, context], color=colour, linewidth=1.8)
        axes[0].scatter(index - 0.12, centre, color="white", edgecolor=colour, s=48, linewidth=1.5, zorder=3)
        axes[0].scatter(index + 0.12, context, color=colour, edgecolor="black", s=48, linewidth=0.5, zorder=3)
    axes[0].set_xticks(x, [str(row["section"]).replace("GBM", "") for row in ordered], rotation=32, ha="right")
    axes[0].set_ylabel("mSCF1")
    axes[0].set_title("Section-level paired comparison")
    axes[0].grid(axis="y", alpha=0.25)
    axes[0].plot([], [], marker="o", markerfacecolor="white", markeredgecolor="black", linestyle="", label="Centre-only IG")
    axes[0].plot([], [], marker="o", markerfacecolor="black", markeredgecolor="black", linestyle="", label="Uniform-context IG")
    axes[0].legend(frameon=False, fontsize=9)

    deltas = np.asarray([float(row["mean_context_delta"]) for row in summaries])
    colours = [patient_colours[str(row["patient"])] for row in summaries]
    axes[1].axhline(0, color="black", linewidth=1)
    axes[1].bar(np.arange(len(summaries)), deltas, color=colours, edgecolor="black", linewidth=0.6)
    axes[1].set_xticks(np.arange(len(summaries)), [f"Patient {row['patient']}" for row in summaries])
    axes[1].set_ylabel("Mean context $-$ centre mSCF1")
    axes[1].set_title("Within-patient mean context effect")
    axes[1].grid(axis="y", alpha=0.25)
    for index, value in enumerate(deltas):
        label_y = value + 0.0015 if value >= 0 else -0.0015
        axes[1].text(
            index,
            label_y,
            f"{value:+.3f}",
            ha="center",
            va="bottom" if value >= 0 else "top",
            fontsize=9,
        )

    fig.suptitle("GBM context effects grouped within four patients")
    fig.tight_layout()
    fig.savefig(REPORT_IMAGE, dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    rows = read_sections()
    summaries = patient_summary(rows)
    write_csv(OUTPUT_ROOT / "gbm_patient_section_results.csv", rows)
    write_csv(OUTPUT_ROOT / "gbm_patient_summary.csv", summaries)
    write_latex(REPORT_TABLE, summaries)
    plot(rows, summaries)
    print(f"Saved {len(rows)} sections and {len(summaries)} patient summaries")
    for row in summaries:
        print(
            f"patient {row['patient']}: centre={row['mean_central_ig']:.4f}, "
            f"context={row['mean_spatial_ig']:.4f}, delta={row['mean_context_delta']:+.4f}"
        )


if __name__ == "__main__":
    main()

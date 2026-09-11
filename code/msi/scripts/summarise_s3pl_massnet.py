#!/usr/bin/env python3
"""Aggregate an eight-section MassNet GBM S3PL experiment."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


DATASETS = (
    "GBM108_positive",
    "GBM108_negative",
    "GBM12_1",
    "GBM12_2",
    "GBM22_1",
    "GBM22_2",
    "GBM39_1",
    "GBM39_2",
)
THRESHOLDS = ("0.3", "0.4", "0.5", "0.6")
TRAINING_SUFFIX = "Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_{patch_size}"
ISSUE_PATTERN = re.compile(
    r"traceback|cuda out of memory|out of memory|\bnan\b|\binf\b|error|warning",
    re.IGNORECASE,
)

INK = "#25313c"
BLUE = "#356d8a"
LIGHT_BLUE = "#8eb6c9"
ORANGE = "#c7772b"
GRID = "#d9dee2"


def parse_args() -> argparse.Namespace:
    project_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=project_root)
    parser.add_argument(
        "--patch-size",
        type=int,
        default=9,
        help="Odd spatial patch width used by the experiment (default: 9)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Defaults to massnet_gbm_summary for p=9 or massnet_gbm_summary_pN otherwise",
    )
    args = parser.parse_args()
    if args.patch_size <= 0 or args.patch_size % 2 == 0:
        parser.error("--patch-size must be a positive odd integer")
    return args


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def find_job(project_root: Path, training_name: str) -> tuple[str | None, int | None, int]:
    for path in sorted((project_root / "logs").glob("s3pl-gbm-*.out")):
        text = path.read_text(encoding="utf-8", errors="replace")
        if training_name not in text:
            continue
        job_match = re.search(r"s3pl-gbm-(\d+)\.out$", path.name)
        candidate_match = re.search(
            r"length of peak selection before cut-off = (\d+)", text
        )
        issue_count = len(ISSUE_PATTERN.findall(text))
        error_path = path.with_suffix(".err")
        if error_path.is_file():
            issue_count += len(
                ISSUE_PATTERN.findall(
                    error_path.read_text(encoding="utf-8", errors="replace")
                )
            )
        return (
            job_match.group(1) if job_match else None,
            int(candidate_match.group(1)) if candidate_match else None,
            issue_count,
        )
    return None, None, 0


def load_rows(project_root: Path, patch_size: int) -> list[dict]:
    result_root = project_root / "results" / "baselines" / "s3pl"
    visual_root = project_root / "results" / "visualisations" / "gbm_massnet"
    config_root = project_root / "logs" / "s3pl"
    rows = []
    training_suffix = TRAINING_SUFFIX.format(patch_size=patch_size)

    for dataset in DATASETS:
        training_name = f"{dataset}_{training_suffix}"
        result_dir = result_root / training_name
        metrics = read_json(result_dir / "metrics.json")
        runtime = read_json(result_dir / "runtime_metrics.json")
        config = read_json(config_root / f"{training_name}.json")
        section = read_json(visual_root / dataset / "summary.json")
        job_id, candidates, issue_count = find_job(project_root, training_name)

        mixed = [float(metrics["mixed_f1"][threshold]) for threshold in THRESHOLDS]
        reported_mscf1 = float(metrics["mSCF1"])
        recomputed_mscf1 = float(np.mean(mixed))
        if abs(reported_mscf1 - recomputed_mscf1) > 0.00051:
            raise ValueError(
                f"{dataset}: reported mSCF1 {reported_mscf1} does not match "
                f"threshold mean {recomputed_mscf1}"
            )

        normal = int(section["class_counts"]["normal"])
        tumour = int(section["class_counts"]["tumour"])
        measured = int(section["measured_pixels"])
        if normal + tumour != measured:
            raise ValueError(f"{dataset}: class counts do not sum to measured pixels")

        history = np.asarray(config["train_history"], dtype=float)
        if history.size != 10 or not np.all(np.isfinite(history)):
            raise ValueError(f"{dataset}: invalid ten-epoch training history")

        row = {
            "dataset": dataset,
            "job_id": job_id,
            "measured_pixels": measured,
            "coverage_percent": float(section["coverage_percent"]),
            "normal_pixels": normal,
            "tumour_pixels": tumour,
            "tumour_fraction": tumour / measured,
            "candidate_peaks": candidates,
            "picked_peaks": int(metrics["number_picked_peaks"]),
            "f1_0.3": mixed[0],
            "f1_0.4": mixed[1],
            "f1_0.5": mixed[2],
            "f1_0.6": mixed[3],
            "mscf1": reported_mscf1,
            "mscf1_unrounded": recomputed_mscf1,
            "normal_f1_0.3": float(metrics["class_metrics"]["0.3"]["class 0"]["F1"]),
            "tumour_f1_0.3": float(metrics["class_metrics"]["0.3"]["class 1"]["F1"]),
            "training_minutes": float(runtime["training_seconds"]) / 60,
            "evaluation_minutes": float(runtime["evaluation_seconds"]) / 60,
            "total_minutes": float(runtime["total_seconds"]) / 60,
            "peak_gpu_memory_gib": float(runtime["peak_gpu_memory_bytes"]) / 2**30,
            "loss_start": float(history[0]),
            "loss_end": float(history[-1]),
            "loss_reduction_percent": float(100 * (1 - history[-1] / history[0])),
            "log_issue_count": issue_count,
            "train_history": history.tolist(),
        }
        rows.append(row)
    return rows


def correlation(rows: list[dict], x_key: str, y_key: str = "mscf1") -> float:
    x = np.asarray([row[x_key] for row in rows], dtype=float)
    y = np.asarray([row[y_key] for row in rows], dtype=float)
    return float(np.corrcoef(x, y)[0, 1])


def write_csv(rows: list[dict], path: Path) -> None:
    fieldnames = [key for key in rows[0] if key != "train_history"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({key: row[key] for key in fieldnames} for row in rows)


def build_summary(rows: list[dict], patch_size: int) -> dict:
    numeric_keys = (
        "measured_pixels",
        "coverage_percent",
        "tumour_fraction",
        "candidate_peaks",
        "picked_peaks",
        "f1_0.3",
        "f1_0.4",
        "f1_0.5",
        "f1_0.6",
        "mscf1",
        "normal_f1_0.3",
        "tumour_f1_0.3",
        "training_minutes",
        "evaluation_minutes",
        "total_minutes",
        "peak_gpu_memory_gib",
        "loss_reduction_percent",
    )
    aggregate = {}
    for key in numeric_keys:
        values = np.asarray([row[key] for row in rows], dtype=float)
        aggregate[key] = {
            "mean": float(np.mean(values)),
            "median": float(np.median(values)),
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
        }

    ranking = sorted(rows, key=lambda row: row["mscf1"], reverse=True)
    paper_aligned = patch_size == 3
    return {
        "dataset_collection": "MassNet GBM",
        "model": "S3PL Attention3DConvAutoencoder",
        "experiment_label": f"patch-size-{patch_size} " + (
            "paper-aligned reproduction" if paper_aligned else "transfer run"
        ),
        "paper_alignment": {
            "status": (
                "uses the paper-reported GBM spatial patch size"
                if paper_aligned
                else "not the paper-aligned GBM spatial patch size"
            ),
            "difference": (
                "This run uses p=3, matching the paper's reported GBM optimum."
                if paper_aligned
                else f"This run uses p={patch_size}; the paper reports p=3 for GBM."
            ),
            "paper_reported_gbm_means": {
                "f1_0.3": 0.564,
                "f1_0.4": 0.556,
                "f1_0.5": 0.488,
                "f1_0.6": 0.371,
                "mscf1": 0.496,
            },
        },
        "configuration": {
            "epochs": 10,
            "batch_size": 16,
            "spectral_patch_size": patch_size,
            "peaks_per_spectral_patch": 256,
            "learning_rate": 0.01,
            "random_seed": 1,
            "pcc_thresholds": [float(value) for value in THRESHOLDS],
        },
        "section_count": len(rows),
        "all_logs_clean": all(row["log_issue_count"] == 0 for row in rows),
        "aggregate": aggregate,
        "exploratory_correlations_with_mscf1": {
            "tumour_fraction": correlation(rows, "tumour_fraction"),
            "coverage_percent": correlation(rows, "coverage_percent"),
            "measured_pixels": correlation(rows, "measured_pixels"),
            "picked_peaks": correlation(rows, "picked_peaks"),
        },
        "ranking_by_mscf1": [
            {"dataset": row["dataset"], "mscf1": row["mscf1"]} for row in ranking
        ],
        "cautions": [
            "Eight sections are too few for causal inference from exploratory correlations.",
            "GBM108 positive and negative are distinct tissue sections and not a controlled polarity pair.",
            "Class imbalance and spatial morphology both affect mask-to-ion Pearson correlations.",
            "Section means are unweighted so that large sections do not dominate the collection summary.",
        ],
    }


def style_axis(axis: plt.Axes) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color=GRID, linewidth=0.7, alpha=0.75)
    axis.set_axisbelow(True)
    axis.tick_params(colors=INK, labelsize=8)
    axis.xaxis.label.set_color(INK)
    axis.yaxis.label.set_color(INK)
    axis.title.set_color(INK)


def save_figure(fig: plt.Figure, output_dir: Path, stem: str) -> None:
    fig.savefig(output_dir / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(output_dir / f"{stem}.svg", bbox_inches="tight")
    plt.close(fig)


def plot_performance(rows: list[dict], output_dir: Path, patch_size: int) -> None:
    labels = [row["dataset"] for row in rows]
    x = np.arange(len(rows))
    mean_mscf1 = np.mean([row["mscf1"] for row in rows])

    fig, axes = plt.subplots(2, 2, figsize=(13, 8.5), constrained_layout=True)
    fig.suptitle(f"S3PL MassNet GBM (spatial patch size p={patch_size})", fontsize=15, color=INK)

    lowest_dataset = min(rows, key=lambda row: row["mscf1"])["dataset"]
    colours = [ORANGE if row["dataset"] == lowest_dataset else BLUE for row in rows]
    axes[0, 0].bar(x, [row["mscf1"] for row in rows], color=colours, width=0.72)
    axes[0, 0].axhline(mean_mscf1, color=INK, linestyle="--", linewidth=1, label=f"Mean {mean_mscf1:.3f}")
    axes[0, 0].set_ylabel("mSCF1")
    axes[0, 0].set_title("A. Aggregate score")
    axes[0, 0].set_xticks(x, labels, rotation=35, ha="right")
    axes[0, 0].set_ylim(0, 0.7)
    axes[0, 0].legend(frameon=False, fontsize=8)
    style_axis(axes[0, 0])

    threshold_x = np.asarray([float(value) for value in THRESHOLDS])
    for row in rows:
        values = [row[f"f1_{threshold}"] for threshold in THRESHOLDS]
        highlight = row["dataset"] == lowest_dataset
        axes[0, 1].plot(
            threshold_x,
            values,
            marker="o",
            linewidth=2.2 if highlight else 1.2,
            color=ORANGE if highlight else BLUE,
            alpha=1 if highlight else 0.62,
            label=row["dataset"],
        )
    axes[0, 1].set_xlabel("PCC threshold")
    axes[0, 1].set_ylabel("Mixed-class F1")
    axes[0, 1].set_title("B. Sensitivity to the PCC definition")
    axes[0, 1].set_xticks(threshold_x)
    axes[0, 1].set_ylim(0, 0.7)
    axes[0, 1].legend(frameon=False, fontsize=6.8, ncol=2)
    style_axis(axes[0, 1])

    width = 0.36
    axes[1, 0].bar(x - width / 2, [row["normal_f1_0.3"] for row in rows], width, color=LIGHT_BLUE, label="Normal")
    axes[1, 0].bar(x + width / 2, [row["tumour_f1_0.3"] for row in rows], width, color=BLUE, label="Tumour")
    axes[1, 0].set_ylabel("Class-specific F1 at PCC 0.3")
    axes[1, 0].set_title("C. Class-specific behaviour")
    axes[1, 0].set_xticks(x, labels, rotation=35, ha="right")
    axes[1, 0].set_ylim(0, 0.7)
    axes[1, 0].legend(frameon=False, fontsize=8)
    style_axis(axes[1, 0])

    tumour_fraction = np.asarray([row["tumour_fraction"] * 100 for row in rows])
    mscf1 = np.asarray([row["mscf1"] for row in rows])
    axes[1, 1].scatter(tumour_fraction, mscf1, s=52, c=colours, edgecolor="white", linewidth=0.7, zorder=3)
    label_offsets = {"GBM12_2": (4, -11), "GBM22_2": (4, 5)}
    for row, x_value, y_value in zip(rows, tumour_fraction, mscf1):
        axes[1, 1].annotate(
            row["dataset"],
            (x_value, y_value),
            xytext=label_offsets.get(row["dataset"], (4, 4)),
            textcoords="offset points",
            fontsize=7,
            color=INK,
        )
    axes[1, 1].set_xlabel("Tumour pixels (% of measured pixels)")
    axes[1, 1].set_ylabel("mSCF1")
    axes[1, 1].set_title(f"D. Class balance (exploratory r = {correlation(rows, 'tumour_fraction'):.2f})")
    axes[1, 1].set_ylim(0, 0.7)
    style_axis(axes[1, 1])

    save_figure(fig, output_dir, "performance_overview")


def plot_runtime(rows: list[dict], output_dir: Path, patch_size: int) -> None:
    pixels = np.asarray([row["measured_pixels"] for row in rows], dtype=float)
    runtime = np.asarray([row["total_minutes"] for row in rows], dtype=float)

    fig, axes = plt.subplots(1, 2, figsize=(12.5, 4.6), constrained_layout=True)
    fig.suptitle(f"S3PL MassNet GBM p={patch_size} runtime and optimisation diagnostics", fontsize=15, color=INK)

    axes[0].scatter(pixels, runtime, s=55, color=BLUE, edgecolor="white", linewidth=0.7, zorder=3)
    slope, intercept = np.polyfit(pixels, runtime, 1)
    line_x = np.linspace(pixels.min(), pixels.max(), 100)
    axes[0].plot(line_x, slope * line_x + intercept, color=INK, linestyle="--", linewidth=1)
    for row in rows:
        axes[0].annotate(row["dataset"], (row["measured_pixels"], row["total_minutes"]), xytext=(4, 4), textcoords="offset points", fontsize=7, color=INK)
    axes[0].set_xlabel("Measured pixels")
    axes[0].set_ylabel("Instrumented total time (minutes)")
    axes[0].set_title(f"A. Runtime scaling (r = {float(np.corrcoef(pixels, runtime)[0, 1]):.2f})")
    style_axis(axes[0])

    epochs = np.arange(1, 11)
    lowest_dataset = min(rows, key=lambda row: row["mscf1"])["dataset"]
    for row in rows:
        highlight = row["dataset"] == lowest_dataset
        axes[1].plot(
            epochs,
            row["train_history"],
            marker="o",
            markersize=3,
            linewidth=2.2 if highlight else 1.2,
            color=ORANGE if highlight else BLUE,
            alpha=1 if highlight else 0.62,
            label=row["dataset"],
        )
    axes[1].set_xlabel("Epoch")
    axes[1].set_ylabel("Training loss")
    axes[1].set_title(f"B. Training histories; {lowest_dataset} highlighted")
    axes[1].set_xticks(epochs)
    axes[1].legend(frameon=False, fontsize=6.8, ncol=2)
    style_axis(axes[1])

    save_figure(fig, output_dir, "runtime_diagnostics")


def write_readme(rows: list[dict], summary: dict, path: Path, patch_size: int) -> None:
    ranking = sorted(rows, key=lambda row: row["mscf1"], reverse=True)
    lines = [
        f"# MassNet GBM S3PL patch-size-{patch_size} summary",
        "",
        "This directory is generated by `scripts/summarise_s3pl_massnet.py` from the committed section-level artifacts.",
        "",
        "## Collection result",
        "",
        f"- Sections: {len(rows)}",
        f"- Mean mSCF1: {summary['aggregate']['mscf1']['mean']:.3f}",
        f"- Median mSCF1: {summary['aggregate']['mscf1']['median']:.3f}",
        f"- Mean instrumented runtime: {summary['aggregate']['total_minutes']['mean']:.2f} minutes",
        f"- Logs free of detected warnings/errors: {summary['all_logs_clean']}",
        f"- Paper alignment: {summary['paper_alignment']['status']}.",
        "",
        "| Rank | Section | Picked peaks | F1@0.3 | F1@0.4 | F1@0.5 | F1@0.6 | mSCF1 | Total min |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for rank, row in enumerate(ranking, start=1):
        lines.append(
            f"| {rank} | `{row['dataset']}` | {row['picked_peaks']} | "
            f"{row['f1_0.3']:.3f} | {row['f1_0.4']:.3f} | {row['f1_0.5']:.3f} | "
            f"{row['f1_0.6']:.3f} | {row['mscf1']:.3f} | {row['total_minutes']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            f"`{ranking[-1]['dataset']}` is the lowest-scoring section in this run. Its artifacts and metrics are internally complete; score differences still require scientific interpretation rather than being treated as execution failures. With only eight sections, the reported correlations are descriptive and must not be interpreted causally.",
            "",
            "The collection mean is an unweighted mean over sections. Despite their filenames, `GBM108_positive` and `GBM108_negative` are not ionisation modes: the paper states that the GBM collection was acquired in positive-ion mode.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    args = parse_args()
    project_root = args.project_root.resolve()
    default_name = "massnet_gbm_summary" if args.patch_size == 9 else f"massnet_gbm_summary_p{args.patch_size}"
    output_dir = args.output_dir or (
        project_root / "results" / "baselines" / "s3pl" / default_name
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    rows = load_rows(project_root, args.patch_size)
    summary = build_summary(rows, args.patch_size)
    write_csv(rows, output_dir / "section_metrics.csv")
    (output_dir / "aggregate_metrics.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    plot_performance(rows, output_dir, args.patch_size)
    plot_runtime(rows, output_dir, args.patch_size)
    write_readme(rows, summary, output_dir / "README.md", args.patch_size)

    print(f"Validated {len(rows)} MassNet GBM S3PL sections")
    print(f"Mean mSCF1: {summary['aggregate']['mscf1']['mean']:.3f}")
    print(f"Outputs: {output_dir}")


if __name__ == "__main__":
    main()

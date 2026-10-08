#!/usr/bin/env python3
"""Summarise the frozen S3PL GBM seed screen and native CAC runtime repeats."""

from __future__ import annotations

import csv
import itertools
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


MSI_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = MSI_ROOT.parents[1]
OUTPUT = MSI_ROOT / "results/comparisons/s3pl_gbm_stability_runtime"
GALLERY = REPO_ROOT / "results/model-comparisons"
REPRO = MSI_ROOT / "reproducibility/s3pl_massnet"
RUNTIME_ROOT = MSI_ROOT / "results/validation/s3pl_vae_cac_runtime"

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
SEEDS = (1, 2, 3)
RUNTIME_JOBS = (65630, 65854, 65855)
STAGES = ("s3pl_full", "vae_train", "vae_attribution", "vae_peak_evaluation")


def read_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def find_one(root: Path, pattern: str) -> Path:
    matches = list(root.rglob(pattern))
    if len(matches) != 1:
        raise RuntimeError(f"Expected one {pattern!r} below {root}, found {len(matches)}")
    return matches[0]


def read_peak_set(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.reader(handle))
    return {row[0] for row in rows[1:] if row}


def seed_records() -> list[dict]:
    records = []
    for dataset in DATASETS:
        for seed in SEEDS:
            root = REPRO / f"{dataset}_p3_rng_init{seed}_order1"
            metrics_path = find_one(root / "results", "metrics.json")
            config_path = root / "logs/s3pl" / (
                f"{dataset}_Attention3DConvAutoencoder_10epochs_256_"
                "spectral_patch_size_3.json"
            )
            peaks_path = find_one(root / "results", "picked_peaks_*.csv")
            metrics = read_json(metrics_path)
            config = read_json(config_path)
            history = config["train_history"]
            if not (
                config["initialization_seed"] == seed
                and config["sample_order_seed"] == 1
                and config["n_epochs"] == 10
                and config["spectral_patch_size"] == 3
                and len(history) == 10
            ):
                raise RuntimeError(f"Protocol mismatch in {config_path}")
            peaks = read_peak_set(peaks_path)
            if len(peaks) != int(metrics["number_picked_peaks"]):
                raise RuntimeError(f"Peak count mismatch in {peaks_path}")
            records.append(
                {
                    "dataset": dataset,
                    "initialization_seed": seed,
                    "sample_order_seed": 1,
                    "epochs": 10,
                    "patch_size": 3,
                    "mSCF1": float(metrics["mSCF1"]),
                    "final_reconstruction_loss": float(history[-1]),
                    "selected_peak_count": len(peaks),
                    "peaks": peaks,
                    "metrics_path": metrics_path.relative_to(REPO_ROOT).as_posix(),
                }
            )
    if len(records) != 24:
        raise RuntimeError(f"Expected 24 seed records, found {len(records)}")
    return records


def section_summaries(records: list[dict]) -> list[dict]:
    summaries = []
    for dataset in DATASETS:
        rows = sorted(
            (row for row in records if row["dataset"] == dataset),
            key=lambda row: row["initialization_seed"],
        )
        scores = [row["mSCF1"] for row in rows]
        overlaps = {
            f"seed_{left['initialization_seed']}_vs_{right['initialization_seed']}": len(
                left["peaks"] & right["peaks"]
            )
            for left, right in itertools.combinations(rows, 2)
        }
        summaries.append(
            {
                "dataset": dataset,
                "seed_1_mSCF1": scores[0],
                "seed_2_mSCF1": scores[1],
                "seed_3_mSCF1": scores[2],
                "mean_mSCF1": statistics.mean(scores),
                "sample_sd_mSCF1": statistics.stdev(scores),
                "range_mSCF1": max(scores) - min(scores),
                "minimum_pairwise_peak_overlap": min(overlaps.values()),
                **overlaps,
            }
        )
    return summaries


def parse_resource_file(path: Path) -> dict[str, float]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        values[key] = float(value)
    return values


def max_gpu_memory(path: Path) -> float:
    values = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) >= 3:
                values.append(float(row[2].strip()))
    if not values:
        raise RuntimeError(f"No GPU samples in {path}")
    return max(values)


def runtime_records() -> list[dict]:
    rows = []
    for job in RUNTIME_JOBS:
        root = RUNTIME_ROOT / str(job)
        stage_status = {}
        with (root / "stages.tsv").open(newline="", encoding="utf-8") as handle:
            for stage in csv.DictReader(handle, delimiter="\t"):
                stage_status[stage["stage"]] = stage
        if set(stage_status) != set(STAGES) or any(
            int(stage_status[stage]["exit_code"]) != 0 for stage in STAGES
        ):
            raise RuntimeError(f"Incomplete runtime workflow {job}")
        for stage in STAGES:
            resource = parse_resource_file(root / f"{stage}.resources.txt")
            rows.append(
                {
                    "job_id": job,
                    "stage": stage,
                    "wall_seconds": resource["elapsed_seconds"],
                    "cpu_seconds": resource["user_cpu_seconds"]
                    + resource["system_cpu_seconds"],
                    "max_rss_gib": resource["max_rss_kib"] / 1024**2,
                    "sampled_gpu_memory_mib": max_gpu_memory(
                        root / f"{stage}.gpu_samples.csv"
                    ),
                }
            )
    return rows


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def plot_stability(summaries: list[dict], destination: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, (score_ax, spread_ax) = plt.subplots(
        2, 1, figsize=(11.5, 7.8), sharex=True, height_ratios=(2.2, 1)
    )
    x = np.arange(len(DATASETS))
    colors = ("#335C81", "#D1495B", "#2A9D8F")
    for seed, color in zip(SEEDS, colors):
        scores = [row[f"seed_{seed}_mSCF1"] for row in summaries]
        score_ax.plot(
            x,
            scores,
            marker="o",
            linewidth=2,
            markersize=6,
            color=color,
            label=f"Initialization seed {seed}",
        )
    score_ax.set_ylabel("mSCF1 (higher is better)")
    score_ax.set_ylim(0, 0.72)
    score_ax.set_title("S3PL 10-epoch GBM results depend on weight initialization")
    score_ax.legend(ncol=3, frameon=True, loc="upper center")

    spreads = [row["range_mSCF1"] for row in summaries]
    bars = spread_ax.bar(
        x,
        spreads,
        color=["#D1495B" if value >= 0.10 else "#8FA6B8" for value in spreads],
    )
    spread_ax.axhline(0.10, color="#333333", linestyle="--", linewidth=1.3)
    spread_ax.text(
        len(DATASETS) - 0.45,
        0.108,
        "0.10 spread",
        ha="right",
        va="bottom",
        fontsize=9,
    )
    spread_ax.bar_label(bars, labels=[f"{value:.3f}" for value in spreads], padding=3)
    spread_ax.set_ylabel("Seed range")
    spread_ax.set_ylim(0, max(spreads) + 0.09)
    spread_ax.set_xticks(x, [name.replace("_", "\n") for name in DATASETS])
    spread_ax.set_xlabel("GBM tissue section")
    fig.text(
        0.5,
        0.005,
        "Fixed sample order, patch size 3 and 10 epochs; no best-seed selection.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.025, 1, 1))
    fig.savefig(destination, dpi=220, bbox_inches="tight")
    plt.close(fig)


def plot_runtime(rows: list[dict], destination: Path) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 5.2))
    jobs = list(RUNTIME_JOBS)
    x = np.arange(len(jobs))
    width = 0.35

    def get(job: int, stage: str, field: str) -> float:
        return next(
            row[field]
            for row in rows
            if row["job_id"] == job and row["stage"] == stage
        )

    s3pl = [get(job, "s3pl_full", "wall_seconds") for job in jobs]
    train = [get(job, "vae_train", "wall_seconds") for job in jobs]
    attribution = [get(job, "vae_attribution", "wall_seconds") for job in jobs]
    evaluation = [get(job, "vae_peak_evaluation", "wall_seconds") for job in jobs]
    s3pl_bars = axes[0].bar(
        x - width / 2, s3pl, width, color="#335C81", label="S3PL full"
    )
    axes[0].bar(x + width / 2, train, width, color="#2A9D8F", label="VAE train")
    axes[0].bar(
        x + width / 2,
        attribution,
        width,
        bottom=train,
        color="#E9C46A",
        label="VAE attribution",
    )
    bottoms = np.array(train) + np.array(attribution)
    axes[0].bar(
        x + width / 2,
        evaluation,
        width,
        bottom=bottoms,
        color="#E76F51",
        label="VAE scoring",
    )
    axes[0].set_ylabel("Wall time (seconds)")
    axes[0].set_title("Native workflow wall time")
    axes[0].legend(fontsize=8)
    axes[0].bar_label(s3pl_bars, labels=[f"{value:.1f}" for value in s3pl], padding=3)
    for position, total in zip(x + width / 2, bottoms + np.array(evaluation)):
        axes[0].text(position, total + 3, f"{total:.1f}", ha="center", fontsize=8)

    s3pl_rss = [get(job, "s3pl_full", "max_rss_gib") for job in jobs]
    vae_rss = [
        max(get(job, stage, "max_rss_gib") for stage in STAGES[1:]) for job in jobs
    ]
    rss_left = axes[1].bar(
        x - width / 2, s3pl_rss, width, color="#335C81", label="S3PL"
    )
    rss_right = axes[1].bar(
        x + width / 2, vae_rss, width, color="#2A9D8F", label="VAE max stage"
    )
    axes[1].set_ylabel("Maximum resident memory (GiB)")
    axes[1].set_title("Host memory")
    axes[1].legend(fontsize=8)
    axes[1].bar_label(rss_left, labels=[f"{value:.2f}" for value in s3pl_rss], padding=3)
    axes[1].bar_label(rss_right, labels=[f"{value:.2f}" for value in vae_rss], padding=3)

    s3pl_gpu = [get(job, "s3pl_full", "sampled_gpu_memory_mib") for job in jobs]
    vae_gpu = [
        max(get(job, stage, "sampled_gpu_memory_mib") for stage in STAGES[1:])
        for job in jobs
    ]
    gpu_left = axes[2].bar(
        x - width / 2, s3pl_gpu, width, color="#335C81", label="S3PL"
    )
    gpu_right = axes[2].bar(
        x + width / 2, vae_gpu, width, color="#2A9D8F", label="VAE max stage"
    )
    axes[2].set_ylabel("Sampled whole-device memory (MiB)")
    axes[2].set_title("GPU memory")
    axes[2].legend(fontsize=8)
    axes[2].bar_label(gpu_left, labels=[f"{value:.0f}" for value in s3pl_gpu], padding=3)
    axes[2].bar_label(gpu_right, labels=[f"{value:.0f}" for value in vae_gpu], padding=3)

    for axis in axes:
        axis.set_xticks(x, [str(job) for job in jobs])
        axis.set_xlabel("Slurm job")
    fig.suptitle("Repeated 160TopL native-workflow cost measurements", fontsize=14)
    fig.text(
        0.5,
        0.005,
        "Protocols are native rather than equal-work: S3PL uses 10 epochs and the VAE uses 100.",
        ha="center",
        fontsize=9,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 0.95))
    fig.savefig(destination, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    GALLERY.mkdir(parents=True, exist_ok=True)
    records = seed_records()
    summaries = section_summaries(records)
    runtime = runtime_records()

    public_seed_rows = [{k: v for k, v in row.items() if k != "peaks"} for row in records]
    write_csv(
        OUTPUT / "s3pl_gbm_seed_screen.csv",
        public_seed_rows,
        [
            "dataset",
            "initialization_seed",
            "sample_order_seed",
            "epochs",
            "patch_size",
            "mSCF1",
            "final_reconstruction_loss",
            "selected_peak_count",
            "metrics_path",
        ],
    )
    write_csv(OUTPUT / "s3pl_gbm_seed_summary.csv", summaries, list(summaries[0]))
    write_csv(OUTPUT / "runtime_repeats.csv", runtime, list(runtime[0]))

    collection_means = {
        f"seed_{seed}": statistics.mean(
            row["mSCF1"] for row in records if row["initialization_seed"] == seed
        )
        for seed in SEEDS
    }
    large_spread = [row["dataset"] for row in summaries if row["range_mSCF1"] >= 0.10]
    runtime_totals = {}
    for job in RUNTIME_JOBS:
        s3pl = next(
            row["wall_seconds"]
            for row in runtime
            if row["job_id"] == job and row["stage"] == "s3pl_full"
        )
        vae = sum(
            row["wall_seconds"]
            for row in runtime
            if row["job_id"] == job and row["stage"] != "s3pl_full"
        )
        runtime_totals[str(job)] = {"s3pl_seconds": s3pl, "vae_seconds": vae}

    summary = {
        "status": "complete",
        "generated_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "protocol": {
            "gbm_seed_screen": "initialization seeds 1-3; sample-order seed 1; 10 epochs; patch size 3",
            "runtime": "native 160TopL workflows on RTX 3060; not equal-work",
        },
        "collection_mean_mSCF1_by_initialization_seed": collection_means,
        "sections_with_at_least_0.10_seed_range": large_spread,
        "section_summaries": summaries,
        "runtime_totals": runtime_totals,
        "reporting_rule": (
            "Report every declared seed and section-level mean plus sample SD; show "
            "collection-level aggregation separately; never select the best seed. "
            "Describe runtime as native-workflow cost, not intrinsic or equal-work speed."
        ),
    }
    (OUTPUT / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    seed_figure = OUTPUT / "s3pl_gbm_seed_stability.png"
    runtime_figure = OUTPUT / "s3pl_vae_native_runtime_repeats.png"
    plot_stability(summaries, seed_figure)
    plot_runtime(runtime, runtime_figure)
    (GALLERY / seed_figure.name).write_bytes(seed_figure.read_bytes())
    (GALLERY / runtime_figure.name).write_bytes(runtime_figure.read_bytes())

    lines = [
        "# S3PL GBM stability and native-runtime synthesis",
        "",
        "All 24 GBM seed-screen configurations and all three native runtime workflows passed validation.",
        "",
        "## Reporting decision",
        "",
        "S3PL's 10-epoch GBM output is initialization-sensitive at section level. Report all declared seeds, section mean and sample SD, collection aggregation, and selected-peak overlap. Do not select the best seed. The collection mean is more stable than several individual sections, so show both levels.",
        "",
        "The native runtime repetitions show the VAE workflow taking less wall time in all three measurements, with slightly lower sampled host and GPU memory. This is a workflow-cost result only: the methods use different architectures, objectives and epoch counts, so it is not an intrinsic efficiency or equal-work claim.",
        "",
        "## Key values",
        "",
        f"- Collection means by initialization seed: {', '.join(f'{key}={value:.3f}' for key, value in collection_means.items())}.",
        f"- Sections with seed range at least 0.10: {len(large_spread)}/8 ({', '.join(large_spread)}).",
        "- Runtime totals (S3PL / VAE seconds): "
        + "; ".join(
            f"{job}: {values['s3pl_seconds']:.2f} / {values['vae_seconds']:.2f}"
            for job, values in runtime_totals.items()
        )
        + ".",
        "",
        "See `summary.json` and the CSV files in this directory for exact provenance-linked values.",
    ]
    (OUTPUT / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Saved synthesis to {OUTPUT}")


if __name__ == "__main__":
    main()

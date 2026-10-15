#!/usr/bin/env python3
"""Items B and C1 of the 15 October round: runtime table and training curves.

Reads only saved JSON artifacts (no HDF5, no model, no scoring, no new runs)
and writes, under results/publication/current_evidence/:

  runtime_all_sections.csv     one row per section and method: training time,
                               timer boundary, epochs, GPU model, peak GPU memory
  training_curves_vae.csv      per-epoch VAE losses, all 16 sections, centre-only
                               and uniform-mean production runs
  training_curves_s3pl.csv     per-epoch S3PL losses: GBM108_positive 10/25/50-epoch
                               runs (initialization seeds 1 and 2) and the 16
                               existing 10-epoch seed-1 baselines
  training_curves.png          figure of both

Timer boundaries differ between runs and are labelled per row, never merged:
the historical VAE production trainer streamed spectra from HDF5 inside each
epoch, so its time includes HDF5 reads; the attention runs and the GBM108_positive
cached runs loaded the section into memory first and time it separately; S3PL
builds its patch dataset before its training timer starts.
"""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
EXPERIMENTS = RESULTS / "experiments"
S3PL_RESULTS = RESULTS / "baselines" / "s3pl"
S3PL_LOGS = ROOT / "logs" / "s3pl"
S3PL_REPRO = ROOT / "reproducibility" / "s3pl_massnet"
CACHED = RESULTS / "validation" / "spatial_msipl_cached_full" / "GBM108_positive_seed1"

GBM = ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2",
       "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2")
CAC = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL")
DEVELOPMENT = {"GBM108_positive", "GBM22_2", "160TopL", "40TopL"}

STREAMED = ("VAE production trainer, sum of per-epoch times; each epoch streams "
            "spectra from HDF5, so HDF5 reads are inside the timer")
CACHED_TIMER = ("VAE cached trainer, sum of per-epoch times; the section was loaded "
                "into memory before training and that load is timed separately")
S3PL_TIMER = ("S3PL training loop only (baselines/s3pl/train.py); the patch dataset "
              "is built in memory before the timer starts; peak picking not included")
S3PL_LOSS = "MSE of the last mini-batch of each epoch (released S3PL train_history)"
VAE_LOSS = "sample-weighted mean over the epoch's mini-batches"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def relative(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def write_csv(path, rows):
    fields = list(rows[0])
    for row in rows[1:]:
        fields += [key for key in row if key not in fields]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {path.name} ({len(rows)} rows)")


def collection(section):
    return "GBM" if section.startswith("GBM") else "CAC"


def vae_run_dirs(section):
    """Production centre-only and uniform-mean training folders, and attention."""
    if section.startswith("GBM"):
        centre = EXPERIMENTS / "spatial_msipl_reconstruction" / f"{section}_seed1" / "central_only"
        uniform = EXPERIMENTS / "spatial_msipl_neighbourhood" / f"{section}_seed1" / "uniform_mean"
    else:
        centre = EXPERIMENTS / "spatial_msipl_cac_reconstruction" / f"{section}_seed1" / "central_only"
        uniform = EXPERIMENTS / "spatial_msipl_cac_neighbourhood" / f"{section}_seed1" / "uniform_mean"
    attention = EXPERIMENTS / "spatial_attention_context" / f"{section}_seed1" / "real_attention"
    return {"vae_central_only": centre, "vae_uniform_mean": uniform, "vae_attention": attention}


def history_seconds(history):
    return sum(float(record["epoch_seconds"]) for record in history)


def vae_runtime_row(section, method, folder, timer):
    summary = load(folder / "summary.json")
    metadata = load(folder / "metadata.json")
    history = load(folder / "training_history.json")
    if summary.get("status") != "complete":
        raise SystemExit(f"{folder}: training summary status is not complete")
    if len(history) != int(metadata["epochs"]):
        raise SystemExit(f"{folder}: {len(history)} history epochs, metadata says "
                         f"{metadata['epochs']}")
    seconds = float(summary["training_seconds"])
    if abs(seconds - history_seconds(history)) > 1e-6 * max(1.0, seconds):
        raise SystemExit(f"{folder}: training_seconds differs from the summed epoch times")
    load_seconds = summary.get("dataset_load_seconds")
    return {
        "section": section, "collection": collection(section),
        "development_section": section in DEVELOPMENT, "method": method,
        "epochs": len(history), "training_seconds": seconds,
        "seconds_per_epoch": seconds / len(history),
        "data_load_seconds_outside_timer": load_seconds,
        "timer_boundary": timer, "gpu": metadata.get("device_name"),
        "peak_gpu_memory_allocated_bytes": summary.get("peak_gpu_memory_allocated_bytes"),
        "resumed_from_epoch": summary.get("resumed_from_epoch"),
        "samples_per_epoch": summary.get("samples_per_epoch"),
        "source": relative(folder / "summary.json"),
    }


def s3pl_name(section, epochs=10):
    patch = 3 if section.startswith("GBM") else 9
    return f"{section}_Attention3DConvAutoencoder_{epochs}epochs_256_spectral_patch_size_{patch}"


def s3pl_runtime_row(section):
    name = s3pl_name(section)
    runtime_path = S3PL_RESULTS / name / "runtime_metrics.json"
    runtime = load(runtime_path)
    log = load(S3PL_LOGS / f"{name}.json")
    if runtime.get("normalization", "reference_spatial_max") != "reference_spatial_max":
        raise SystemExit(f"{runtime_path}: unexpected normalisation")
    if log.get("initialization_seed") is not None or int(log["random_seed"]) != 1:
        raise SystemExit(f"{name}: not the released seed-1 RNG path")
    return {
        "section": section, "collection": collection(section),
        "development_section": section in DEVELOPMENT, "method": "s3pl_10_epochs",
        "epochs": int(log["n_epochs"]), "training_seconds": float(runtime["training_seconds"]),
        "seconds_per_epoch": float(runtime["training_seconds"]) / int(log["n_epochs"]),
        "data_load_seconds_outside_timer": None,
        "timer_boundary": S3PL_TIMER, "gpu": runtime.get("device"),
        "peak_gpu_memory_allocated_bytes": runtime.get("peak_gpu_memory_bytes"),
        "resumed_from_epoch": None, "samples_per_epoch": None,
        "source": relative(runtime_path),
    }


def runtime_rows():
    rows = []
    for section in GBM + CAC:
        folders = vae_run_dirs(section)
        rows.append(vae_runtime_row(section, "vae_central_only", folders["vae_central_only"], STREAMED))
        rows.append(vae_runtime_row(section, "vae_uniform_mean", folders["vae_uniform_mean"], STREAMED))
        rows.append(vae_runtime_row(section, "vae_attention", folders["vae_attention"], CACHED_TIMER))
        if section == "GBM108_positive":
            for arm in ("central_only", "uniform_mean"):
                rows.append(vae_runtime_row(section, f"vae_{arm}_cached_rerun", CACHED / arm,
                                            CACHED_TIMER))
        rows.append(s3pl_runtime_row(section))
    return rows


def vae_curve_rows():
    rows = []
    for section in GBM + CAC:
        folders = vae_run_dirs(section)
        for arm in ("central_only", "uniform_mean"):
            folder = folders[f"vae_{arm}"]
            for record in load(folder / "training_history.json"):
                rows.append({
                    "section": section, "collection": collection(section),
                    "development_section": section in DEVELOPMENT, "arm": arm,
                    "epoch": int(record["epoch"]),
                    "total_loss": record["total_loss"],
                    "reconstruction_loss": record["reconstruction_loss"],
                    "kl_loss": record["kl_loss"],
                    "epoch_seconds": record["epoch_seconds"],
                    "loss_definition": VAE_LOSS,
                    "source": relative(folder / "training_history.json"),
                })
    return rows


def s3pl_curve_rows():
    runs = []
    for initialization in (1, 2):
        for epochs, suffix in ((10, ""), (25, "_25epochs"), (50, "_50epochs")):
            folder = S3PL_REPRO / f"GBM108_positive_p3_rng_init{initialization}_order1{suffix}"
            runs.append((f"GBM108_positive_init{initialization}_order1_{epochs}epochs",
                         "GBM108_positive", f"controlled RNG: initialization seed "
                         f"{initialization}, sample-order seed 1",
                         folder / "logs" / "s3pl" / f"{s3pl_name('GBM108_positive', epochs)}.json",
                         epochs))
    for section in GBM + CAC:
        runs.append((f"{section}_released_seed1_10epochs", section,
                     "released RNG path, random_seed 1",
                     S3PL_LOGS / f"{s3pl_name(section)}.json", 10))
    rows = []
    for run, section, rng, path, epochs in runs:
        log = load(path)
        history = log["train_history"]
        if int(log["n_epochs"]) != epochs or len(history) != epochs:
            raise SystemExit(f"{path}: expected {epochs} epochs")
        for epoch, loss in enumerate(history, start=1):
            rows.append({"run": run, "section": section, "collection": collection(section),
                         "rng": rng, "run_epochs": epochs, "epoch": epoch,
                         "loss": loss, "loss_definition": S3PL_LOSS,
                         "source": relative(path)})
    return rows


def plot(vae_rows, s3pl_rows, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    colours = {"central_only": "#2a78d6", "uniform_mean": "#eb6834"}
    labels = {"central_only": "centre-only", "uniform_mean": "uniform 3×3"}
    figure, axes = plt.subplots(1, 3, figsize=(13, 4), constrained_layout=True)
    for axis, name in zip(axes[:2], ("GBM", "CAC")):
        for arm in ("central_only", "uniform_mean"):
            for index, section in enumerate(GBM if name == "GBM" else CAC):
                series = [r for r in vae_rows if r["section"] == section and r["arm"] == arm]
                first = series[0]["total_loss"]
                axis.plot([r["epoch"] for r in series],
                          [r["total_loss"] / first for r in series],
                          color=colours[arm], linewidth=1.2, alpha=0.7,
                          label=labels[arm] if index == 0 else None)
        for epoch in (10, 25, 50):
            axis.axvline(epoch, color="#b8b8b2", linewidth=0.8, zorder=0)
        axis.set_title(f"VAE, {name} (8 sections; 100 epochs)")
        axis.set_xlabel("epoch")
        axis.set_ylabel("epoch-mean total loss / epoch 1")
        axis.legend(frameon=False)
    axis = axes[2]
    for initialization, colour in ((1, "#2a78d6"), (2, "#eb6834")):
        for epochs, style in ((10, ":"), (25, "--"), (50, "-")):
            run = f"GBM108_positive_init{initialization}_order1_{epochs}epochs"
            series = [r for r in s3pl_rows if r["run"] == run]
            axis.plot([r["epoch"] for r in series], [r["loss"] for r in series],
                      color=colour, linestyle=style, linewidth=1.4,
                      label=f"init {initialization}, {epochs} epochs")
    axis.axvline(10, color="#b8b8b2", linewidth=0.8, zorder=0)
    axis.set_yscale("log")
    axis.set_title("S3PL, GBM108_positive (patch 3)")
    axis.set_xlabel("epoch")
    axis.set_ylabel("last-batch MSE (log scale)")
    axis.legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", color="#e6e6e1", linewidth=0.6)
    figure.savefig(path, dpi=200)
    plt.close(figure)
    print(f"wrote {path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=RESULTS / "publication" / "current_evidence")
    parser.add_argument("--no-figure", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / "runtime_all_sections.csv", runtime_rows())
    vae = vae_curve_rows()
    s3pl = s3pl_curve_rows()
    write_csv(args.output / "training_curves_vae.csv", vae)
    write_csv(args.output / "training_curves_s3pl.csv", s3pl)
    if not args.no_figure:
        plot(vae, s3pl, args.output / "training_curves.png")


if __name__ == "__main__":
    main()

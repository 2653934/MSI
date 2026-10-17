#!/usr/bin/env python3
"""Items B and C1 of the 15 October round: runtime table and training curves.

Reads only saved JSON artifacts (no HDF5, no model, no scoring, no new runs)
and writes, under results/publication/current_evidence/:

  runtime_all_sections.csv     one row per section and method: training time,
                               timer boundary, epochs, GPU model, peak GPU memory
  runtime_all_sections_v2.csv  the v1 rows plus seed and loader columns, and the
                               RCC, S3PL 100-epoch, S3PL seed 2/3 and Test R
                               cached rows (supervisor chat 2026-10-17 09:48);
                               the v1 file is left unchanged
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
RCC_EXPERIMENTS = EXPERIMENTS / "rcc_spatial_msipl"
TEST_R = EXPERIMENTS / "test_r_training_seeds"
S3PL_E100 = ROOT / "reproducibility" / "s3pl_e100" / "seed1_released"
S3PL_CAC_SEEDS = ROOT / "reproducibility" / "s3pl_cac_seeds"
S3PL_RCC = ROOT / "reproducibility" / "s3pl_rcc"
V1_NAME = "runtime_all_sections.csv"
V2_NAME = "runtime_all_sections_v2.csv"

GBM = ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2",
       "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2")
CAC = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL")
RCC = ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
       "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01")
TEST_R_SECTIONS = RCC + CAC + GBM   # slurm_jobs/test_r_sections.sh order
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
    path = Path(path).resolve()
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:   # only test fixtures live outside the workspace
        return path.as_posix()


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
    if section.startswith("RCC_"):
        return "RCC"
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
    if section.startswith("RCC_"):   # released RCC configuration; files drop the prefix
        return (f"{section[len('RCC_'):]}_Attention3DConvAutoencoder_{epochs}epochs_1024"
                "_spectral_patch_size_5")
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


# --- Runtime table v2 (supervisor chat 2026-10-17 09:48, item 1) --------------

LOADERS = {"streaming_hdf5": "streaming", "cached_float32": "cached"}


def with_seed_and_loader(row, seed, loader):
    """Insert seed and loader after method; every other v1 field is kept as is."""
    out = {}
    for key, value in row.items():
        out[key] = value
        if key == "method":
            out["seed"] = int(seed)
            out["loader"] = loader
    return out


def vae_loader(folder, timer):
    """streaming/cached from the training summary, checked against the timer label.

    The historical production trainer predates the data_loader field and always
    streamed, so an absent field is accepted only under the streaming timer.
    """
    summary = load(Path(folder) / "summary.json")
    recorded = summary.get("controls", {}).get("data_loader")
    loader = "streaming" if recorded is None else LOADERS.get(recorded)
    expected = "streaming" if timer == STREAMED else "cached"
    if loader != expected:
        raise SystemExit(f"{folder}: data_loader {recorded!r} contradicts the "
                         f"{expected} timer label")
    return loader


def vae_row_v2(section, method, folder, timer, expected_seed=None):
    folder = Path(folder)
    seed = int(load(folder / "metadata.json")["seed"])
    if expected_seed is not None and seed != expected_seed:
        raise SystemExit(f"{folder}: training seed {seed}, expected {expected_seed}")
    return with_seed_and_loader(vae_runtime_row(section, method, folder, timer),
                                seed, vae_loader(folder, timer))


def s3pl_seed_row(section, artifact_root, epochs, seed):
    """S3PL row from an artifact root (released RNG path, given seed and epochs)."""
    name = s3pl_name(section, epochs)
    artifact_root = Path(artifact_root)
    runtime_path = artifact_root / "results" / "baselines" / "s3pl" / name / "runtime_metrics.json"
    runtime = load(runtime_path)
    log = load(artifact_root / "logs" / "s3pl" / f"{name}.json")
    if runtime.get("normalization", "reference_spatial_max") != "reference_spatial_max":
        raise SystemExit(f"{runtime_path}: unexpected normalisation")
    if log.get("initialization_seed") is not None or int(log["random_seed"]) != seed:
        raise SystemExit(f"{name}: not the released RNG path with random_seed {seed}")
    if int(log["n_epochs"]) != epochs:
        raise SystemExit(f"{name}: {log['n_epochs']} epochs, expected {epochs}")
    seconds = float(runtime["training_seconds"])
    row = {
        "section": section, "collection": collection(section),
        "development_section": section in DEVELOPMENT, "method": f"s3pl_{epochs}_epochs",
        "epochs": epochs, "training_seconds": seconds, "seconds_per_epoch": seconds / epochs,
        "data_load_seconds_outside_timer": None,
        "timer_boundary": S3PL_TIMER, "gpu": runtime.get("device"),
        "peak_gpu_memory_allocated_bytes": runtime.get("peak_gpu_memory_bytes"),
        "resumed_from_epoch": None, "samples_per_epoch": None,
        "source": relative(runtime_path),
    }
    # S3PL builds its patch dataset in memory before training: a cached loader.
    return with_seed_and_loader(row, seed, "cached")


def test_r_rows(root=TEST_R):
    """Cached Test R training rows (seeds 2 and 3) for every run present under root."""
    rows, counts = [], {2: 0, 3: 0}
    root = Path(root)
    if not root.exists():
        return rows, counts
    found = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        section, _, seed = folder.name.rpartition("_seed")
        if section not in TEST_R_SECTIONS or seed not in ("2", "3"):
            raise SystemExit(f"{folder}: not a Test R section/seed folder")
        for arm in ("central_only", "uniform_mean"):
            if (folder / arm / "summary.json").exists():
                found.append((int(seed), TEST_R_SECTIONS.index(section), arm, section,
                              folder / arm))
    for seed, _, arm, section, run in sorted(found):
        rows.append(vae_row_v2(section, f"vae_{arm}", run, CACHED_TIMER, expected_seed=seed))
        counts[seed] += 1
    return rows, counts


LEGACY_RCC_SACCT = RESULTS / "baselines" / "msipl" / "rcc_provenance" / "sacct_elapsed_20261017.txt"
LEGACY_WALL = ("Slurm elapsed (wall) time, whole job, not a training-loop timer: legacy "
               "msiPL training (100 epochs), LearnPeaks Beta tuning and evaluation together "
               "(sacct ElapsedRaw; supervisor chat 2026-10-17 12:41)")


def legacy_rcc_rows(path=LEGACY_RCC_SACCT):
    """One row per RCC run from the saved sacct export; its time is never a training time.

    Array index i is RCC[i] (slurm_jobs/rcc_sections.sh order). Exactly one COMPLETED
    task per run is required; failed attempts are ignored.
    """
    completed = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        job, _name, state, _elapsed, raw, node, exit_code = line.split("|")[:7]
        if state != "COMPLETED":
            continue
        index = int(job.split("_")[1])
        if index in completed:
            raise SystemExit(f"{path}: two COMPLETED tasks for array index {index}")
        completed[index] = (job, int(raw), node)
    if sorted(completed) != list(range(len(RCC))):
        raise SystemExit(f"{path}: COMPLETED tasks for indices {sorted(completed)}, "
                         f"expected 0-{len(RCC) - 1}")
    rows = []
    for index, section in enumerate(RCC):
        job, seconds, node = completed[index]
        row = {
            "section": section, "collection": "RCC", "development_section": False,
            "method": "legacy_msipl_whole_job", "epochs": 100,
            "training_seconds": None, "seconds_per_epoch": None,
            "data_load_seconds_outside_timer": None, "timer_boundary": LEGACY_WALL,
            "gpu": None, "peak_gpu_memory_allocated_bytes": None,
            "resumed_from_epoch": None, "samples_per_epoch": None,
            "source": relative(path), "slurm_job_wall_seconds": seconds,
            "slurm_job": job, "slurm_node": node,
        }
        # Legacy msiPL seed 1337 (run_msipl_rcc.sh); it loads the whole run itself.
        rows.append(with_seed_and_loader(row, 1337, "not applicable (whole job)"))
    return rows


def runtime_rows_v2(test_r_root=TEST_R):
    rows = []
    for row in runtime_rows():   # the v1 rows, unchanged apart from the two columns
        if row["method"].startswith("vae_"):
            folder = ROOT / Path(row["source"]).parent
            seed = int(load(folder / "metadata.json")["seed"])
            rows.append(with_seed_and_loader(row, seed,
                                             vae_loader(folder, row["timer_boundary"])))
        else:
            rows.append(with_seed_and_loader(row, 1, "cached"))
    for section in RCC:
        for arm in ("central_only", "uniform_mean"):
            rows.append(vae_row_v2(section, f"vae_{arm}",
                                   RCC_EXPERIMENTS / f"{section}_seed1" / arm, CACHED_TIMER,
                                   expected_seed=1))
    for seed in (1, 2, 3):
        for section in RCC:
            rows.append(s3pl_seed_row(section, S3PL_RCC / f"seed{seed}_released", 10, seed))
    for seed in (2, 3):
        for section in CAC:
            rows.append(s3pl_seed_row(section, S3PL_CAC_SEEDS / f"seed{seed}_released", 10, seed))
    for section in GBM + CAC:
        rows.append(s3pl_seed_row(section, S3PL_E100, 100, 1))
    rows += legacy_rcc_rows()
    test_r, counts = test_r_rows(test_r_root)
    for seed, count in counts.items():
        print(f"Test R seed {seed}: {count}/48 cached training runs tabulated")
    return rows + test_r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path,
                        default=RESULTS / "publication" / "current_evidence")
    parser.add_argument("--no-figure", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    write_csv(args.output / V1_NAME, runtime_rows())
    write_csv(args.output / V2_NAME, runtime_rows_v2())
    vae = vae_curve_rows()
    s3pl = s3pl_curve_rows()
    write_csv(args.output / "training_curves_vae.csv", vae)
    write_csv(args.output / "training_curves_s3pl.csv", s3pl)
    if not args.no_figure:
        plot(vae, s3pl, args.output / "training_curves.png")


if __name__ == "__main__":
    main()

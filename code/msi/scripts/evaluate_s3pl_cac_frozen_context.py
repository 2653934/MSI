#!/usr/bin/env python3
"""Compare frozen S3PL CAC inference on real, zeroed, and centre-tiled patches."""

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path


THRESHOLDS = ("0.3", "0.4", "0.5", "0.6")


def selected_mz(path):
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    values = [float(row["0"]) for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"Duplicate selected m/z values: {path}")
    return values


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--number-peaks", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.number_peaks < 1:
        raise ValueError("--number-peaks must be positive")

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "baselines" / "s3pl"))
    from test import test
    from utils.helpers import artifact_directories

    config = json.loads(args.config.read_text(encoding="utf-8"))
    training_name = config["training_name"]
    section = Path(config["data_dir"]).stem
    artifact_dirs = artifact_directories(config, project_root / "baselines" / "s3pl")
    checkpoint = artifact_dirs["weights"] / f"{training_name}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    result_root = artifact_dirs["results"]
    matched_suffix = f"_matched_{args.number_peaks}peaks"
    baseline_suffix = f"_frozen_real_{args.number_peaks}peaks"
    zero_suffix = f"_frozen_zero_noncentral_{args.number_peaks}peaks"
    tiled_suffix = f"_frozen_tiled_centre_{args.number_peaks}peaks"
    peak_filename = f"picked_peaks_{section}_{config['peaks_per_spectral_patch']}peaks_z_patchsize_{config['spectral_patch_size']}.csv"

    def paths(suffix):
        directory = result_root / f"{training_name}{suffix}"
        return directory / "metrics.json", directory / peak_filename

    source_metrics_path, source_peaks_path = paths(matched_suffix)
    if not source_metrics_path.is_file() or not source_peaks_path.is_file():
        raise FileNotFoundError("Run the existing matched-count S3PL evaluation first")
    source_metrics = json.loads(source_metrics_path.read_text(encoding="utf-8"))
    source_peaks = selected_mz(source_peaks_path)
    if len(source_peaks) != args.number_peaks:
        raise ValueError("Existing matched-count list has the wrong size")

    # Reproduce the old result before interpreting the perturbation. Distinct
    # suffixes leave the publication source and checkpoint untouched.
    test(config, None, args.number_peaks, baseline_suffix, input_ablation="none")
    real_metrics_path, real_peaks_path = paths(baseline_suffix)
    real_metrics = json.loads(real_metrics_path.read_text(encoding="utf-8"))
    real_peaks = selected_mz(real_peaks_path)
    # F1 evaluates the selected set, not its internal ranking. Equal-score
    # pixel-frequency ties may reorder selected peaks without changing that set.
    if set(real_peaks) != set(source_peaks) or real_metrics["mixed_f1"] != source_metrics["mixed_f1"]:
        raise ValueError("Frozen real-input run did not reproduce the existing selected set and threshold scores")

    test(config, None, args.number_peaks, zero_suffix, input_ablation="zero_noncentral")
    zero_metrics_path, zero_peaks_path = paths(zero_suffix)
    zero_metrics = json.loads(zero_metrics_path.read_text(encoding="utf-8"))
    zero_peaks = selected_mz(zero_peaks_path)
    if len(zero_peaks) != args.number_peaks:
        raise ValueError("Ablated list has the wrong peak budget")
    if zero_metrics["normalization"] != real_metrics["normalization"]:
        raise ValueError("Normalisation changed between frozen evaluations")
    if real_metrics["number_picked_peaks"] != args.number_peaks or zero_metrics["number_picked_peaks"] != args.number_peaks:
        raise ValueError("An evaluation did not honour the matched peak budget")

    test(config, None, args.number_peaks, tiled_suffix, input_ablation="tile_centre")
    tiled_metrics_path, tiled_peaks_path = paths(tiled_suffix)
    tiled_metrics = json.loads(tiled_metrics_path.read_text(encoding="utf-8"))
    tiled_peaks = selected_mz(tiled_peaks_path)
    if len(tiled_peaks) != args.number_peaks or tiled_metrics["number_picked_peaks"] != args.number_peaks:
        raise ValueError("Tiled-centre evaluation did not honour the matched peak budget")
    if tiled_metrics["normalization"] != real_metrics["normalization"]:
        raise ValueError("Normalisation changed in the tiled-centre evaluation")

    real_set, zero_set, tiled_set = set(real_peaks), set(zero_peaks), set(tiled_peaks)
    thresholds = {
        threshold: {
            "real_f1": real_metrics["mixed_f1"][threshold],
            "zero_noncentral_f1": zero_metrics["mixed_f1"][threshold],
            "tiled_centre_f1": tiled_metrics["mixed_f1"][threshold],
            "real_minus_zero_f1": real_metrics["mixed_f1"][threshold] - zero_metrics["mixed_f1"][threshold],
            "real_minus_tiled_f1": real_metrics["mixed_f1"][threshold] - tiled_metrics["mixed_f1"][threshold],
        }
        for threshold in THRESHOLDS
    }
    real_full = sum(real_metrics["mixed_f1"][threshold] for threshold in THRESHOLDS) / len(THRESHOLDS)
    zero_full = sum(zero_metrics["mixed_f1"][threshold] for threshold in THRESHOLDS) / len(THRESHOLDS)
    tiled_full = sum(tiled_metrics["mixed_f1"][threshold] for threshold in THRESHOLDS) / len(THRESHOLDS)
    report = {
        "status": "valid",
        "section": section,
        "training_name": training_name,
        "training_repeated": False,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": sha256(checkpoint),
        "config_sha256": sha256(args.config),
        "matched_peaks": args.number_peaks,
        "normalization": real_metrics["normalization"],
        "interventions": {
            "zero_noncentral": "zero noncentral patch positions after original normalisation",
            "tile_centre": "fill every patch position with the unchanged normalised central spectrum",
        },
        "baseline_matches_prior_selected_set_and_mixed_f1": True,
        "baseline_peak_order_matches_prior": real_peaks == source_peaks,
        "baseline_changed_rank_positions": sum(left != right for left, right in zip(real_peaks, source_peaks)),
        "real_mscf1": real_metrics["mSCF1"],
        "zero_noncentral_mscf1": zero_metrics["mSCF1"],
        "tiled_centre_mscf1": tiled_metrics["mSCF1"],
        "real_minus_zero_mscf1": real_metrics["mSCF1"] - zero_metrics["mSCF1"],
        "real_minus_tiled_mscf1": real_metrics["mSCF1"] - tiled_metrics["mSCF1"],
        "real_mscf1_unrounded": real_full,
        "zero_noncentral_mscf1_unrounded": zero_full,
        "tiled_centre_mscf1_unrounded": tiled_full,
        "real_minus_zero_mscf1_unrounded": real_full - zero_full,
        "real_minus_tiled_mscf1_unrounded": real_full - tiled_full,
        "shared_selected_peaks": len(real_set & zero_set),
        "entering_and_leaving_peaks": args.number_peaks - len(real_set & zero_set),
        "shared_selected_peaks_real_and_tiled": len(real_set & tiled_set),
        "entering_and_leaving_peaks_real_and_tiled": args.number_peaks - len(real_set & tiled_set),
        "thresholds": thresholds,
        "source_matched_metrics": str(source_metrics_path),
        "real_metrics": str(real_metrics_path),
        "zero_noncentral_metrics": str(zero_metrics_path),
        "tiled_centre_metrics": str(tiled_metrics_path),
        "limitation": "Both frozen input interventions are out of training distribution; sensitivity or F1 change is not a causal training benefit and does not isolate the S3PL-versus-VAE architecture gap. The original spatial-maximum normalisation is applied before intervention, so unchanged central values can still encode neighbour-dependent scaling. Tiling preserves patch occupancy and approximate magnitude but not the distribution of real neighbour spectra.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

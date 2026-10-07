#!/usr/bin/env python3
"""Test frozen S3PL sensitivity to neighbour positions at a matched CAC peak count."""

import argparse
import json
import sys
from pathlib import Path

from evaluate_s3pl_cac_frozen_context import THRESHOLDS, selected_mz, sha256


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
    if config.get("input_context_mode", "none") != "none":
        raise ValueError("Use the original real-patch checkpoint, not a trained input control")
    training_name = config["training_name"]
    section = Path(config["data_dir"]).stem
    artifact_dirs = artifact_directories(config, project_root / "baselines" / "s3pl")
    checkpoint = artifact_dirs["weights"] / f"{training_name}.pt"
    if not checkpoint.is_file():
        raise FileNotFoundError(checkpoint)
    checkpoint_hash = sha256(checkpoint)
    config_hash = sha256(args.config)
    if args.output.exists():
        prior = json.loads(args.output.read_text(encoding="utf-8"))
        if (
            prior.get("status") in ("valid", "valid_pair_with_prior_drift")
            and prior.get("checkpoint_sha256") == checkpoint_hash
            and prior.get("config_sha256") == config_hash
            and prior.get("matched_peaks") == args.number_peaks
        ):
            print(f"Already complete with the same frozen inputs: {args.output}", flush=True)
            return
        raise FileExistsError(f"Existing topology report has different provenance: {args.output}")

    result_root = artifact_dirs["results"]
    peak_filename = (
        f"picked_peaks_{section}_{config['peaks_per_spectral_patch']}peaks_z_patchsize_"
        f"{config['spectral_patch_size']}.csv"
    )

    def result_paths(suffix):
        directory = result_root / f"{training_name}{suffix}"
        return directory / "metrics.json", directory / peak_filename

    source_path, source_peaks_path = result_paths(f"_matched_{args.number_peaks}peaks")
    source_metrics = json.loads(source_path.read_text(encoding="utf-8"))
    source_peaks = selected_mz(source_peaks_path)
    if source_metrics["number_picked_peaks"] != args.number_peaks or len(source_peaks) != args.number_peaks:
        raise ValueError("Stored matched-count source has the wrong peak budget")

    modes = ("none", "rotate_90", "permute_within_rings")
    suffixes = {
        "none": f"_frozen_topology_real_{args.number_peaks}peaks",
        "rotate_90": f"_frozen_topology_rotate90_{args.number_peaks}peaks",
        "permute_within_rings": f"_frozen_topology_ringshift_{args.number_peaks}peaks",
    }
    metrics = {}
    peak_sets = {}
    result_files = {}
    for mode in modes:
        suffix = suffixes[mode]
        test(config, None, args.number_peaks, suffix, input_ablation=mode)
        metric_path, peak_path = result_paths(suffix)
        measured = json.loads(metric_path.read_text(encoding="utf-8"))
        selected = selected_mz(peak_path)
        if measured["number_picked_peaks"] != args.number_peaks or len(selected) != args.number_peaks:
            raise ValueError(f"{mode}: evaluation did not honour the matched peak budget")
        if measured["frozen_input_ablation"] != mode:
            raise ValueError(f"{mode}: output metadata does not match the requested intervention")
        metrics[mode] = measured
        peak_sets[mode] = set(selected)
        result_files[mode] = str(metric_path)

    real = metrics["none"]
    drift = (
        peak_sets["none"] != set(source_peaks)
        or real["mixed_f1"] != source_metrics["mixed_f1"]
    )
    comparisons = {}
    for mode in modes[1:]:
        changed = metrics[mode]
        if changed["normalization"] != real["normalization"]:
            raise ValueError(f"{mode}: normalisation differs from the paired real-input run")
        threshold_delta = {
            threshold: real["mixed_f1"][threshold] - changed["mixed_f1"][threshold]
            for threshold in THRESHOLDS
        }
        real_mean = sum(real["mixed_f1"][threshold] for threshold in THRESHOLDS) / len(THRESHOLDS)
        changed_mean = sum(changed["mixed_f1"][threshold] for threshold in THRESHOLDS) / len(THRESHOLDS)
        comparisons[mode] = {
            "intervention_mscf1": changed["mSCF1"],
            "real_minus_intervention_mscf1_unrounded": real_mean - changed_mean,
            "real_minus_intervention_f1_by_threshold": threshold_delta,
            "shared_selected_peaks_with_real": len(peak_sets["none"] & peak_sets[mode]),
            "entering_and_leaving_peaks": args.number_peaks - len(peak_sets["none"] & peak_sets[mode]),
            "metrics": result_files[mode],
        }

    report = {
        "status": "valid_pair_with_prior_drift" if drift else "valid",
        "section": section,
        "training_repeated": False,
        "training_name": training_name,
        "checkpoint": str(checkpoint),
        "checkpoint_sha256": checkpoint_hash,
        "config_sha256": config_hash,
        "matched_peaks": args.number_peaks,
        "normalization": real["normalization"],
        "interventions": {
            "rotate_90": "rotate the normalised 9x9 patch 90 degrees, preserving its centre, geometry, and all spectral values",
            "permute_within_rings": "cyclically shift positions within each Chebyshev-distance ring around the centre; preserve its centre and each ring's spectral multiset",
        },
        "real_mscf1": real["mSCF1"],
        "real_mscf1_unrounded": sum(real["mixed_f1"].values()) / len(THRESHOLDS),
        "real_metrics": result_files["none"],
        "source_matched_metrics": str(source_path),
        "source_shared_selected_peaks_with_fresh_real": len(peak_sets["none"] & set(source_peaks)),
        "source_threshold_scores_match_fresh_real": real["mixed_f1"] == source_metrics["mixed_f1"],
        "comparisons": comparisons,
        "limitation": "These are post-training, out-of-distribution input tests. They measure frozen-model position sensitivity, not whether real spatial context improves training or explains the S3PL-versus-VAE gap. Normalisation precedes intervention, so the central value can still depend on the original neighbours. Edge zero positions move under both interventions. A cutoff-bin difference from the historical source is recorded; each comparison uses the same fresh real-input job.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

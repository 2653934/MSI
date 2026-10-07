#!/usr/bin/env python3
"""Score a frozen attention model with shuffled inputs or uniform weights.

This reuses the original real-input attribution pixels, component targets,
checkpoint, and GMM. It changes only neighbour spectra at attribution time.
These are mechanism diagnostics, not estimates of generalisation performance.
"""

import argparse
import csv
import json
import resource
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch

from audit_spatial_attention_input_swap import fixed_gmm_parameters
from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
from evaluate_msipl_massnet_peaks import THRESHOLDS
from run_spatial_msipl_gmm_integrated_gradients import (
    baseline_for,
    load_model,
    sample_as_tensors,
    state_sha256,
)
from spatial_msipl.attribution import integrated_gradients_cluster_posterior
from spatial_msipl.neighbourhood import UniformMeanNeighbourhood
from spatial_msipl.peak_selection import balanced_round_robin_rankings
from spatial_msipl.preprocessing import CachedH5SpatialContextDataset, tic_normalize
from evaluate_spatial_reconstruction import deterministic_reconstruction_metrics


def selected_pixel_indices(diagnostics, labels, components, expected_per_component):
    """Recover the exact unsupervised attribution pixels and frozen targets."""
    selected = {component: [] for component in components}
    seen = set()
    for record in diagnostics:
        index = int(record["pixel_index"])
        component = int(record["component"])
        if index in seen or not 0 <= index < len(labels):
            raise ValueError("attribution pixel indices are duplicated or out of range")
        if component not in selected or int(labels[index]) != component:
            raise ValueError("saved pixel target disagrees with the frozen GMM")
        selected[component].append(index)
        seen.add(index)
    if any(len(indices) != expected_per_component for indices in selected.values()):
        raise ValueError("attribution pixel count differs from the frozen real run")
    return selected


def mean_tic_spectrum(dataset, chunk_size=256):
    """Use the production per-spectrum TIC operation without making a second cache."""
    total = np.zeros(dataset.n_mz, dtype=np.float64)
    for begin in range(0, len(dataset), chunk_size):
        raw = dataset._read_spectra(np.arange(begin, min(begin + chunk_size, len(dataset))))
        total += tic_normalize(raw).sum(axis=0, dtype=np.float64)
    return (total / len(dataset)).astype(np.float32)


def component_rankings(scores, mz_count):
    if not scores or any(np.shape(values) != (mz_count,) for values in scores.values()):
        raise ValueError("component scores do not match the m/z axis")
    rankings = {component: np.argsort(values)[::-1].copy() for component, values in scores.items()}
    return balanced_round_robin_rankings(rankings, mz_count)[0]


def completeness_summary(diagnostics):
    residuals = np.asarray([abs(item["completeness_residual"]) for item in diagnostics])
    normalized = np.asarray([
        abs(item["completeness_residual"]) / max(abs(item["score_delta"]), 1e-4)
        for item in diagnostics
    ])
    if not len(normalized):
        raise ValueError("no IG diagnostics were produced")
    median = float(np.median(normalized))
    p95 = float(np.percentile(normalized, 95))
    return {
        "passed": bool(np.all(np.isfinite(normalized)) and median <= 0.05 and p95 <= 0.15),
        "median_normalized_residual": median,
        "percentile_95_normalized_residual": p95,
        "maximum_absolute_residual": float(np.max(residuals)),
    }


def validate_gmm_provenance(fixed_gmm, attribution_dir):
    """Identify whether the earlier reconstruction audit used the same GMM.

    The ranking comparison itself always freezes the original real-input
    attribution GMM. For sections audited before attribution existed, the
    reconstruction audit fitted its own real-input GMM; that provenance is
    recorded, not silently presented as an identical GMM.
    """
    source = fixed_gmm.get("source")
    if source == "pre-existing real-input attribution":
        if Path(fixed_gmm.get("parameters", "")).resolve() != (
            attribution_dir / "gmm_parameters.npz"
        ).resolve():
            raise ValueError("the input-swap audit used a different attribution GMM")
        return True
    if source == "fit once on real-input latent vectors":
        if not Path(fixed_gmm.get("parameters", "")).is_file():
            raise ValueError("the earlier input-swap GMM parameters are missing")
        return False
    raise ValueError("unrecognised input-swap GMM provenance")


def save_plot(result, path):
    thresholds = result["pcc_thresholds"]
    real = result["real"]["mixed_f1"]
    key = "shuffled" if result["intervention"] == "shuffled_input" else "uniform_weights"
    counterfactual = result[key]["mixed_f1"]
    positions = np.arange(len(thresholds))
    fig, ax = plt.subplots(figsize=(7.5, 4.2))
    ax.plot(positions, [real[str(value)] for value in thresholds], "o-", label="Real neighbours")
    ax.plot(positions, [counterfactual[str(value)] for value in thresholds], "o-",
            label="Shuffled neighbours" if key == "shuffled" else "Uniform weights")
    ax.set_xticks(positions, [str(value) for value in thresholds])
    ax.set_xlabel("PCC threshold")
    ax.set_ylabel("Matched-count F1")
    ax.set_ylim(0, 1)
    ax.set_title(f"{result['section']}: frozen attention/GMM peak ranking")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--input-swap-summary", required=True, type=Path)
    parser.add_argument("--peak-evaluation-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--matched-count", required=True, type=int)
    parser.add_argument("--intervention", choices=("shuffled_input", "uniform_weights"),
                        default="shuffled_input")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--ig-steps", type=int, default=64)
    parser.add_argument("--ig-internal-batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.matched_count < 1 or args.ig_steps < 1 or args.ig_internal_batch_size < 1:
        parser.error("matched-count and IG settings must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; ranking swap stopped before loading data")
    started = time.perf_counter()
    real_summary = json.loads((args.attribution_dir / "summary.json").read_text(encoding="utf-8"))
    swap_summary = json.loads(args.input_swap_summary.read_text(encoding="utf-8"))
    evaluation_summary = json.loads(args.peak_evaluation_summary.read_text(encoding="utf-8"))
    section = args.input.stem
    if real_summary["status"] != "valid" or swap_summary["status"] != "valid":
        raise ValueError("original attribution and input-swap audit must both be valid")
    if evaluation_summary["status"] != "complete":
        raise ValueError("original matched-count peak evaluation is incomplete")
    if any(Path(name).stem != section for name in (real_summary["dataset"], swap_summary["input"])):
        raise ValueError("the baseline artifacts refer to another section")
    if swap_summary.get("section") != section:
        raise ValueError("the input-swap audit refers to another section")
    fixed_gmm = swap_summary.get("fixed_gmm", {})
    reconstruction_audit_gmm_aligned = validate_gmm_provenance(fixed_gmm, args.attribution_dir)
    if int(evaluation_summary["matched_peak_evaluation"]["count"]) != args.matched_count:
        raise ValueError("matched count differs from the original peak evaluation")
    if int(real_summary["integrated_gradients"]["steps"]) != args.ig_steps:
        raise ValueError("IG steps differ from the original attribution")
    if not real_summary["integrated_gradients"]["completeness"]["passed"]:
        raise ValueError("original real-input IG failed its completeness check")

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    if int(checkpoint.get("completed_epochs", 0)) != 100:
        raise ValueError("ranking swap requires the full 100-epoch checkpoint")
    real = CachedH5SpatialContextDataset(args.input, True, window_size=3, context_mode="measured")
    shuffled = CachedH5SpatialContextDataset(
        args.input, True, window_size=3, context_mode="shuffled",
        context_seed=int(swap_summary["shuffle_seed"]),
    ) if args.intervention == "shuffled_input" else None
    intervention_dataset = shuffled if shuffled is not None else real
    try:
        if shuffled is not None and shuffled.context_permutation_sha256 != swap_summary["shuffle_source_slots_sha256"]:
            raise ValueError("shuffle permutation differs from the completed input-swap audit")
        if shuffled is not None and not np.array_equal(real.neighbour_slots, shuffled.neighbour_slots):
            raise ValueError("neighbour topology or missing slots changed")
        if shuffled is not None and (not np.array_equal(real.x, shuffled.x) or not np.array_equal(real.y, shuffled.y)):
            raise ValueError("section coordinates changed")
        device = torch.device("cuda")
        model, _ = load_model(args.checkpoint, real.n_mz, "attention", device, checkpoint)
        model_sha = state_sha256(model)
        if model_sha != real_summary["model_state_sha256"] or model_sha != swap_summary["checkpoint_state_sha256"]:
            raise ValueError("checkpoint differs from the frozen real and input-swap audits")
        reconstruction = None
        if args.intervention == "uniform_weights":
            baseline_reconstruction, baseline_pixels = deterministic_reconstruction_metrics(
                model, real, 32, device)
            # Replace only the aggregator's forward rule. All trained encoder/decoder
            # parameters, real neighbours, GMM and attribution targets stay frozen.
            model.aggregator.forward = UniformMeanNeighbourhood().forward
            uniform_reconstruction, uniform_pixels = deterministic_reconstruction_metrics(
                model, real, 32, device)
            if baseline_pixels != uniform_pixels or baseline_pixels != len(real):
                raise ValueError("reconstruction pixel count changed under weight intervention")
            reconstruction = {"learned": baseline_reconstruction,
                              "uniform_weights": uniform_reconstruction,
                              "pixels": baseline_pixels}
        with np.load(args.attribution_dir / "coordinates_and_gmm.npz") as saved:
            if not np.array_equal(saved["x"], real.x) or not np.array_equal(saved["y"], real.y):
                raise ValueError("saved GMM coordinates differ from this section")
            labels = saved["component"].copy()
        with np.load(args.attribution_dir / "attributions.npz") as saved:
            if not np.array_equal(saved["mz"], real.mz_values):
                raise ValueError("saved attribution m/z axis differs from this section")
            components = sorted(np.unique(labels).tolist())
            real_scores = {
                component: saved[f"component_{component}_combined_absolute_mean"].copy()
                for component in components
            }
        selected = selected_pixel_indices(
            real_summary["integrated_gradients"]["per_pixel_diagnostics"],
            labels,
            components,
            int(real_summary["integrated_gradients"]["attribution_pixels_per_component"]),
        )
        gmm = fixed_gmm_parameters(args.attribution_dir / "gmm_parameters.npz", device)
        mean_spectrum = torch.as_tensor(mean_tic_spectrum(real), device=device)
        intervention_scores = {}
        ig_diagnostics = []
        for component, indices in selected.items():
            contributions = []
            for index in indices:
                real_sample = real[index]
                intervention_sample = intervention_dataset[index]
                if not np.array_equal(real_sample["target"], intervention_sample["target"]):
                    raise ValueError("central spectrum changed")
                if not np.array_equal(real_sample["neighbour_mask"], intervention_sample["neighbour_mask"]):
                    raise ValueError("missing-neighbour mask changed")
                central, neighbours, mask = sample_as_tensors(intervention_dataset, index, device)
                central_baseline, neighbour_baseline = baseline_for(mean_spectrum, neighbours, mask)
                central_ig, neighbour_ig, check = integrated_gradients_cluster_posterior(
                    model, central, neighbours, mask, central_baseline, neighbour_baseline,
                    target_component=component, gmm_parameters=gmm,
                    steps=args.ig_steps, internal_batch_size=args.ig_internal_batch_size,
                )
                contributions.append(
                    central_ig[0].abs().detach().cpu().numpy()
                    + neighbour_ig[0].abs().sum(dim=0).detach().cpu().numpy()
                )
                ig_diagnostics.append({"pixel_index": int(index), "component": int(component), **check})
            intervention_scores[component] = np.mean(contributions, axis=0)
            print(f"{section}: component {component} finished {len(indices)} paired IG pixels", flush=True)

        mz, raw_labels, x, y, pixels_first = read_h5_metadata(args.input)
        if not np.array_equal(mz.astype(np.float32), real.mz_values):
            raise ValueError("scoring and attribution m/z axes differ")
        if not np.array_equal(x, real.x) or not np.array_equal(y, real.y):
            raise ValueError("scoring coordinates differ from the attribution section")
        real_order = component_rankings(real_scores, len(mz))
        intervention_order = component_rankings(intervention_scores, len(mz))
        real_peaks = real_order[:args.matched_count]
        intervention_peaks = intervention_order[:args.matched_count]
        original_peaks_path = args.peak_evaluation_summary.parent / f"ig_matched_{args.matched_count}_bins.csv"
        with original_peaks_path.open(newline="", encoding="utf-8") as handle:
            original_peaks = np.asarray(
                [int(row["bin_index"]) for row in csv.DictReader(handle)], dtype=np.int64
            )
        if not np.array_equal(real_peaks, original_peaks):
            raise ValueError("real-input selected peak order was not reproduced")
        correlations = load_correlations(args.input, raw_labels, len(mz), pixels_first, args.chunk_size)
        real_score = score_indices(real_peaks, correlations, len(mz))
        intervention_score = score_indices(intervention_peaks, correlations, len(mz))
        expected_real = evaluation_summary["matched_peak_evaluation"]["methods"]["integrated_gradients"]
        if abs(real_score["mSCF1"] - expected_real["mSCF1"]) > 1e-9:
            raise ValueError("real-input peak score was not reproduced")
        completeness = completeness_summary(ig_diagnostics)
        overlap = len(set(real_peaks.tolist()) & set(intervention_peaks.tolist()))
        key = "shuffled" if args.intervention == "shuffled_input" else "uniform_weights"
        result = {
            "status": "valid" if completeness["passed"] else "inconclusive_ig_completeness",
            "scope": "same-checkpoint, same-GMM, same-pixel and component-target peak-ranking diagnostic",
            "section": section,
            "intervention": args.intervention,
            "reconstruction": reconstruction,
            "checkpoint": str(args.checkpoint),
            "checkpoint_state_sha256": model_sha,
            "original_attribution": str(args.attribution_dir),
            "input_swap_audit": str(args.input_swap_summary),
            "ranking_gmm": str(args.attribution_dir / "gmm_parameters.npz"),
            "reconstruction_audit_gmm_aligned": reconstruction_audit_gmm_aligned,
            "matched_count": args.matched_count,
            "sampling": {"pixels_per_component": len(next(iter(selected.values()))),
                         "components": components, "ig_steps": args.ig_steps},
            "pcc_thresholds": list(THRESHOLDS),
            "real": {"mSCF1": real_score["mSCF1"], "mixed_f1": real_score["mixed_f1"]},
            key: {"mSCF1": intervention_score["mSCF1"], "mixed_f1": intervention_score["mixed_f1"]},
            f"{key}_minus_real_mSCF1": intervention_score["mSCF1"] - real_score["mSCF1"],
            "matched_peak_overlap": overlap,
            f"{key}_ig_completeness": completeness,
            "peak_process_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "peak_pytorch_gpu_allocated_bytes": torch.cuda.max_memory_allocated(device),
            "runtime_seconds": time.perf_counter() - started,
            "limitations": [
                ("The model was trained with real neighbours; shuffled inputs may be out of distribution."
                 if args.intervention == "shuffled_input" else
                 "Uniform weighting is an inference-time intervention on a model trained with learned attention; it is not a retrained uniform model."),
                "The original real-input GMM targets and attribution pixels are held fixed.",
                "For sections where the earlier reconstruction audit fitted its own GMM, its GMM is not the ranking GMM.",
                "Expert masks enter only the post-hoc peak scoring, not training, GMM fitting or ranking.",
                "One training seed per section cannot establish seed-level reproducibility or independent-patient generalisation.",
            ],
        }
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        np.savez(args.output / "rankings.npz", mz=mz, real_indices=real_peaks,
                 **{f"{key}_indices": intervention_peaks},
                 **{f"{key}_component_{component}": values for component, values in intervention_scores.items()})
        save_plot(result, args.output / "matched_peak_f1.png")
        print(json.dumps(result, indent=2), flush=True)
        if not completeness["passed"]:
            raise RuntimeError(f"{key} IG completeness failed; investigate before interpretation")
    finally:
        real.close()
        if shuffled is not None:
            shuffled.close()


if __name__ == "__main__":
    main()

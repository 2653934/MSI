#!/usr/bin/env python3
"""Evaluate augmentation-off/on pilots on matched clean and noisy inputs."""

import argparse
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn.functional as functional
from sklearn.metrics import (
    adjusted_rand_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from evaluate_spatial_loss_pilots import full_neighbour_latent_mse
from evaluate_spatial_msipl_neighbourhoods import load_labels, spatial_probe
from spatial_msipl.evaluation import morans_i
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import poisson_augment_tic_normalized


MODELS = ("augmentation_off", "poisson_trained")
CONDITIONS = ("clean_input", "poisson_noisy_input")
DISPLAY_NAMES = {
    ("augmentation_off", "clean_input"): "Off / clean",
    ("poisson_trained", "clean_input"): "On / clean",
    ("augmentation_off", "poisson_noisy_input"): "Off / noisy",
    ("poisson_trained", "poisson_noisy_input"): "On / noisy",
}
COLOURS = ("#264653", "#2A9D8F", "#E9C46A", "#E76F51")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--baseline-checkpoint", required=True, type=Path)
    parser.add_argument("--poisson-checkpoint", required=True, type=Path)
    parser.add_argument("--baseline-summary", required=True, type=Path)
    parser.add_argument("--poisson-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--effective-count", type=float, default=100000.0)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--noise-seed", type=int, default=20260916)
    return parser.parse_args()


def load_model(checkpoint_path, spectral_dim, device):
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    if int(checkpoint.get("completed_epochs", 0)) != 5:
        raise ValueError(f"{checkpoint_path} is not a complete five-epoch pilot")
    configuration = checkpoint["model_configuration"]
    if int(configuration["spectral_dim"]) != spectral_dim:
        raise ValueError(f"{checkpoint_path} has the wrong spectral dimension")
    if configuration["neighbourhood"]["name"] != "uniform_mean":
        raise ValueError(f"{checkpoint_path} is not a uniform-mean model")
    model = NeighbourhoodSpatialVAE(
        spectral_dim=spectral_dim,
        neighbourhood="uniform_mean",
        hidden_dim=configuration["hidden_dim"],
        latent_dim=configuration["latent_dim"],
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, checkpoint


def validate_training_match(args):
    baseline = json.loads(args.baseline_summary.read_text(encoding="utf-8"))
    poisson = json.loads(args.poisson_summary.read_text(encoding="utf-8"))
    required_equal = (
        "seed",
        "epochs",
        "batch_size",
        "hidden_dim",
        "latent_dim",
        "spatial_lambda",
        "full_dataset",
    )
    differences = {
        name: [baseline["controls"].get(name), poisson["controls"].get(name)]
        for name in required_equal
        if baseline["controls"].get(name) != poisson["controls"].get(name)
    }
    if differences:
        raise ValueError(f"pilot controls do not match: {differences}")
    if baseline["initial_vae_sha256"] != poisson["initial_vae_sha256"]:
        raise ValueError("pilots did not start from identical VAE weights")
    if bool(baseline["controls"].get("poisson_augmentation")):
        raise ValueError("baseline summary unexpectedly enables augmentation")
    if not bool(poisson["controls"].get("poisson_augmentation")):
        raise ValueError("Poisson summary does not enable augmentation")
    if float(poisson["controls"].get("poisson_effective_count")) != float(
        args.effective_count
    ):
        raise ValueError("Poisson training count does not match evaluation count")
    return baseline, poisson


def evaluate_condition(
    model,
    dataset,
    labels,
    batch_size,
    device,
    effective_count,
    noise_seed,
    noisy,
    probe_seed,
):
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    latent = np.empty((len(dataset), model.vae.latent_dim), dtype=np.float32)
    totals = {
        "scaled_categorical_cross_entropy": 0.0,
        "mean_squared_error": 0.0,
        "mean_absolute_error": 0.0,
        "cosine_similarity": 0.0,
        "input_l1": 0.0,
        "input_cosine_similarity": 0.0,
        "pixels": 0,
    }
    epsilon = torch.finfo(torch.float32).eps
    noise_generator = None
    if noisy:
        noise_generator = torch.Generator(device=device).manual_seed(noise_seed)

    with torch.no_grad():
        for batch in loader:
            target = batch["target"].to(device=device, dtype=torch.float32)
            neighbours = batch["neighbours"].to(device=device, dtype=torch.float32)
            neighbour_mask = batch["neighbour_mask"].to(
                device=device, dtype=torch.bool
            )
            if noisy:
                central_input = poisson_augment_tic_normalized(
                    target, effective_count, generator=noise_generator
                )
                neighbour_input = poisson_augment_tic_normalized(
                    neighbours, effective_count, generator=noise_generator
                )
            else:
                central_input = target
                neighbour_input = neighbours

            mean, _, _, _ = model.encode(
                central_input, neighbour_input, neighbour_mask
            )
            reconstruction = model.vae.decode(mean)
            probabilities = reconstruction / reconstruction.sum(
                dim=1, keepdim=True
            ).clamp_min(epsilon)
            probabilities = probabilities.clamp(min=epsilon, max=1.0 - epsilon)

            cross_entropy = -(target * probabilities.log()).sum(dim=1) * target.shape[1]
            mse = (target - probabilities).pow(2).mean(dim=1)
            mae = (target - probabilities).abs().mean(dim=1)
            cosine = functional.cosine_similarity(target, probabilities, dim=1)
            input_l1 = (central_input - target).abs().sum(dim=1)
            input_cosine = functional.cosine_similarity(
                central_input, target, dim=1, eps=1e-12
            )
            indices = batch["index"].numpy()
            latent[indices] = mean.cpu().numpy()
            count = target.shape[0]
            totals["scaled_categorical_cross_entropy"] += float(cross_entropy.sum())
            totals["mean_squared_error"] += float(mse.sum())
            totals["mean_absolute_error"] += float(mae.sum())
            totals["cosine_similarity"] += float(cosine.sum())
            totals["input_l1"] += float(input_l1.sum())
            totals["input_cosine_similarity"] += float(input_cosine.sum())
            totals["pixels"] += count

    pixels = totals.pop("pixels")
    reconstruction = {name: value / pixels for name, value in totals.items()}
    standardized = StandardScaler().fit_transform(latent)
    probe, _, _ = spatial_probe(
        latent,
        labels,
        dataset.x,
        dataset.y,
        rows=4,
        columns=4,
        halo=1,
        seed=probe_seed,
    )
    gmm_labels = GaussianMixture(
        n_components=2, n_init=20, random_state=probe_seed
    ).fit_predict(standardized)
    moran_values = [
        morans_i(standardized[:, dimension], dataset.neighbour_slots)
        for dimension in range(standardized.shape[1])
    ]
    adjacent_mse, adjacent_pairs = full_neighbour_latent_mse(
        latent, dataset.neighbour_slots
    )
    return {
        "evaluation_input": "Poisson-noisy" if noisy else "clean",
        "noise_seed": noise_seed if noisy else None,
        "effective_count": float(effective_count) if noisy else None,
        "pixels": pixels,
        "deterministic_reconstruction": reconstruction,
        "spatial_probe": probe,
        "gmm_two_cluster": {
            "adjusted_rand_index": float(adjusted_rand_score(labels, gmm_labels)),
            "normalized_mutual_information": float(
                normalized_mutual_info_score(labels, gmm_labels)
            ),
        },
        "label_silhouette": float(silhouette_score(standardized, labels)),
        "morans_i": {
            "per_latent_dimension": moran_values,
            "mean": float(np.mean(moran_values)),
        },
        "full_neighbour_latent_mse": adjacent_mse,
        "full_neighbour_pairs": adjacent_pairs,
    }


def relative_change(new, reference):
    return 100.0 * (new - reference) / reference


def build_decision_summary(results):
    off_clean = results["augmentation_off"]["clean_input"]
    on_clean = results["poisson_trained"]["clean_input"]
    off_noisy = results["augmentation_off"]["poisson_noisy_input"]
    on_noisy = results["poisson_trained"]["poisson_noisy_input"]
    metric = "mean_squared_error"
    clean_change = relative_change(
        on_clean["deterministic_reconstruction"][metric],
        off_clean["deterministic_reconstruction"][metric],
    )
    noisy_change = relative_change(
        on_noisy["deterministic_reconstruction"][metric],
        off_noisy["deterministic_reconstruction"][metric],
    )
    off_degradation = relative_change(
        off_noisy["deterministic_reconstruction"][metric],
        off_clean["deterministic_reconstruction"][metric],
    )
    on_degradation = relative_change(
        on_noisy["deterministic_reconstruction"][metric],
        on_clean["deterministic_reconstruction"][metric],
    )
    return {
        "poisson_model_clean_mse_change_percent_vs_off": clean_change,
        "poisson_model_noisy_mse_change_percent_vs_off": noisy_change,
        "off_model_noisy_mse_degradation_percent": off_degradation,
        "poisson_model_noisy_mse_degradation_percent": on_degradation,
        "predeclared_reconstruction_rule": {
            "maximum_clean_mse_regression_percent": 1.0,
            "minimum_noisy_mse_improvement_percent": 1.0,
            "clean_rule_passed": clean_change <= 1.0,
            "noisy_rule_passed": noisy_change <= -1.0,
            "both_passed": clean_change <= 1.0 and noisy_change <= -1.0,
        },
        "interpretation_guardrail": (
            "The rule is a development gate, not a statistical significance test. "
            "Representation metrics and the one-section exploratory scope must also be reviewed."
        ),
    }


def save_figure(results, output):
    order = [
        ("augmentation_off", "clean_input"),
        ("poisson_trained", "clean_input"),
        ("augmentation_off", "poisson_noisy_input"),
        ("poisson_trained", "poisson_noisy_input"),
    ]
    labels = [DISPLAY_NAMES[item] for item in order]
    x = np.arange(len(order))
    baseline_mse = results["augmentation_off"]["clean_input"][
        "deterministic_reconstruction"
    ]["mean_squared_error"]
    panels = (
        (
            [
                relative_change(
                    results[model][condition]["deterministic_reconstruction"][
                        "mean_squared_error"
                    ],
                    baseline_mse,
                )
                for model, condition in order
            ],
            "Reconstruction MSE",
            "% versus off / clean (lower is better)",
        ),
        (
            [
                results[model][condition]["deterministic_reconstruction"][
                    "cosine_similarity"
                ]
                for model, condition in order
            ],
            "Reconstruction cosine",
            "Higher is better",
        ),
        (
            [
                results[model][condition]["spatial_probe"]["balanced_accuracy"]
                for model, condition in order
            ],
            "Spatially blocked probe",
            "Balanced accuracy",
        ),
        (
            [
                results[model][condition]["gmm_two_cluster"][
                    "adjusted_rand_index"
                ]
                for model, condition in order
            ],
            "Unsupervised GMM agreement",
            "Adjusted Rand index",
        ),
        (
            [results[model][condition]["label_silhouette"] for model, condition in order],
            "Label separation",
            "Silhouette score",
        ),
        (
            [results[model][condition]["morans_i"]["mean"] for model, condition in order],
            "Latent spatial autocorrelation",
            "Mean Moran's I",
        ),
    )
    figure, axes = plt.subplots(2, 3, figsize=(17, 10))
    for axis, (values, title, ylabel) in zip(axes.flat, panels):
        bars = axis.bar(x, values, color=COLOURS)
        axis.set_xticks(x, labels, rotation=18, ha="right")
        axis.set_title(title)
        axis.set_ylabel(ylabel)
        axis.grid(axis="y", alpha=0.2)
        axis.bar_label(bars, fmt="%.4g", padding=3, fontsize=8)
    figure.suptitle("Five-epoch Poisson augmentation pilot: clean and noisy evaluation")
    figure.text(
        0.5,
        0.01,
        "GBM108_positive, seed 1; deterministic encoder mean; noisy inputs use an independent fixed evaluation draw at N=100,000.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 0.96))
    figure.savefig(output / "poisson_pilot_comparison.png", dpi=220, bbox_inches="tight")
    plt.close(figure)


def main():
    args = parse_arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; Poisson evaluation stopped")
    if args.batch_size < 1 or args.effective_count <= 0:
        raise ValueError("batch size and effective count must be positive")
    baseline_summary, poisson_summary = validate_training_match(args)

    args.output.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda")
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        labels = load_labels(args.input, len(dataset))
        checkpoints = {
            "augmentation_off": args.baseline_checkpoint,
            "poisson_trained": args.poisson_checkpoint,
        }
        results = {}
        for model_name in MODELS:
            model, checkpoint = load_model(
                checkpoints[model_name], dataset.n_mz, device
            )
            results[model_name] = {}
            for condition in CONDITIONS:
                started = time.perf_counter()
                result = evaluate_condition(
                    model=model,
                    dataset=dataset,
                    labels=labels,
                    batch_size=args.batch_size,
                    device=device,
                    effective_count=args.effective_count,
                    noise_seed=args.noise_seed,
                    noisy=condition == "poisson_noisy_input",
                    probe_seed=args.seed,
                )
                result["evaluation_seconds"] = float(time.perf_counter() - started)
                results[model_name][condition] = result
                print(json.dumps({model_name: {condition: result}}, indent=2), flush=True)
            results[model_name]["checkpoint"] = str(checkpoints[model_name])
            results[model_name]["completed_epochs"] = int(
                checkpoint["completed_epochs"]
            )
            del model
            torch.cuda.empty_cache()
    finally:
        dataset.close()

    decision = build_decision_summary(results)
    save_figure(results, args.output)
    comparison = {
        "dataset": "GBM108_positive",
        "scope": "five-epoch development-only Poisson augmentation gate",
        "design": {
            "training_seed": args.seed,
            "evaluation_noise_seed": args.noise_seed,
            "effective_count": args.effective_count,
            "latent_representation": "deterministic encoder mean",
            "decoder_target": "clean TIC-normalized central spectrum",
            "same_noisy_inputs_for_both_models": True,
            "spatial_probe": "4x4 tile holdout with one-pixel halo",
            "initial_vae_sha256": baseline_summary["initial_vae_sha256"],
            "matched_training_controls": True,
        },
        "training": {
            "augmentation_off": baseline_summary,
            "poisson_trained": poisson_summary,
        },
        "evaluations": results,
        "decision_summary": decision,
        "status": "complete",
    }
    (args.output / "comparison.json").write_text(
        json.dumps(comparison, indent=2), encoding="utf-8"
    )
    print(json.dumps({"decision_summary": decision}, indent=2), flush=True)
    print(f"Poisson pilot evaluation complete: {args.output}", flush=True)


if __name__ == "__main__":
    main()

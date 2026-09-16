#!/usr/bin/env python3
"""Pilot nonlinear m/z attribution through the full Spatial-msiPL encoder."""

import argparse
import csv
import hashlib
import json
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader

from spatial_msipl.attribution import (
    first_layer_l2_importance,
    gmm_posterior,
    integrated_gradients_cluster_posterior,
)
from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset


CLUSTER_COLOURS = ("#457B9D", "#E76F51", "#6D597A", "#2A9D8F")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--gmm-components", type=int, default=2)
    parser.add_argument("--gmm-n-init", type=int, default=20)
    parser.add_argument("--attribution-per-cluster", type=int, default=12)
    parser.add_argument("--faithfulness-per-cluster", type=int, default=32)
    parser.add_argument("--ig-steps", type=int, default=64)
    parser.add_argument("--ig-internal-batch-size", type=int, default=8)
    parser.add_argument("--deletion-budgets", type=int, nargs="+", default=[32, 128, 512])
    parser.add_argument("--random-repeats", type=int, default=10)
    parser.add_argument("--top-candidates", type=int, default=50)
    parser.add_argument("--seed", type=int, default=1)
    return parser.parse_args()


def state_sha256(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def load_model(path, spectral_dim, device):
    checkpoint = torch.load(path, map_location="cpu")
    if int(checkpoint.get("completed_epochs", 0)) != 100:
        raise ValueError("attribution requires the complete 100-epoch checkpoint")
    configuration = checkpoint["model_configuration"]
    neighbourhood = configuration["neighbourhood"]
    if int(configuration["spectral_dim"]) != spectral_dim:
        raise ValueError("checkpoint and dataset spectral dimensions differ")
    if neighbourhood["name"] != "uniform_mean":
        raise ValueError("this controlled pilot requires the retained uniform-mean model")
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


def encode_all(model, dataset, batch_size, device):
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    latent = np.empty((len(dataset), model.vae.latent_dim), dtype=np.float32)
    central_sum = np.zeros(dataset.n_mz, dtype=np.float64)
    with torch.no_grad():
        for batch in loader:
            central = batch["target"].to(device=device, dtype=torch.float32)
            neighbours = batch["neighbours"].to(device=device, dtype=torch.float32)
            mask = batch["neighbour_mask"].to(device=device, dtype=torch.bool)
            indices = batch["index"].numpy()
            latent[indices] = model.encode(central, neighbours, mask)[0].cpu().numpy()
            central_sum += central.double().sum(dim=0).cpu().numpy()
    return latent, (central_sum / len(dataset)).astype(np.float32)


def torch_gmm_parameters(scaler, gmm, device):
    convert = lambda value: torch.as_tensor(value, dtype=torch.float32, device=device)
    return {
        "scaler_mean": convert(scaler.mean_),
        "scaler_scale": convert(scaler.scale_),
        "mixture_weights": convert(gmm.weights_),
        "component_means": convert(gmm.means_),
        "precision_cholesky": convert(gmm.precisions_cholesky_),
    }


def sample_as_tensors(dataset, index, device):
    sample = dataset[int(index)]
    central = torch.as_tensor(sample["target"], dtype=torch.float32, device=device)[None]
    neighbours = torch.as_tensor(
        sample["neighbours"], dtype=torch.float32, device=device
    )[None]
    mask = torch.as_tensor(
        sample["neighbour_mask"], dtype=torch.bool, device=device
    )[None]
    return central, neighbours, mask


def baseline_for(mean_spectrum, neighbours, mask):
    central = mean_spectrum[None]
    neighbour = torch.zeros_like(neighbours)
    neighbour[mask] = mean_spectrum
    return central, neighbour


def choose_disjoint_samples(labels, n_attribution, n_faithfulness, seed):
    rng = np.random.default_rng(seed)
    selected = {}
    for component in np.unique(labels):
        candidates = np.flatnonzero(labels == component)
        required = n_attribution + n_faithfulness
        if len(candidates) < required:
            raise ValueError(
                f"component {component} has {len(candidates)} pixels; {required} required"
            )
        shuffled = rng.permutation(candidates)
        selected[int(component)] = {
            "attribution": np.sort(shuffled[:n_attribution]),
            "faithfulness": np.sort(shuffled[n_attribution:required]),
        }
    return selected


def gather_samples(dataset, indices, device):
    samples = [dataset[int(index)] for index in indices]
    central = torch.as_tensor(
        np.stack([sample["target"] for sample in samples]),
        dtype=torch.float32,
        device=device,
    )
    neighbours = torch.as_tensor(
        np.stack([sample["neighbours"] for sample in samples]),
        dtype=torch.float32,
        device=device,
    )
    mask = torch.as_tensor(
        np.stack([sample["neighbour_mask"] for sample in samples]),
        dtype=torch.bool,
        device=device,
    )
    return central, neighbours, mask


def target_posteriors(model, central, neighbours, mask, components, gmm_parameters):
    with torch.no_grad():
        latent = model.encode(central, neighbours, mask)[0]
        posterior = gmm_posterior(latent, **gmm_parameters)
        return posterior.gather(1, components[:, None]).squeeze(1)


def replace_bins(central, neighbours, mask, mean_spectrum, bins):
    changed_central = central.clone()
    changed_neighbours = neighbours.clone()
    changed_central[:, bins] = mean_spectrum[bins]
    replacement = mean_spectrum[bins].view(1, 1, -1)
    changed_neighbours[:, :, bins] = torch.where(
        mask.unsqueeze(2), replacement, changed_neighbours[:, :, bins]
    )
    return changed_central, changed_neighbours


def deletion_faithfulness(
    model,
    dataset,
    selected,
    rankings,
    first_layer_ranking,
    mean_spectrum,
    gmm_parameters,
    budgets,
    random_repeats,
    seed,
    device,
):
    rng = np.random.default_rng(seed)
    records = []
    for component, split in selected.items():
        indices = split["faithfulness"]
        central, neighbours, mask = gather_samples(dataset, indices, device)
        components = torch.full(
            (len(indices),), int(component), dtype=torch.long, device=device
        )
        original = target_posteriors(
            model, central, neighbours, mask, components, gmm_parameters
        )
        for budget in budgets:
            if budget < 1 or budget > dataset.n_mz:
                raise ValueError(f"invalid deletion budget: {budget}")
            method_drops = {}
            for method, ranking in (
                ("integrated_gradients", rankings[component]),
                ("first_layer_l2", first_layer_ranking),
            ):
                bins = np.asarray(ranking[:budget], dtype=np.int64)
                changed_central, changed_neighbours = replace_bins(
                    central, neighbours, mask, mean_spectrum, bins
                )
                changed = target_posteriors(
                    model,
                    changed_central,
                    changed_neighbours,
                    mask,
                    components,
                    gmm_parameters,
                )
                method_drops[method] = (original - changed).cpu().numpy()

            random_drops = []
            for _ in range(random_repeats):
                bins = rng.choice(dataset.n_mz, size=budget, replace=False)
                changed_central, changed_neighbours = replace_bins(
                    central, neighbours, mask, mean_spectrum, bins
                )
                changed = target_posteriors(
                    model,
                    changed_central,
                    changed_neighbours,
                    mask,
                    components,
                    gmm_parameters,
                )
                random_drops.append((original - changed).cpu().numpy())
            random_values = np.concatenate(random_drops)
            records.append(
                {
                    "component": int(component),
                    "removed_bins": int(budget),
                    "pixels": int(len(indices)),
                    "integrated_gradients_mean_posterior_drop": float(
                        np.mean(method_drops["integrated_gradients"])
                    ),
                    "first_layer_l2_mean_posterior_drop": float(
                        np.mean(method_drops["first_layer_l2"])
                    ),
                    "random_mean_posterior_drop": float(np.mean(random_values)),
                    "random_standard_deviation": float(np.std(random_values)),
                }
            )
    return records


def spatial_image(values, x, y):
    image = np.full((int(y.max()), int(x.max())), np.nan)
    image[y - 1, x - 1] = values
    return image


def save_gmm_figure(labels, confidence, x, y, output):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    cluster_cmap = matplotlib.colors.ListedColormap(CLUSTER_COLOURS[: len(np.unique(labels))])
    cluster_cmap.set_bad("#ECECEC")
    confidence_cmap = matplotlib.colormaps["viridis"].copy()
    confidence_cmap.set_bad("#ECECEC")
    axes[0].imshow(
        spatial_image(labels, x, y), cmap=cluster_cmap, interpolation="nearest"
    )
    axes[0].set_title("GMM assignment (labels are arbitrary)")
    shown = axes[1].imshow(
        spatial_image(confidence, x, y),
        cmap=confidence_cmap,
        vmin=0.5,
        vmax=1.0,
        interpolation="nearest",
    )
    axes[1].set_title("Assigned-cluster posterior")
    fig.colorbar(shown, ax=axes[1], fraction=0.046)
    for axis in axes:
        axis.set_xlabel("X")
        axis.set_ylabel("Y")
        axis.set_aspect("equal")
    fig.suptitle("Uniform-mean Spatial-msiPL: latent GMM target", fontsize=14)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_attribution_figure(mz, aggregate, output, top_n=20):
    components = sorted(aggregate)
    fig, axes = plt.subplots(len(components), 1, figsize=(12, 5 * len(components)))
    axes = np.atleast_1d(axes)
    for axis, component in zip(axes, components):
        score = aggregate[component]["combined_absolute_mean"]
        top = np.argsort(score)[-top_n:]
        order = top[np.argsort(score[top])]
        positions = np.arange(len(order))
        axis.barh(positions, score[order], color=CLUSTER_COLOURS[component])
        axis.set_yticks(positions, [f"{mz[index]:.4f}" for index in order])
        axis.set_xlabel("Mean absolute IG contribution")
        axis.set_ylabel("m/z")
        axis.set_title(f"GMM component {component}: top {top_n} nonlinear features")
    fig.suptitle("Integrated Gradients through central and neighbourhood pathways", fontsize=14)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def save_faithfulness_figure(records, output):
    components = sorted({record["component"] for record in records})
    fig, axes = plt.subplots(1, len(components), figsize=(6 * len(components), 4.8), squeeze=False)
    for axis, component in zip(axes[0], components):
        subset = sorted(
            (record for record in records if record["component"] == component),
            key=lambda record: record["removed_bins"],
        )
        budgets = [0] + [record["removed_bins"] for record in subset]
        for field, name, colour in (
            ("integrated_gradients_mean_posterior_drop", "Integrated Gradients", "#457B9D"),
            ("first_layer_l2_mean_posterior_drop", "First-layer L2", "#E76F51"),
            ("random_mean_posterior_drop", "Random", "#8D99AE"),
        ):
            values = [0.0] + [record[field] for record in subset]
            axis.plot(budgets, values, marker="o", label=name, color=colour)
        axis.axhline(0.0, color="black", linewidth=0.7)
        axis.set_title(f"GMM component {component}")
        axis.set_xlabel("m/z bins replaced by section mean")
        axis.set_ylabel("Assigned-posterior drop")
        axis.legend()
    fig.suptitle("Held-out deletion faithfulness (higher drop is stronger evidence)", fontsize=14)
    fig.tight_layout()
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main():
    args = parse_arguments()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the attribution pilot")
    device = torch.device("cuda")
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    model, checkpoint = load_model(args.checkpoint, dataset.n_mz, device)
    latent, mean_spectrum_np = encode_all(model, dataset, args.batch_size, device)
    scaler = StandardScaler().fit(latent)
    standardized = scaler.transform(latent)
    gmm = GaussianMixture(
        n_components=args.gmm_components,
        covariance_type="full",
        n_init=args.gmm_n_init,
        random_state=args.seed,
    ).fit(standardized)
    labels = gmm.predict(standardized)
    sklearn_posterior = gmm.predict_proba(standardized)
    confidence = sklearn_posterior[np.arange(len(dataset)), labels]
    gmm_parameters = torch_gmm_parameters(scaler, gmm, device)
    with torch.no_grad():
        torch_posterior = gmm_posterior(
            torch.as_tensor(latent, dtype=torch.float32, device=device),
            **gmm_parameters,
        ).cpu().numpy()
    posterior_max_difference = float(np.max(np.abs(torch_posterior - sklearn_posterior)))
    if posterior_max_difference > 1e-4:
        raise RuntimeError(
            f"differentiable posterior disagrees with sklearn: {posterior_max_difference}"
        )

    selected = choose_disjoint_samples(
        labels,
        args.attribution_per_cluster,
        args.faithfulness_per_cluster,
        args.seed + 700,
    )
    mean_spectrum = torch.as_tensor(mean_spectrum_np, device=device)
    aggregate = {}
    diagnostics = []
    for component, split in selected.items():
        central_signed = []
        context_signed = []
        central_absolute = []
        context_absolute = []
        combined_absolute = []
        for index in split["attribution"]:
            central, neighbours, mask = sample_as_tensors(dataset, index, device)
            central_baseline, neighbour_baseline = baseline_for(
                mean_spectrum, neighbours, mask
            )
            central_attr, neighbour_attr, check = (
                integrated_gradients_cluster_posterior(
                    model,
                    central,
                    neighbours,
                    mask,
                    central_baseline,
                    neighbour_baseline,
                    target_component=component,
                    gmm_parameters=gmm_parameters,
                    steps=args.ig_steps,
                    internal_batch_size=args.ig_internal_batch_size,
                )
            )
            central_values = central_attr[0].detach().cpu().numpy()
            neighbour_values = neighbour_attr[0].detach().cpu().numpy()
            central_signed.append(central_values)
            context_signed.append(neighbour_values.sum(axis=0))
            central_absolute.append(np.abs(central_values))
            context_absolute.append(np.abs(neighbour_values).sum(axis=0))
            combined_absolute.append(
                np.abs(central_values) + np.abs(neighbour_values).sum(axis=0)
            )
            check.update(
                {
                    "pixel_index": int(index),
                    "x": int(dataset.x[index]),
                    "y": int(dataset.y[index]),
                    "component": int(component),
                    "assigned_posterior": float(confidence[index]),
                }
            )
            diagnostics.append(check)
        aggregate[component] = {
            "central_signed_mean": np.mean(central_signed, axis=0),
            "context_signed_mean": np.mean(context_signed, axis=0),
            "central_absolute_mean": np.mean(central_absolute, axis=0),
            "context_absolute_mean": np.mean(context_absolute, axis=0),
            "combined_absolute_mean": np.mean(combined_absolute, axis=0),
        }

    first_central, first_context = first_layer_l2_importance(model)
    first_central = first_central.cpu().numpy()
    first_context = first_context.cpu().numpy()
    first_combined = first_central + first_context
    rankings = {
        component: np.argsort(values["combined_absolute_mean"])[::-1]
        for component, values in aggregate.items()
    }
    first_layer_ranking = np.argsort(first_combined)[::-1]
    faithfulness = deletion_faithfulness(
        model,
        dataset,
        selected,
        rankings,
        first_layer_ranking,
        mean_spectrum,
        gmm_parameters,
        sorted(set(args.deletion_budgets)),
        args.random_repeats,
        args.seed + 1700,
        device,
    )

    residuals = np.asarray(
        [abs(record["completeness_residual"]) for record in diagnostics]
    )
    normalized_residuals = np.asarray(
        [
            abs(record["completeness_residual"])
            / max(abs(record["score_delta"]), 1e-4)
            for record in diagnostics
        ]
    )
    completeness_passed = bool(
        np.all(np.isfinite(residuals))
        and np.median(normalized_residuals) <= 0.05
        and np.percentile(normalized_residuals, 95) <= 0.15
    )

    np.save(args.output / "latent_mean.npy", latent)
    np.savez(
        args.output / "coordinates_and_gmm.npz",
        x=dataset.x,
        y=dataset.y,
        component=labels,
        assigned_posterior=confidence,
    )
    np.savez(
        args.output / "gmm_parameters.npz",
        scaler_mean=scaler.mean_,
        scaler_scale=scaler.scale_,
        mixture_weights=gmm.weights_,
        component_means=gmm.means_,
        covariances=gmm.covariances_,
        precision_cholesky=gmm.precisions_cholesky_,
    )
    attribution_arrays = {
        f"component_{component}_{name}": values
        for component, component_values in aggregate.items()
        for name, values in component_values.items()
    }
    np.savez(
        args.output / "attributions.npz",
        mz=dataset.mz_values,
        first_layer_central_l2=first_central,
        first_layer_context_l2=first_context,
        first_layer_combined_l2=first_combined,
        **attribution_arrays,
    )

    with (args.output / "top_mz_candidates.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "component",
                "rank",
                "bin_index",
                "mz",
                "combined_absolute_ig",
                "central_absolute_ig",
                "context_absolute_ig",
                "central_signed_ig",
                "context_signed_ig",
                "first_layer_combined_l2",
            ),
        )
        writer.writeheader()
        for component, ranking in rankings.items():
            for rank, index in enumerate(ranking[: args.top_candidates], start=1):
                values = aggregate[component]
                writer.writerow(
                    {
                        "component": component,
                        "rank": rank,
                        "bin_index": int(index),
                        "mz": float(dataset.mz_values[index]),
                        "combined_absolute_ig": float(values["combined_absolute_mean"][index]),
                        "central_absolute_ig": float(values["central_absolute_mean"][index]),
                        "context_absolute_ig": float(values["context_absolute_mean"][index]),
                        "central_signed_ig": float(values["central_signed_mean"][index]),
                        "context_signed_ig": float(values["context_signed_mean"][index]),
                        "first_layer_combined_l2": float(first_combined[index]),
                    }
                )

    save_gmm_figure(
        labels,
        confidence,
        dataset.x,
        dataset.y,
        args.output / "gmm_cluster_target.png",
    )
    save_attribution_figure(
        dataset.mz_values,
        aggregate,
        args.output / "top_nonlinear_mz_attributions.png",
    )
    save_faithfulness_figure(
        faithfulness, args.output / "deletion_faithfulness.png"
    )

    summary = {
        "attribution_version": 1,
        "status": "valid_pilot" if completeness_passed else "needs_more_ig_steps",
        "dataset": str(args.input),
        "checkpoint": str(args.checkpoint),
        "model_state_sha256": state_sha256(model),
        "completed_training_epochs": int(checkpoint["completed_epochs"]),
        "model_configuration": checkpoint["model_configuration"],
        "pixels": int(len(dataset)),
        "spectral_bins": int(dataset.n_mz),
        "gmm": {
            "components": args.gmm_components,
            "covariance_type": "full",
            "n_init": args.gmm_n_init,
            "seed": args.seed,
            "component_counts": {
                str(component): int(np.count_nonzero(labels == component))
                for component in np.unique(labels)
            },
            "differentiable_posterior_max_absolute_difference": posterior_max_difference,
            "label_note": "component numbers are arbitrary and were not fitted to the expert mask",
        },
        "integrated_gradients": {
            "baseline": "section-wide mean TIC-normalised spectrum for centre and every valid neighbour",
            "baseline_reason": "a physically plausible in-distribution reference; missing neighbour slots remain zero and masked",
            "target": "posterior of the pixel's assigned GMM component",
            "steps": args.ig_steps,
            "integration": "trapezoidal rule including both endpoints",
            "attribution_pixels_per_component": args.attribution_per_cluster,
            "central_context_combination": "per-bin |central IG| + sum over valid neighbour slots of |neighbour IG|",
            "selection_seed": args.seed + 700,
            "completeness": {
                "passed": completeness_passed,
                "median_absolute_residual": float(np.median(residuals)),
                "maximum_absolute_residual": float(np.max(residuals)),
                "median_normalized_residual": float(np.median(normalized_residuals)),
                "percentile_95_normalized_residual": float(
                    np.percentile(normalized_residuals, 95)
                ),
            },
            "per_pixel_diagnostics": diagnostics,
        },
        "first_layer_comparator": {
            "method": "L2 norm over hidden units for the central and aggregated-context halves of encoder_dense",
            "combination": "central L2 + context L2",
            "interpretation": "linear comparator only; not the primary nonlinear explanation",
        },
        "faithfulness": {
            "held_out_from_attribution": True,
            "pixels_per_component": args.faithfulness_per_cluster,
            "replacement": "selected bins in centre and all valid neighbours are replaced by section-mean values without renormalising other bins",
            "budgets": sorted(set(args.deletion_budgets)),
            "random_repeats": args.random_repeats,
            "seed": args.seed + 1700,
            "records": faithfulness,
        },
        "runtime_seconds": time.perf_counter() - started,
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Post-hoc check of whether frozen real attention favours same-label neighbours."""

import argparse
import gc
import json
from pathlib import Path

import numpy as np

from audit_attention_weights import checkpoint_root, median_summary


def same_label_mass(weights, valid, source_labels, centre_labels):
    """Compare attention mass on same-label sources with equal-weight mass."""
    weights = np.asarray(weights, dtype=np.float64)
    valid = np.asarray(valid, dtype=bool)
    source_labels = np.asarray(source_labels)
    centre_labels = np.asarray(centre_labels).reshape(-1)
    if (weights.ndim != 2 or weights.shape != valid.shape or
            weights.shape != source_labels.shape or len(centre_labels) != len(weights)):
        raise ValueError("incompatible weight, slot and label shapes")
    counts = valid.sum(axis=1)
    if np.any(counts < 2) or np.any(weights < 0):
        raise ValueError("each centre needs at least two valid nonnegative weights")
    if not np.allclose((weights * valid).sum(axis=1), 1, atol=1e-4):
        raise ValueError("valid attention weights must sum to one")
    same = valid & (source_labels == centre_labels[:, None])
    learned = np.sum(weights * same, axis=1)
    uniform = same.sum(axis=1) / counts
    return learned, uniform


def evaluate(checkpoint_path, dataset, labels, indices, seed):
    import torch

    from spatial_msipl.neighbourhood import AttentionNeighbourhood
    from spatial_msipl.preprocessing import checkpoint_input_spec

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    signature = checkpoint.get("resume_signature", {})
    configuration = checkpoint.get("model_configuration", {}).get("neighbourhood", {})
    if checkpoint.get("completed_epochs") != 100 or checkpoint_input_spec(checkpoint)["context_mode"] != "measured":
        raise ValueError(f"epoch/context mismatch: {checkpoint_path}")
    if signature.get("seed") != seed or Path(signature["data_source"]).resolve() != dataset.path:
        raise ValueError(f"seed/input mismatch: {checkpoint_path}")
    if configuration.get("name") != "attention" or configuration.get("input_scale_name") != "sqrt_bins":
        raise ValueError(f"attention configuration mismatch: {checkpoint_path}")
    projection = checkpoint["model_state_dict"]["aggregator.projection.weight"]
    bias = checkpoint["model_state_dict"]["aggregator.projection.bias"]
    if projection.shape != (configuration["attention_dim"], dataset.n_mz):
        raise ValueError(f"projection shape mismatch: {checkpoint_path}")
    aggregator = AttentionNeighbourhood(dataset.n_mz, configuration["attention_dim"], "sqrt_bins")
    aggregator.projection.load_state_dict({"weight": projection, "bias": bias})
    aggregator.eval()
    del checkpoint, projection, bias
    gc.collect()

    learned_mass, uniform_mass = [], []
    with torch.no_grad():
        for start in range(0, len(indices), 4):
            batch_indices = indices[start:start + 4]
            samples = [dataset[int(i)] for i in batch_indices]
            central = torch.from_numpy(np.stack([sample["target"] for sample in samples]))
            neighbours = torch.from_numpy(np.stack([sample["neighbours"] for sample in samples]))
            mask = torch.from_numpy(np.stack([sample["neighbour_mask"] for sample in samples]))
            _, weights = aggregator(central, neighbours, mask)
            slots = dataset.neighbour_slots[batch_indices]
            a, u = same_label_mass(
                weights.numpy(), mask.numpy(), labels[np.maximum(slots, 0)], labels[batch_indices]
            )
            learned_mass.extend(a.tolist())
            uniform_mass.extend(u.tolist())
    learned_mass, uniform_mass = np.asarray(learned_mass), np.asarray(uniform_mass)
    excess = learned_mass - uniform_mass
    return {
        "checkpoint": str(checkpoint_path),
        "sampled_boundary_centres": len(indices),
        "same_label_mass_attention": median_summary(learned_mass),
        "same_label_mass_uniform": median_summary(uniform_mass),
        "paired_excess_attention_minus_uniform": median_summary(excess),
        "mean_paired_excess": float(np.mean(excess)),
        "fraction_positive_excess": float(np.mean(excess > 0)),
        "fraction_excess_above_0_05": float(np.mean(excess > 0.05)),
        "per_pixel": [
            {"measured_index": int(index), "attention_mass": float(a),
             "uniform_mass": float(u), "excess": float(d)}
            for index, a, u, d in zip(indices, learned_mass, uniform_mass, excess)
        ],
    }


def main():
    import h5py

    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--boundary-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    previous = json.loads(args.boundary_summary.read_text(encoding="utf-8"))
    if previous.get("status") != "valid" or previous.get("section") != args.input.stem:
        raise ValueError("boundary summary does not validate this section")
    if Path(previous["input"]).resolve() != args.input.resolve():
        raise ValueError("boundary summary input HDF5 differs")

    with h5py.File(args.input, "r") as handle:
        labels = np.asarray(handle["Class_Label"]).reshape(-1)
    dataset = CachedH5SpatialContextDataset(args.input, include_neighbourhood=True, window_size=3)
    try:
        if len(labels) != len(dataset):
            raise ValueError("label count differs from measured spectra")
        indices = np.asarray(previous["selected_measured_indices"]["boundary"], dtype=np.int64)
        if len(indices) < 1 or np.any(indices < 0) or np.any(indices >= len(dataset)):
            raise ValueError("invalid frozen boundary sample")
        slots = dataset.neighbour_slots[indices]
        if np.any(np.sum(slots >= 0, axis=1) < 2):
            raise ValueError("boundary sample includes centre with fewer than two neighbours")
        if not np.all(np.any(
                (slots >= 0) & (labels[np.maximum(slots, 0)] != labels[indices, None]), axis=1
        )):
            raise ValueError("frozen boundary sample no longer crosses a label edge")

        results = {}
        for seed in (1, 2, 3):
            checkpoint = checkpoint_root(args.input.stem, seed, "real_attention") / "checkpoint.pt"
            if not checkpoint.is_file():
                raise FileNotFoundError(checkpoint)
            results[str(seed)] = evaluate(checkpoint, dataset, labels, indices, seed)
            print(f"{args.input.stem} seed {seed}: median same-label excess "
                  f"{results[str(seed)]['paired_excess_attention_minus_uniform']['median']:.5f}", flush=True)
    finally:
        dataset.close()
        del dataset
        gc.collect()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    for seed, colour in zip((1, 2, 3), ("#287c64", "#7857a6", "#c57a38")):
        pixels = results[str(seed)]["per_pixel"]
        axes[0].scatter(
            [row["uniform_mass"] for row in pixels], [row["attention_mass"] for row in pixels],
            s=18, alpha=.55, color=colour, label=f"Seed {seed}"
        )
    axes[0].plot([0, 1], [0, 1], color="#555555", linestyle="--", linewidth=1)
    axes[0].set(xlim=(0, 1), ylim=(0, 1), xlabel="Equal-mean same-label mass",
                ylabel="Attention same-label mass", title="Each point is a boundary centre")
    axes[0].legend()
    axes[1].boxplot(
        [[row["excess"] for row in results[str(seed)]["per_pixel"]] for seed in (1, 2, 3)],
        showfliers=False
    )
    axes[1].set_xticks([1, 2, 3], ["Seed 1", "Seed 2", "Seed 3"])
    axes[1].axhline(0, color="#555555", linestyle="--", linewidth=1)
    axes[1].set(ylabel="Attention minus equal-mean same-label mass",
                title="Positive means same-label preference")
    fig.suptitle(f"{args.input.stem}: learned weighting at labelled boundaries")
    fig.tight_layout()

    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "same_label_attention_mass.png", dpi=180)
    plt.close(fig)
    summary = {
        "status": "valid", "section": args.input.stem, "input": str(args.input),
        "source_boundary_summary": str(args.boundary_summary),
        "scope": "post-hoc label agreement of frozen real-attention weights on preselected boundary centres",
        "labels_used_only_after_weight_inference": True,
        "same_boundary_centres_all_seeds": True,
        "sampled_boundary_centres": len(indices),
        "results": results,
        "interpretation_limit": (
            "Same-label preference is descriptive, not a measure of boundary accuracy or "
            "peak quality. Pixels within one section are spatially dependent. A negative "
            "excess can also be meaningful if the model learns cross-boundary contrast."
        ),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"status": "valid", "section": args.input.stem, "output": str(args.output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()

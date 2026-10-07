#!/usr/bin/env python3
"""Post-hoc boundary/interior diagnosis of frozen attention, without mask training."""

import argparse
import gc
import json
from pathlib import Path

import numpy as np

from audit_attention_vs_uniform import context_distances
from audit_attention_weights import checkpoint_root, median_summary, weight_statistics


def select_groups(slots, labels, per_class, seed):
    """Return fixed class-balanced measured centres with >=2 neighbours."""
    slots = np.asarray(slots)
    labels = np.asarray(labels).reshape(-1)
    if slots.ndim != 2 or len(slots) != len(labels) or per_class < 1:
        raise ValueError("slots, labels, and per-class sample size are incompatible")
    valid = slots >= 0
    boundary = np.any(valid & (labels[np.maximum(slots, 0)] != labels[:, None]), axis=1)
    eligible = valid.sum(axis=1) >= 2
    rng = np.random.default_rng(seed)
    selected = {}
    for group, group_mask in (("boundary", boundary), ("interior", ~boundary)):
        indices = []
        for label in np.unique(labels):
            candidates = np.flatnonzero(group_mask & eligible & (labels == label))
            if len(candidates):
                indices.extend(rng.choice(candidates, size=min(per_class, len(candidates)), replace=False).tolist())
        if not indices:
            raise ValueError(f"no eligible {group} centres")
        selected[group] = np.asarray(sorted(indices), dtype=np.int64)
    population = {
        "boundary": int(np.sum(boundary & eligible)),
        "interior": int(np.sum((~boundary) & eligible)),
    }
    return selected, population


def evaluate(checkpoint_path, dataset, groups, arm, seed):
    import torch

    from spatial_msipl.neighbourhood import AttentionNeighbourhood
    from spatial_msipl.preprocessing import checkpoint_input_spec

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    signature = checkpoint.get("resume_signature", {})
    config = checkpoint.get("model_configuration", {}).get("neighbourhood", {})
    expected_mode = "measured" if arm == "real_attention" else "shuffled"
    if checkpoint.get("completed_epochs") != 100 or checkpoint_input_spec(checkpoint)["context_mode"] != expected_mode:
        raise ValueError(f"epoch/context mismatch: {checkpoint_path}")
    if signature.get("seed") != seed or Path(signature["data_source"]).resolve() != dataset.path:
        raise ValueError(f"seed/input mismatch: {checkpoint_path}")
    if config.get("name") != "attention" or config.get("input_scale_name") != "sqrt_bins":
        raise ValueError(f"attention configuration mismatch: {checkpoint_path}")
    if expected_mode == "shuffled" and signature.get("context_permutation_sha256") != dataset.context_permutation_sha256:
        raise ValueError(f"frozen shuffle mismatch: {checkpoint_path}")
    projection = checkpoint["model_state_dict"]["aggregator.projection.weight"]
    bias = checkpoint["model_state_dict"]["aggregator.projection.bias"]
    if projection.shape != (config["attention_dim"], dataset.n_mz):
        raise ValueError(f"projection shape mismatch: {checkpoint_path}")
    aggregator = AttentionNeighbourhood(dataset.n_mz, config["attention_dim"], "sqrt_bins")
    aggregator.projection.load_state_dict({"weight": projection, "bias": bias})
    aggregator.eval()
    del checkpoint, projection, bias
    gc.collect()

    output = {}
    with torch.no_grad():
        for group, indices in groups.items():
            all_weights, all_masks, distances, cosines = [], [], [], []
            for start in range(0, len(indices), 4):
                samples = [dataset[int(i)] for i in indices[start:start + 4]]
                central = torch.from_numpy(np.stack([s["target"] for s in samples]))
                neighbours = torch.from_numpy(np.stack([s["neighbours"] for s in samples]))
                mask = torch.from_numpy(np.stack([s["neighbour_mask"] for s in samples]))
                context, weights = aggregator(central, neighbours, mask)
                uniform = (neighbours * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True)
                uniform = uniform / uniform.sum(dim=1, keepdim=True).clamp_min(torch.finfo(uniform.dtype).eps)
                d, c = context_distances(context.numpy(), uniform.numpy())
                all_weights.append(weights.numpy())
                all_masks.append(mask.numpy())
                distances.extend(d.tolist())
                cosines.extend(c.tolist())
            statistics = weight_statistics(np.concatenate(all_weights), np.concatenate(all_masks))
            if not np.all(np.isfinite(distances)) or not np.all(np.isfinite(cosines)):
                raise ValueError(f"non-finite {group} context metrics")
            output[group] = {
                "sampled_centres": len(indices),
                "normalized_attention_entropy": median_summary(statistics["normalized_entropy"]),
                "effective_neighbours": median_summary(statistics["effective_neighbours"]),
                "half_l1_attention_vs_uniform": median_summary(distances),
                "cosine_attention_vs_uniform": median_summary(cosines),
            }
    return output


def main():
    import h5py

    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-swap-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--per-class", type=int, default=16)
    parser.add_argument("--sample-seed", type=int, default=20261007)
    args = parser.parse_args()
    if args.per_class < 1:
        parser.error("per-class must be positive")
    provenance = json.loads(args.input_swap_summary.read_text(encoding="utf-8"))
    if provenance.get("status") != "valid" or provenance.get("section") != args.input.stem:
        raise ValueError("input-swap provenance does not validate this section")
    if Path(provenance["input"]).resolve() != args.input.resolve():
        raise ValueError("input-swap source HDF5 differs")

    with h5py.File(args.input, "r") as handle:
        if "Class_Label" not in handle:
            raise KeyError("Class_Label is required only for post-hoc grouping")
        labels = np.asarray(handle["Class_Label"]).reshape(-1)

    results, groups, population = {}, None, None
    for arm, mode in (("real_attention", "measured"), ("shuffled_attention", "shuffled")):
        dataset = CachedH5SpatialContextDataset(
            args.input, include_neighbourhood=True, window_size=3,
            context_mode=mode, context_seed=int(provenance["shuffle_seed"]) if mode == "shuffled" else None,
        )
        try:
            if len(labels) != len(dataset):
                raise ValueError("label count differs from measured spectra")
            if mode == "shuffled" and dataset.context_permutation_sha256 != provenance["shuffle_source_slots_sha256"]:
                raise ValueError("frozen shuffle differs from input-swap audit")
            selected, counts = select_groups(dataset.neighbour_slots, labels, args.per_class, args.sample_seed)
            if groups is None:
                groups, population = selected, counts
            elif any(not np.array_equal(groups[key], selected[key]) for key in groups):
                raise ValueError("selected centres changed between arms")
            results[arm] = {}
            for seed in (1, 2, 3):
                checkpoint = checkpoint_root(args.input.stem, seed, arm) / "checkpoint.pt"
                if not checkpoint.is_file():
                    raise FileNotFoundError(checkpoint)
                results[arm][str(seed)] = evaluate(checkpoint, dataset, groups, arm, seed)
                print(f"{args.input.stem} {arm} seed {seed}:",
                      {group: round(results[arm][str(seed)][group]["half_l1_attention_vs_uniform"]["median"], 5)
                       for group in groups}, flush=True)
        finally:
            dataset.close()
            del dataset
            gc.collect()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for axis, group in zip(axes, ("boundary", "interior")):
        for offset, arm, colour, label in ((-.18, "real_attention", "#287c64", "Real"),
                                           (.18, "shuffled_attention", "#7857a6", "Shuffled")):
            values = [results[arm][str(seed)][group]["half_l1_attention_vs_uniform"]["median"] for seed in (1, 2, 3)]
            axis.bar(np.arange(3) + offset, values, width=.35, color=colour, label=label)
        axis.set_xticks(np.arange(3), ["Seed 1", "Seed 2", "Seed 3"])
        axis.set_ylabel("Median context half-L1 distance")
        axis.set_title(group.title())
        axis.legend()
    fig.suptitle(f"{args.input.stem}: attention versus equal mean, by tissue group")
    fig.tight_layout()

    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "boundary_context_delta.png", dpi=180)
    plt.close(fig)
    summary = {
        "status": "valid", "section": args.input.stem, "input": str(args.input),
        "scope": "post-hoc mask-defined boundary/interior diagnosis of frozen attention; no labels used in model or attention weights",
        "sample_seed": args.sample_seed, "max_centres_per_group_and_class": args.per_class,
        "eligible_population": population,
        "selected_measured_indices": {key: value.tolist() for key, value in groups.items()},
        "same_centres_both_arms_all_seeds": True,
        "results": results,
        "interpretation_limit": (
            "Class-balanced sampled centres and multiple pixels per section are not independent "
            "patients. A boundary difference would be descriptive, not proof that attention "
            "improves reconstruction or peak selection."
        ),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"status": "valid", "section": args.input.stem, "output": str(args.output)}, indent=2), flush=True)


if __name__ == "__main__":
    main()

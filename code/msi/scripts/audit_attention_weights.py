#!/usr/bin/env python3
"""Compare frozen real/shuffled attention weights without labels or retraining."""

import argparse
import gc
import json
from pathlib import Path

import numpy as np


def weight_statistics(weights, valid_mask):
    """Return per-pixel normalized entropy, effective slots, and largest weight."""
    weights = np.asarray(weights, dtype=np.float64)
    mask = np.asarray(valid_mask, dtype=bool)
    if weights.shape != mask.shape or weights.ndim != 2:
        raise ValueError("weights and mask must be matching pixel-by-slot matrices")
    counts = mask.sum(axis=1)
    if np.any(counts < 2) or np.any(weights < 0):
        raise ValueError("each sampled centre needs at least two valid nonnegative weights")
    if np.any(np.abs((weights * mask).sum(axis=1) - 1) > 1e-4):
        raise ValueError("valid attention weights must sum to one")
    safe = np.where(mask & (weights > 0), weights, 1)
    entropy = -(np.where(mask, weights, 0) * np.log(safe)).sum(axis=1)
    return {
        "normalized_entropy": entropy / np.log(counts),
        "effective_neighbours": np.exp(entropy),
        "max_weight": np.max(np.where(mask, weights, 0), axis=1),
        "valid_neighbours": counts,
    }


def median_summary(values):
    return {"median": float(np.median(values)), "p10": float(np.quantile(values, .1)),
            "p90": float(np.quantile(values, .9))}


def checkpoint_root(section, seed, arm):
    campaign = "attention_context" if seed == 1 else "attention_context_seed_stability"
    return Path("/datasets/zsuliman/msi_checkpoints/spatial_msipl") / campaign / f"{section}_seed{seed}" / arm


def evaluate_checkpoint(checkpoint_path, dataset, indices, arm, seed):
    import torch

    from spatial_msipl.neighbourhood import AttentionNeighbourhood
    from spatial_msipl.preprocessing import checkpoint_input_spec

    checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    spec = checkpoint_input_spec(checkpoint)
    expected_mode = "measured" if arm == "real_attention" else "shuffled"
    config = checkpoint.get("model_configuration", {}).get("neighbourhood", {})
    signature = checkpoint.get("resume_signature", {})
    if checkpoint.get("completed_epochs") != 100 or spec["context_mode"] != expected_mode:
        raise ValueError(f"epoch/context mismatch: {checkpoint_path}")
    if config.get("name") != "attention" or config.get("input_scale_name") != "sqrt_bins":
        raise ValueError(f"attention configuration mismatch: {checkpoint_path}")
    if signature.get("seed") != seed or signature.get("dataset_size") != len(dataset):
        raise ValueError(f"seed or dataset size mismatch: {checkpoint_path}")
    if spec["context_mode"] == "shuffled":
        if signature.get("context_permutation_sha256") != dataset.context_permutation_sha256:
            raise ValueError(f"shuffled source mapping mismatch: {checkpoint_path}")
    if Path(signature["data_source"]).resolve() != dataset.path:
        raise ValueError(f"checkpoint input HDF5 mismatch: {checkpoint_path}")

    state = checkpoint["model_state_dict"]
    projection = state["aggregator.projection.weight"]
    bias = state["aggregator.projection.bias"]
    if projection.shape != (config["attention_dim"], dataset.n_mz):
        raise ValueError(f"attention projection shape mismatch: {checkpoint_path}")
    aggregator = AttentionNeighbourhood(
        dataset.n_mz, attention_dim=config["attention_dim"], input_scale="sqrt_bins"
    )
    aggregator.projection.load_state_dict({"weight": projection, "bias": bias})
    aggregator.eval()
    del checkpoint, state, projection, bias
    gc.collect()

    all_weights, all_masks = [], []
    with torch.no_grad():
        for start in range(0, len(indices), 4):
            samples = [dataset[int(i)] for i in indices[start:start + 4]]
            central = torch.from_numpy(np.stack([s["target"] for s in samples]))
            neighbours = torch.from_numpy(np.stack([s["neighbours"] for s in samples]))
            mask = torch.from_numpy(np.stack([s["neighbour_mask"] for s in samples]))
            _, weights = aggregator(central, neighbours, mask)
            all_weights.append(weights.numpy())
            all_masks.append(mask.numpy())
    statistics = weight_statistics(np.concatenate(all_weights), np.concatenate(all_masks))
    return {
        "checkpoint": str(checkpoint_path),
        "sampled_centres": len(indices),
        "normalized_entropy": median_summary(statistics["normalized_entropy"]),
        "effective_neighbours": median_summary(statistics["effective_neighbours"]),
        "max_weight": median_summary(statistics["max_weight"]),
        "valid_neighbours": median_summary(statistics["valid_neighbours"]),
    }


def main():
    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-swap-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=128)
    parser.add_argument("--sample-seed", type=int, default=20261007)
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("sample-size must be positive")
    provenance = json.loads(args.input_swap_summary.read_text(encoding="utf-8"))
    if provenance.get("status") != "valid" or provenance.get("section") != args.input.stem:
        raise ValueError("input-swap provenance does not validate this section")
    if Path(provenance["input"]).resolve() != args.input.resolve():
        raise ValueError("input-swap source HDF5 differs")

    results = {}
    reference_indices = None
    for arm, mode in (("real_attention", "measured"), ("shuffled_attention", "shuffled")):
        dataset = CachedH5SpatialContextDataset(
            args.input, include_neighbourhood=True, window_size=3,
            context_mode=mode, context_seed=int(provenance["shuffle_seed"]) if mode == "shuffled" else None,
        )
        try:
            if mode == "shuffled" and dataset.context_permutation_sha256 != provenance["shuffle_source_slots_sha256"]:
                raise ValueError("frozen shuffle differs from input-swap audit")
            eligible = np.flatnonzero(np.sum(dataset.neighbour_slots >= 0, axis=1) >= 2)
            if reference_indices is None:
                reference_indices = np.sort(np.random.default_rng(args.sample_seed).choice(
                    eligible, size=min(args.sample_size, len(eligible)), replace=False
                ))
            elif not np.all(np.isin(reference_indices, eligible)):
                raise ValueError("sampled centres changed between arms")
            results[arm] = {}
            for seed in (1, 2, 3):
                path = checkpoint_root(args.input.stem, seed, arm) / "checkpoint.pt"
                if not path.is_file():
                    raise FileNotFoundError(path)
                results[arm][str(seed)] = evaluate_checkpoint(path, dataset, reference_indices, arm, seed)
                print(f"{args.input.stem} {arm} seed {seed}: {results[arm][str(seed)]['normalized_entropy']['median']:.4f} median normalized entropy", flush=True)
        finally:
            dataset.close()
            del dataset
            gc.collect()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    locations = np.arange(3)
    for offset, arm, colour, label in ((-.18, "real_attention", "#287c64", "Real"),
                                       (.18, "shuffled_attention", "#7857a6", "Shuffled")):
        values = [results[arm][str(seed)]["normalized_entropy"]["median"] for seed in (1, 2, 3)]
        ax.bar(locations + offset, values, width=.35, color=colour, label=label)
    ax.set_xticks(locations, ["Seed 1", "Seed 2", "Seed 3"])
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Median normalized attention entropy (1 = uniform)")
    ax.set_title(f"{args.input.stem}: how selective is frozen attention?")
    ax.legend()
    fig.tight_layout()

    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "attention_entropy.png", dpi=180)
    plt.close(fig)
    summary = {
        "status": "valid", "scope": "sampled frozen attention weights; label-free, no retraining",
        "section": args.input.stem, "input": str(args.input),
        "input_swap_summary": str(args.input_swap_summary),
        "sample_seed": args.sample_seed, "sampled_centres": len(reference_indices),
        "same_centres_both_arms_all_seeds": True, "results": results,
        "interpretation_limit": (
            "Entropy measures whether weights are concentrated, not whether spatial context "
            "caused better reconstruction or peak selection. Pixels are not independent patients."
        ),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

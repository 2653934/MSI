#!/usr/bin/env python3
"""Measure how far frozen attention contexts depart from uniform neighbour means."""

import argparse
import gc
import json
from pathlib import Path

import numpy as np

from audit_attention_weights import checkpoint_root, median_summary


def context_distances(attention, uniform):
    attention = np.asarray(attention, dtype=np.float64)
    uniform = np.asarray(uniform, dtype=np.float64)
    if attention.shape != uniform.shape or attention.ndim != 2:
        raise ValueError("contexts must be matching pixel-by-bin matrices")
    half_l1 = 0.5 * np.abs(attention - uniform).sum(axis=1)
    numerator = np.sum(attention * uniform, axis=1)
    denominator = np.linalg.norm(attention, axis=1) * np.linalg.norm(uniform, axis=1)
    cosine = np.divide(numerator, denominator, out=np.full_like(numerator, np.nan), where=denominator > 0)
    return half_l1, cosine


def evaluate(checkpoint_path, dataset, indices, arm, seed):
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

    distances, cosines = [], []
    with torch.no_grad():
        for start in range(0, len(indices), 4):
            samples = [dataset[int(i)] for i in indices[start:start + 4]]
            central = torch.from_numpy(np.stack([s["target"] for s in samples]))
            neighbours = torch.from_numpy(np.stack([s["neighbours"] for s in samples]))
            mask = torch.from_numpy(np.stack([s["neighbour_mask"] for s in samples]))
            attention, _ = aggregator(central, neighbours, mask)
            counts = mask.sum(dim=1, keepdim=True)
            uniform = (neighbours * mask.unsqueeze(-1)).sum(dim=1) / counts.clamp_min(1)
            uniform = uniform / uniform.sum(dim=1, keepdim=True).clamp_min(torch.finfo(uniform.dtype).eps)
            d, c = context_distances(attention.numpy(), uniform.numpy())
            distances.extend(d.tolist())
            cosines.extend(c.tolist())
    distances, cosines = np.asarray(distances), np.asarray(cosines)
    if not np.all(np.isfinite(distances)) or not np.all(np.isfinite(cosines)):
        raise ValueError("sample contains zero or non-finite contexts")
    return {
        "checkpoint": str(checkpoint_path),
        "sampled_centres": len(indices),
        "half_l1_attention_vs_uniform": median_summary(distances),
        "cosine_attention_vs_uniform": median_summary(cosines),
    }


def main():
    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-swap-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--sample-size", type=int, default=64)
    parser.add_argument("--sample-seed", type=int, default=20261007)
    args = parser.parse_args()
    if args.sample_size < 1:
        parser.error("sample-size must be positive")
    provenance = json.loads(args.input_swap_summary.read_text(encoding="utf-8"))
    if provenance.get("status") != "valid" or provenance.get("section") != args.input.stem:
        raise ValueError("input-swap provenance does not validate this section")
    if Path(provenance["input"]).resolve() != args.input.resolve():
        raise ValueError("input-swap source HDF5 differs")

    results, before_after = {}, {}
    chosen = None
    project = Path.home() / "msi"
    for arm, mode in (("real_attention", "measured"), ("shuffled_attention", "shuffled")):
        dataset = CachedH5SpatialContextDataset(
            args.input, include_neighbourhood=True, window_size=3,
            context_mode=mode, context_seed=int(provenance["shuffle_seed"]) if mode == "shuffled" else None,
        )
        try:
            if mode == "shuffled" and dataset.context_permutation_sha256 != provenance["shuffle_source_slots_sha256"]:
                raise ValueError("frozen shuffle differs from input-swap audit")
            eligible = np.flatnonzero(np.sum(dataset.neighbour_slots >= 0, axis=1) >= 2)
            if chosen is None:
                chosen = np.sort(np.random.default_rng(args.sample_seed).choice(
                    eligible, size=min(args.sample_size, len(eligible)), replace=False
                ))
            elif not np.all(np.isin(chosen, eligible)):
                raise ValueError("sampled centres changed between arms")
            results[arm], before_after[arm] = {}, {}
            for seed in (1, 2, 3):
                campaign = "spatial_attention_context" if seed == 1 else "spatial_attention_context_seed_stability"
                training = project / "results/experiments" / campaign / f"{args.input.stem}_seed{seed}" / arm / "summary.json"
                frozen = json.loads(training.read_text(encoding="utf-8"))
                diagnostics = frozen["attention_diagnostics"]
                if frozen.get("status") != "complete" or diagnostics.get("before_training") is None or diagnostics.get("after_training") is None:
                    raise ValueError(f"missing paired initial/final training diagnostics: {training}")
                before_after[arm][str(seed)] = {
                    "source": str(training),
                    "training_diagnostic_centres": len(diagnostics["indices"]),
                    "initial_entropy_mean": diagnostics["before_training"]["entropy_mean"],
                    "trained_entropy_mean": diagnostics["after_training"]["entropy_mean"],
                }
                checkpoint = checkpoint_root(args.input.stem, seed, arm) / "checkpoint.pt"
                if not checkpoint.is_file():
                    raise FileNotFoundError(checkpoint)
                results[arm][str(seed)] = evaluate(checkpoint, dataset, chosen, arm, seed)
                value = results[arm][str(seed)]["half_l1_attention_vs_uniform"]["median"]
                print(f"{args.input.stem} {arm} seed {seed}: half-L1 {value:.5f}", flush=True)
        finally:
            dataset.close()
            del dataset
            gc.collect()

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    positions = np.arange(3)
    for offset, arm, colour, label in ((-.18, "real_attention", "#287c64", "Real"),
                                       (.18, "shuffled_attention", "#7857a6", "Shuffled")):
        entropy_change = [before_after[arm][str(s)]["trained_entropy_mean"] - before_after[arm][str(s)]["initial_entropy_mean"] for s in (1, 2, 3)]
        delta = [results[arm][str(s)]["half_l1_attention_vs_uniform"]["median"] for s in (1, 2, 3)]
        axes[0].bar(positions + offset, entropy_change, width=.35, color=colour, label=label)
        axes[1].bar(positions + offset, delta, width=.35, color=colour, label=label)
    axes[0].set_ylabel("Trained minus initial attention entropy")
    axes[0].set_title("Training changed the weights")
    axes[1].set_ylabel("Median half-L1 distance")
    axes[1].set_title("Frozen context: attention vs equal mean")
    for axis in axes:
        axis.set_xticks(positions, ["Seed 1", "Seed 2", "Seed 3"])
        axis.legend()
    fig.suptitle(args.input.stem)
    fig.tight_layout()

    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "attention_vs_uniform.png", dpi=180)
    plt.close(fig)
    summary = {
        "status": "valid", "section": args.input.stem, "input": str(args.input),
        "scope": "label-free sampled frozen context difference plus existing paired initial/final training diagnostics",
        "sample_seed": args.sample_seed, "sampled_context_centres": len(chosen),
        "same_context_centres_both_arms_all_seeds": True,
        "initial_and_trained_diagnostics": before_after,
        "frozen_context_vs_uniform": results,
        "interpretation_limit": (
            "Initial/final entropy was measured on each seed's 16 training diagnostic centres, "
            "not the 64 centres used for frozen context distance. Context distance does not "
            "establish a cause of reconstruction or peak-score differences."
        ),
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a matched gradient-training pilot for all three neighbourhood variants."""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import set_random_seed, train_vae


VARIANTS = ("uniform_mean", "depthwise", "attention")


def state_sha256(module):
    """Hash named tensor values so matched initialization can be audited."""
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint-output", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--attention-dim", type=int, default=8)
    parser.add_argument("--maximum-samples", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()

    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    results = {}
    initial_hashes = {}
    selected_indices = {}
    for variant in VARIANTS:
        set_random_seed(args.seed, include_cuda=args.device == "cuda")
        model = NeighbourhoodSpatialVAE(
            spectral_dim=dataset.n_mz,
            neighbourhood=variant,
            hidden_dim=args.hidden_dim,
            latent_dim=args.latent_dim,
            attention_dim=args.attention_dim,
        )
        initial_hashes[variant] = state_sha256(model.vae)
        print(json.dumps({"starting_variant": variant}), flush=True)
        metadata, history = train_vae(
            model=model,
            dataset=dataset,
            output_directory=args.output / variant,
            checkpoint_directory=args.checkpoint_output / variant,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            maximum_samples=args.maximum_samples,
            seed=args.seed,
            device=args.device,
            experiment_metadata={
                "purpose": "matched gradient smoke test, not scientific comparison",
                "neighbourhood_variant": variant,
                "spatial_lambda": 0.0,
                "poisson_augmentation": False,
            },
        )
        selected_indices[variant] = metadata["selected_indices"]
        results[variant] = {
            "initial_vae_sha256": initial_hashes[variant],
            "parameter_count": metadata["parameter_count"],
            "final_losses": history[-1],
            "result_directory": str(args.output / variant),
            "checkpoint_directory": str(args.checkpoint_output / variant),
        }

    dataset.close()
    identical_initial_vae = len(set(initial_hashes.values())) == 1
    if not identical_initial_vae:
        raise ValueError(f"VAE initializations differ: {initial_hashes}")
    identical_selected_pixels = all(
        indices == selected_indices[VARIANTS[0]]
        for indices in selected_indices.values()
    )
    if not identical_selected_pixels:
        raise ValueError("selected training pixels differ between variants")

    summary = {
        "input": str(dataset.path),
        "purpose": "matched gradient smoke test, not scientific comparison",
        "controls": {
            "same_selected_pixels": identical_selected_pixels,
            "same_batch_order": True,
            "same_initial_vae_weights": identical_initial_vae,
            "spatial_lambda": 0.0,
            "poisson_augmentation": False,
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "maximum_samples": args.maximum_samples,
        },
        "variants": results,
        "status": "valid",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Measure production-shape Spatial-msiPL memory and throughput on one GPU."""

import argparse
import gc
import hashlib
import json
from pathlib import Path

import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import set_random_seed, train_vae


VARIANTS = ("uniform_mean", "depthwise", "attention")


def state_sha256(module):
    digest = hashlib.sha256()
    for name, tensor in sorted(module.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--attention-dim", type=int, default=8)
    parser.add_argument("--maximum-samples", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable on this node; no benchmark was run. "
            "Resubmit without selecting a specific node."
        )
    device = "cuda"
    # Initialize the CUDA context before per-variant timing begins.
    torch.zeros(1, device=device).sum()
    torch.cuda.synchronize()

    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    results = {}
    initial_hashes = {}
    selected_indices = {}
    for variant in VARIANTS:
        set_random_seed(args.seed, include_cuda=True)
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
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            maximum_samples=args.maximum_samples,
            seed=args.seed,
            device=device,
            experiment_metadata={
                "purpose": "production-shape GPU feasibility benchmark",
                "neighbourhood_variant": variant,
                "spatial_lambda": 0.0,
                "poisson_augmentation": False,
            },
            save_checkpoint=False,
        )
        selected_indices[variant] = metadata["selected_indices"]
        projected_epoch_seconds = (
            metadata["training_seconds"]
            * len(dataset)
            / metadata["samples_per_epoch"]
        )
        results[variant] = {
            "initial_vae_sha256": initial_hashes[variant],
            "parameter_count": metadata["parameter_count"],
            "training_seconds": metadata["training_seconds"],
            "samples_per_second": metadata["overall_samples_per_second"],
            "peak_gpu_memory_allocated_bytes": metadata[
                "peak_gpu_memory_allocated_bytes"
            ],
            "peak_gpu_memory_reserved_bytes": metadata[
                "peak_gpu_memory_reserved_bytes"
            ],
            "projected_full_dataset_epoch_seconds": projected_epoch_seconds,
            "projected_100_epoch_hours": projected_epoch_seconds * 100 / 3600,
            "final_losses": history[-1],
        }
        del model
        gc.collect()
        torch.cuda.empty_cache()

    dataset.close()
    same_initial_vae = len(set(initial_hashes.values())) == 1
    same_selected_pixels = all(
        indices == selected_indices[VARIANTS[0]]
        for indices in selected_indices.values()
    )
    if not same_initial_vae or not same_selected_pixels:
        raise ValueError("matched benchmark controls were not preserved")

    summary = {
        "input": str(dataset.path),
        "purpose": "capacity planning only; not scientific model comparison",
        "pytorch_version": torch.__version__,
        "pytorch_cuda_version": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0),
        "controls": {
            "same_selected_pixels": same_selected_pixels,
            "same_initial_vae_weights": same_initial_vae,
            "spatial_lambda": 0.0,
            "poisson_augmentation": False,
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "maximum_samples": args.maximum_samples,
            "hidden_dim": args.hidden_dim,
            "latent_dim": args.latent_dim,
        },
        "notes": [
            "Projections extrapolate one short run and are not final runtime measurements.",
            "No model checkpoints are saved by this benchmark.",
            "Loss differences must not be used to rank neighbourhood variants.",
        ],
        "variants": results,
        "status": "valid",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()


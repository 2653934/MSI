#!/usr/bin/env python3
"""Run one full-section Spatial-msiPL neighbourhood stability experiment."""

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
    """Hash the shared VAE weights so matched initialization is auditable."""
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
    parser.add_argument("--variant", required=True, choices=VARIANTS)
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--attention-dim", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable on this node; no training was run. "
            "Resubmit the failed variant without selecting a specific node."
        )

    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        set_random_seed(args.seed, include_cuda=True)
        model = NeighbourhoodSpatialVAE(
            spectral_dim=dataset.n_mz,
            neighbourhood=args.variant,
            hidden_dim=args.hidden_dim,
            latent_dim=args.latent_dim,
            attention_dim=args.attention_dim,
        )
        initial_vae_hash = state_sha256(model.vae)
        metadata, history = train_vae(
            model=model,
            dataset=dataset,
            output_directory=args.output,
            checkpoint_directory=args.checkpoint_output,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            maximum_samples=None,
            seed=args.seed,
            device="cuda",
            experiment_metadata={
                "purpose": "five-epoch full-section stability test",
                "neighbourhood_variant": args.variant,
                "spatial_lambda": 0.0,
                "poisson_augmentation": False,
                "initial_vae_sha256": initial_vae_hash,
            },
        )
    finally:
        dataset.close()

    first_loss = history[0]["total_loss"]
    final_loss = history[-1]["total_loss"]
    summary = {
        "input": str(dataset.path),
        "purpose": "training stability check, not final scientific comparison",
        "variant": args.variant,
        "initial_vae_sha256": initial_vae_hash,
        "controls": {
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "hidden_dim": args.hidden_dim,
            "latent_dim": args.latent_dim,
            "attention_dim": args.attention_dim,
            "spatial_lambda": 0.0,
            "poisson_augmentation": False,
            "full_dataset": True,
        },
        "samples_per_epoch": metadata["samples_per_epoch"],
        "dataset_size": metadata["dataset_size"],
        "training_seconds": metadata["training_seconds"],
        "peak_gpu_memory_allocated_bytes": metadata[
            "peak_gpu_memory_allocated_bytes"
        ],
        "first_total_loss": first_loss,
        "final_total_loss": final_loss,
        "total_loss_change_percent": 100.0 * (final_loss - first_loss) / first_loss,
        "history": history,
        "checkpoint": metadata["checkpoint"],
        "status": "complete",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Run a short real-data smoke test of the Spatial-msiPL VAE."""

import argparse
import json
from pathlib import Path

import torch

from spatial_msipl.model import SpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import set_random_seed, train_vae


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--checkpoint-output", type=Path)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--hidden-dim", type=int, default=32)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--maximum-samples", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--device", choices=("cpu", "cuda", "auto"), default="cpu")
    args = parser.parse_args()

    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but PyTorch cannot access a GPU")

    # Seed before constructing the model so its initial weights are reproducible.
    set_random_seed(args.seed, include_cuda=device == "cuda")
    dataset = H5SpatialContextDataset(args.input)
    model = SpatialVAE(
        spectral_dim=dataset.n_mz,
        hidden_dim=args.hidden_dim,
        latent_dim=args.latent_dim,
    )
    print(
        json.dumps(
            {
                "purpose": "architecture smoke test, not a scientific training result",
                "input": str(dataset.path),
                "model_configuration": model.configuration(),
                "maximum_samples": args.maximum_samples,
                "device": device,
            },
            indent=2,
        ),
        flush=True,
    )
    metadata, history = train_vae(
        model=model,
        dataset=dataset,
        output_directory=args.output,
        checkpoint_directory=args.checkpoint_output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        maximum_samples=args.maximum_samples,
        seed=args.seed,
        device=device,
    )
    dataset.close()
    print(json.dumps({"metadata": metadata, "history": history}, indent=2), flush=True)


if __name__ == "__main__":
    main()

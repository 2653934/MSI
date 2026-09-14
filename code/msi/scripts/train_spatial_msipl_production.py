#!/usr/bin/env python3
"""Train one restartable 100-epoch Spatial-msiPL neighbourhood baseline."""

import argparse
import hashlib
import json
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset

from check_spatial_attention_scaling import measure
from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import set_random_seed, train_vae


VARIANTS = ("central_only", "uniform_mean", "depthwise", "attention")


def state_sha256(module):
    """Hash the shared VAE initialization for cross-run verification."""
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
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--hidden-dim", type=int, default=512)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--attention-dim", type=int, default=8)
    parser.add_argument(
        "--attention-input-scale",
        choices=("unit", "sqrt_bins", "spectral_bins"),
        default="spectral_bins",
    )
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--checkpoint-interval", type=int, default=5)
    parser.add_argument("--resume-checkpoint", type=Path)
    args = parser.parse_args()

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable on this node; no training was run. "
            "Resubmit the failed variant."
        )

    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        set_random_seed(args.seed, include_cuda=True)
        if args.variant == "central_only":
            model = CentralOnlyVAE(
                spectral_dim=dataset.n_mz,
                hidden_dim=args.hidden_dim,
                latent_dim=args.latent_dim,
            )
        else:
            model = NeighbourhoodSpatialVAE(
                spectral_dim=dataset.n_mz,
                neighbourhood=args.variant,
                hidden_dim=args.hidden_dim,
                latent_dim=args.latent_dim,
                attention_dim=args.attention_dim,
                attention_input_scale=args.attention_input_scale,
            )
        initial_vae_hash = state_sha256(model.vae)
        attention_diagnostics_before = None
        diagnostic_indices = None
        if args.variant == "attention":
            diagnostic_indices = sorted(
                torch.randperm(
                    len(dataset),
                    generator=torch.Generator().manual_seed(args.seed),
                )[:16].tolist()
            )
            diagnostic_batch = next(
                iter(DataLoader(Subset(dataset, diagnostic_indices), batch_size=16))
            )
            diagnostic_batch = {
                key: diagnostic_batch[key].to("cuda")
                for key in ("target", "neighbours", "neighbour_mask")
            }
            model.to("cuda")
            with torch.no_grad():
                attention_diagnostics_before = measure(model, diagnostic_batch)
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
                "purpose": "production neighbourhood baseline",
                "neighbourhood_variant": args.variant,
                "spatial_lambda": 0.0,
                "poisson_augmentation": False,
                "initial_vae_sha256": initial_vae_hash,
                "attention_input_scale": args.attention_input_scale,
            },
            checkpoint_interval=args.checkpoint_interval,
            resume_checkpoint=args.resume_checkpoint,
        )
        attention_diagnostics_after = None
        if args.variant == "attention":
            with torch.no_grad():
                attention_diagnostics_after = measure(model, diagnostic_batch)
    finally:
        dataset.close()

    first_loss = history[0]["total_loss"]
    final_loss = history[-1]["total_loss"]
    summary = {
        "input": str(dataset.path),
        "purpose": (
            "production reconstruction baseline"
            if args.variant == "central_only"
            else "production neighbourhood baseline"
        ),
        "variant": args.variant,
        "initial_vae_sha256": initial_vae_hash,
        "controls": {
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "hidden_dim": args.hidden_dim,
            "latent_dim": args.latent_dim,
            "attention_dim": args.attention_dim,
            "attention_input_scale": args.attention_input_scale,
            "spatial_lambda": 0.0,
            "poisson_augmentation": False,
            "full_dataset": True,
        },
        "samples_per_epoch": metadata["samples_per_epoch"],
        "dataset_size": metadata["dataset_size"],
        "training_seconds": metadata["training_seconds"],
        "resumed_from_checkpoint": metadata["resumed_from_checkpoint"],
        "resumed_from_epoch": metadata["resumed_from_epoch"],
        "peak_gpu_memory_allocated_bytes": metadata[
            "peak_gpu_memory_allocated_bytes"
        ],
        "first_total_loss": first_loss,
        "final_total_loss": final_loss,
        "total_loss_change_percent": 100.0 * (final_loss - first_loss) / first_loss,
        "history": history,
        "checkpoint": metadata["checkpoint"],
        "attention_diagnostics": {
            "indices": diagnostic_indices,
            "before_training": attention_diagnostics_before,
            "after_training": attention_diagnostics_after,
        } if args.variant == "attention" else None,
        "status": "complete",
    }
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Train one restartable 100-epoch Spatial-msiPL neighbourhood baseline."""

import argparse
import hashlib
import json
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset

from check_spatial_attention_scaling import measure
from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
)
from spatial_msipl.training import set_random_seed, train_vae


VARIANTS = (
    "central_only", "zero_context", "uniform_mean", "shuffled_uniform",
    "depthwise", "attention", "attention_shuffled",
)


def variant_input_spec(variant):
    """Keep model type and neighbour assignment explicit for control runs."""
    return (
        {"shuffled_uniform": "uniform_mean", "attention_shuffled": "attention"}.get(variant, variant),
        "shuffled" if variant in ("shuffled_uniform", "attention_shuffled") else "measured",
    )


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
    parser.add_argument("--window-size", type=int, choices=(1, 3, 5), default=3)
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
    parser.add_argument("--spatial-lambda", type=float, default=0.0)
    parser.add_argument(
        "--spatial-loss-scale",
        choices=("unit", "spectral_bins"),
        default="unit",
        help="Scale applied to latent spatial MSE before multiplying by lambda.",
    )
    parser.add_argument(
        "--poisson-effective-count",
        type=float,
        help=(
            "Enable training-input Poisson augmentation using this explicit "
            "effective ion count; the clean central spectrum remains the target."
        ),
    )
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--context-seed", type=int, default=1,
                        help="Global measured-pixel permutation seed for shuffled context arms.")
    parser.add_argument("--checkpoint-interval", type=int, default=5)
    parser.add_argument("--resume-checkpoint", type=Path)
    parser.add_argument(
        "--cache-spectra",
        action="store_true",
        help="Opt in to one in-memory float32 HDF5 read; default remains streaming.",
    )
    args = parser.parse_args()
    if args.variant == "depthwise" and args.window_size != 3:
        parser.error("depthwise currently supports only the historical 3x3 window")

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA is unavailable on this node; no training was run. "
            "Resubmit the failed variant."
        )

    script_started_at = time.perf_counter()
    dataset_type = (
        CachedH5SpatialContextDataset if args.cache_spectra else H5SpatialContextDataset
    )
    neighbourhood_name, context_mode = variant_input_spec(args.variant)
    dataset = dataset_type(
        args.input, include_neighbourhood=True, window_size=args.window_size,
        context_mode=context_mode,
        context_seed=args.context_seed if context_mode == "shuffled" else None,
    )
    dataset_load_seconds = time.perf_counter() - script_started_at
    try:
        spatial_loss_scale = (
            dataset.n_mz if args.spatial_loss_scale == "spectral_bins" else 1.0
        )
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
                neighbourhood=neighbourhood_name,
                hidden_dim=args.hidden_dim,
                latent_dim=args.latent_dim,
                attention_dim=args.attention_dim,
                attention_input_scale=args.attention_input_scale,
                window_size=args.window_size,
            )
        initial_vae_hash = state_sha256(model.vae)
        attention_diagnostics_before = None
        diagnostic_indices = None
        if args.variant in ("attention", "attention_shuffled"):
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
            spatial_lambda=args.spatial_lambda,
            spatial_loss_scale=spatial_loss_scale,
            poisson_effective_count=args.poisson_effective_count,
            maximum_samples=None,
            seed=args.seed,
            device="cuda",
            experiment_metadata={
                "purpose": (
                    "window/control implementation experiment, not frozen baseline"
                    if args.window_size != 3 or args.variant in ("zero_context", "shuffled_uniform", "attention_shuffled")
                    else "cached full-run runtime/equivalence validation, not frozen baseline"
                    if args.cache_spectra
                    else "production neighbourhood baseline"
                ),
                "neighbourhood_variant": args.variant,
                "window_size": args.window_size,
                "context_mode": context_mode,
                "context_seed": dataset.context_seed,
                "context_permutation_sha256": dataset.context_permutation_sha256,
                "spatial_lambda": args.spatial_lambda,
                "spatial_loss_scale_name": args.spatial_loss_scale,
                "spatial_loss_scale": spatial_loss_scale,
                "poisson_augmentation": args.poisson_effective_count is not None,
                "poisson_effective_count": args.poisson_effective_count,
                "initial_vae_sha256": initial_vae_hash,
                "attention_input_scale": args.attention_input_scale,
                "data_loader": "cached_float32" if args.cache_spectra else "streaming_hdf5",
            },
            checkpoint_interval=args.checkpoint_interval,
            resume_checkpoint=args.resume_checkpoint,
        )
        attention_diagnostics_after = None
        if args.variant in ("attention", "attention_shuffled"):
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
            else (
                "Poisson augmentation pilot"
                if args.poisson_effective_count is not None
                else (
                    "spatial-loss pilot"
                    if args.spatial_lambda > 0
                    else "production neighbourhood baseline"
                )
            )
        ),
        "variant": args.variant,
        "window_size": args.window_size,
        "context_mode": context_mode,
        "context_seed": dataset.context_seed,
        "context_permutation_sha256": dataset.context_permutation_sha256,
        "initial_vae_sha256": initial_vae_hash,
        "controls": {
            "seed": args.seed,
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "hidden_dim": args.hidden_dim,
            "latent_dim": args.latent_dim,
            "attention_dim": args.attention_dim,
            "attention_input_scale": args.attention_input_scale,
            "spatial_lambda": args.spatial_lambda,
            "spatial_loss_scale_name": args.spatial_loss_scale,
            "spatial_loss_scale": spatial_loss_scale,
            "poisson_augmentation": args.poisson_effective_count is not None,
            "poisson_effective_count": args.poisson_effective_count,
            "full_dataset": True,
            "window_size": args.window_size,
            "context_mode": context_mode,
            "context_seed": dataset.context_seed,
            "context_permutation_sha256": dataset.context_permutation_sha256,
            "data_loader": "cached_float32" if args.cache_spectra else "streaming_hdf5",
        },
        "samples_per_epoch": metadata["samples_per_epoch"],
        "dataset_size": metadata["dataset_size"],
        "training_seconds": metadata["training_seconds"],
        "dataset_load_seconds": dataset_load_seconds,
        "script_wall_seconds_to_summary": time.perf_counter() - script_started_at,
        "cached_host_matrix_bytes": (
            int(dataset._spectra.nbytes) if args.cache_spectra else None
        ),
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
        } if args.variant in ("attention", "attention_shuffled") else None,
        "status": "complete",
    }
    if args.window_size != 3 or args.variant in ("zero_context", "shuffled_uniform", "attention_shuffled"):
        summary["purpose"] = "window/control implementation experiment, not frozen baseline"
    elif args.cache_spectra:
        summary["purpose"] = (
            "cached full-run runtime/equivalence validation, not frozen baseline"
        )
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

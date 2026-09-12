#!/usr/bin/env python3
"""Validate all Spatial-msiPL neighbourhood variants on real HDF5 spectra."""

import argparse
import json
from pathlib import Path

import numpy as np
import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset, MOORE_OFFSETS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--hidden-dim", type=int, default=8)
    parser.add_argument("--latent-dim", type=int, default=5)
    parser.add_argument("--attention-dim", type=int, default=8)
    parser.add_argument("--seed", type=int, default=1)
    args = parser.parse_args()

    torch.manual_seed(args.seed)
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    indices = sorted({0, len(dataset) // 2, len(dataset) - 1})
    samples = [dataset[index] for index in indices]
    central = torch.from_numpy(np.stack([sample["target"] for sample in samples]))
    neighbours = torch.from_numpy(np.stack([sample["neighbours"] for sample in samples]))
    neighbour_mask = torch.from_numpy(
        np.stack([sample["neighbour_mask"] for sample in samples])
    )
    expected_uniform_context = torch.from_numpy(
        np.stack([sample["context"] for sample in samples])
    )

    variants = {}
    contexts = {}
    for name in ("uniform_mean", "depthwise", "attention"):
        model = NeighbourhoodSpatialVAE(
            spectral_dim=dataset.n_mz,
            neighbourhood=name,
            hidden_dim=args.hidden_dim,
            latent_dim=args.latent_dim,
            attention_dim=args.attention_dim,
        )
        model.eval()
        with torch.no_grad():
            reconstruction, mean, log_variance, context, weights = model(
                central, neighbours, neighbour_mask
            )

        if not all(
            torch.isfinite(tensor).all()
            for tensor in (reconstruction, mean, log_variance, context, weights)
        ):
            raise ValueError(f"{name} produced a non-finite value")
        if tuple(reconstruction.shape) != (len(indices), dataset.n_mz):
            raise ValueError(f"{name} reconstructed the wrong shape")
        invalid_weight_total = (
            weights * (~neighbour_mask).to(weights.dtype).unsqueeze(-1)
        ).abs().sum() if weights.ndim == 3 else (
            weights * (~neighbour_mask).to(weights.dtype)
        ).abs().sum()
        if float(invalid_weight_total) != 0.0:
            raise ValueError(f"{name} assigned weight to a missing neighbour")

        contexts[name] = context
        variants[name] = {
            "aggregator_configuration": model.aggregator.configuration(),
            "total_model_parameters": sum(p.numel() for p in model.parameters()),
            "context_shape": list(context.shape),
            "weight_shape": list(weights.shape),
            "context_tic_sum_min": float(context.sum(dim=1).min()),
            "context_tic_sum_max": float(context.sum(dim=1).max()),
            "invalid_neighbour_weight_total": float(invalid_weight_total),
            "reconstruction_shape": list(reconstruction.shape),
            "latent_mean_shape": list(mean.shape),
            "finite": True,
        }

    uniform_error = float(
        torch.max(torch.abs(contexts["uniform_mean"] - expected_uniform_context))
    )
    depthwise_initial_error = float(
        torch.max(torch.abs(contexts["depthwise"] - contexts["uniform_mean"]))
    )
    if uniform_error > 1e-6:
        raise ValueError(f"uniform aggregation changed the baseline by {uniform_error}")
    if depthwise_initial_error > 1e-6:
        raise ValueError(
            f"depthwise zero initialization differs from uniform by {depthwise_initial_error}"
        )

    summary = {
        "input": str(dataset.path),
        "purpose": "real-data interface validation, not model training or evaluation",
        "pixels": len(dataset),
        "mz_bins": dataset.n_mz,
        "sample_indices": indices,
        "sample_neighbour_counts": [int(sample["neighbour_count"]) for sample in samples],
        "slot_order_dx_dy": [list(offset) for offset in MOORE_OFFSETS],
        "uniform_baseline_max_absolute_error": uniform_error,
        "depthwise_initial_vs_uniform_max_absolute_error": depthwise_initial_error,
        "variants": variants,
        "status": "valid",
    }
    dataset.close()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()


#!/usr/bin/env python3
"""Short, non-production timing probe for the existing Spatial-msiPL loop.

This deliberately uses the production HDF5 dataset, batch size, models and loss,
but starts a fresh model and never writes a checkpoint or scientific result.
Per-phase CUDA synchronisation makes the timings diagnostic, not a substitute
for an uninterrupted end-to-end training benchmark.
"""

import argparse
import json
import resource
import statistics
import time
from pathlib import Path

import h5py
import torch
from torch.utils.data import DataLoader

from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import CachedH5SpatialContextDataset, H5SpatialContextDataset
from spatial_msipl.training import latent_spatial_coherence_loss, msipl_vae_loss


def synchronize(device):
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def summarize(values):
    return {
        "mean_seconds": statistics.mean(values),
        "median_seconds": statistics.median(values),
        "mean_after_first_seconds": (
            statistics.mean(values[1:]) if len(values) > 1 else None
        ),
        "per_batch_seconds": values,
        "samples": len(values),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--variant", choices=("central_only", "uniform_mean"), required=True)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--batches", type=int, default=4)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--cache-spectra", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 2 or args.batches < 1:
        parser.error("batch-size must be at least 2 and batches must be positive")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no profile was run")
    torch.manual_seed(1)
    dataset_started_at = time.perf_counter()
    dataset = (
        CachedH5SpatialContextDataset(args.input, include_neighbourhood=True)
        if args.cache_spectra
        else H5SpatialContextDataset(args.input, include_neighbourhood=True)
    )
    dataset_load_seconds = time.perf_counter() - dataset_started_at
    try:
        model = (
            CentralOnlyVAE(dataset.n_mz)
            if args.variant == "central_only"
            else NeighbourhoodSpatialVAE(dataset.n_mz, neighbourhood="uniform_mean")
        ).to(device)
        model.train()
        optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
        loader = DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=True,
            drop_last=len(dataset) % args.batch_size == 1,
            num_workers=0,
            generator=torch.Generator().manual_seed(1),
        )
        available_batches = len(loader)
        if available_batches == 0:
            raise ValueError("dataset does not contain one valid training batch")
        batches = min(args.batches, available_batches)

        with h5py.File(args.input, "r") as handle:
            source = handle["Data"]
            h5_layout = {
                "shape": list(source.shape),
                "dtype": str(source.dtype),
                "chunks": list(source.chunks) if source.chunks else None,
                "compression": source.compression,
            }
        if device.type == "cuda":
            torch.cuda.reset_peak_memory_stats(device)

        phase_names = (
            "h5_read_normalize_collate",
            "cpu_to_device",
            "forward",
            "loss_and_spatial_pair_check",
            "backward_and_optimizer",
            "scalar_logging",
        )
        timings = {name: [] for name in phase_names}
        loader_iterator = iter(loader)
        samples_seen = 0
        last_loss = None
        for _ in range(batches):
            synchronize(device)
            start = time.perf_counter()
            batch = next(loader_iterator)
            timings[phase_names[0]].append(time.perf_counter() - start)

            start = time.perf_counter()
            target = batch["target"].to(device, dtype=torch.float32)
            neighbours = batch["neighbours"].to(device, dtype=torch.float32)
            neighbour_mask = batch["neighbour_mask"].to(device, dtype=torch.bool)
            synchronize(device)
            timings[phase_names[1]].append(time.perf_counter() - start)

            optimizer.zero_grad(set_to_none=True)
            start = time.perf_counter()
            reconstruction, mean, log_variance = model(
                target, neighbours, neighbour_mask
            )[:3]
            synchronize(device)
            timings[phase_names[2]].append(time.perf_counter() - start)

            start = time.perf_counter()
            vae_loss, _, _ = msipl_vae_loss(
                reconstruction, target, mean, log_variance, beta=1.0
            )
            # Production currently computes this even with spatial_lambda=0.
            spatial_loss, _ = latent_spatial_coherence_loss(
                mean, batch["x"], batch["y"]
            )
            loss = vae_loss + 0.0 * spatial_loss
            synchronize(device)
            timings[phase_names[3]].append(time.perf_counter() - start)

            start = time.perf_counter()
            loss.backward()
            optimizer.step()
            synchronize(device)
            timings[phase_names[4]].append(time.perf_counter() - start)

            start = time.perf_counter()
            last_loss = float(loss.detach())
            timings[phase_names[5]].append(time.perf_counter() - start)
            samples_seen += len(target)

        phase_summary = {name: summarize(values) for name, values in timings.items()}
        summed_phase_seconds = sum(sum(values) for values in timings.values())
        report = {
            "purpose": "diagnostic only; fresh weights, no production checkpoint",
            "input": str(dataset.path),
            "variant": args.variant,
            "device": str(device),
            "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
            "dataset_size": len(dataset),
            "data_loader": "cached_float32" if args.cache_spectra else "streaming_hdf5",
            "dataset_load_seconds": dataset_load_seconds,
            "spectral_bins": dataset.n_mz,
            "batch_size": args.batch_size,
            "profiled_batches": batches,
            "full_epoch_batches": available_batches,
            "profiled_samples": samples_seen,
            "h5_layout": h5_layout,
            "parameters_by_tensor": {name: tensor.numel() for name, tensor in model.named_parameters()},
            "parameter_count": sum(tensor.numel() for tensor in model.parameters()),
            "approx_float32_batch_payload_mib": (
                args.batch_size * dataset.n_mz * 9 * 4 / (1024 ** 2)
            ),
            "timing_note": "Each GPU phase is synchronized; timings include synchronization overhead and only sampled batches.",
            "phase_timings": phase_summary,
            "summed_profiled_phase_seconds": summed_phase_seconds,
            "observed_profiled_samples_per_second": samples_seen / summed_phase_seconds,
            "last_diagnostic_loss": last_loss,
            "peak_gpu_allocated_bytes": (
                int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None
            ),
            "peak_gpu_reserved_bytes": (
                int(torch.cuda.max_memory_reserved(device)) if device.type == "cuda" else None
            ),
            "host_peak_rss_bytes_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2), flush=True)
    finally:
        dataset.close()


if __name__ == "__main__":
    main()

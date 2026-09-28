#!/usr/bin/env python3
"""Non-production S3PL phase probe on the existing MassNet HDF5 adapter.

Uses the reference model, patch construction, normalization, MSE and Adam.
Writes timing JSON only; it does not train a full epoch or touch checkpoints.
"""

import argparse
import json
import resource
import statistics
import sys
import time
from pathlib import Path

import torch
from torch import nn
from torch.utils.data import DataLoader, SubsetRandomSampler

S3PL_ROOT = Path(__file__).resolve().parents[1] / "baselines" / "s3pl"
sys.path.insert(0, str(S3PL_ROOT))
from model.Attention3DConvAutoencoder import Attention3DConvAutoencoder
from utils.data_source import build_patch_dataset
from utils.helpers import normalize_spectra


def sync(device):
    if device.type == "cuda":
        torch.cuda.synchronize(device)


def summarize(values):
    return {
        "mean_seconds": statistics.mean(values),
        "median_seconds": statistics.median(values),
        "mean_after_first_seconds": statistics.mean(values[1:]) if len(values) > 1 else None,
        "per_batch_seconds": values,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--patch-size", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--batches", type=int, default=8)
    parser.add_argument("--normalization", default="reference_spatial_max")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    args = parser.parse_args()
    if args.patch_size < 1 or args.patch_size % 2 != 1:
        parser.error("patch-size must be a positive odd integer")
    if args.batch_size < 1 or args.batches < 1:
        parser.error("batch-size and batches must be positive")

    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no profile was run")
    torch.manual_seed(1)
    if device.type == "cuda":
        torch.cuda.manual_seed(1)

    load_started = time.perf_counter()
    dataset, mz_values = build_patch_dataset(
        args.input,
        args.patch_size,
        lambda patch: torch.tensor(
            normalize_spectra(patch, args.normalization), dtype=torch.float32
        ),
    )
    dataset_load_seconds = time.perf_counter() - load_started

    model_started = time.perf_counter()
    model = Attention3DConvAutoencoder(
        args.batch_size,
        kernel_depth_d1=51,
        kernel_depth_d2=1,
        dropout=0,
        spectral_patch_size=args.patch_size,
    ).to(device)
    model.train()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    criterion = nn.MSELoss()
    model_setup_seconds = time.perf_counter() - model_started
    sampler = SubsetRandomSampler(range(len(dataset)), generator=torch.Generator().manual_seed(1))
    loader = DataLoader(dataset, batch_size=args.batch_size, sampler=sampler, drop_last=True)
    batches = min(args.batches, len(loader))
    if not batches:
        raise ValueError("dataset has fewer pixels than one full batch")

    phase_names = (
        "patch_normalize_collate",
        "cpu_to_device",
        "forward",
        "mse_loss",
        "backward_and_optimizer",
        "scalar_logging",
    )
    timings = {name: [] for name in phase_names}
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)
    iterator = iter(loader)
    last_loss = None
    samples_seen = 0
    for _ in range(batches):
        sync(device)
        started = time.perf_counter()
        patch, _ = next(iterator)
        timings[phase_names[0]].append(time.perf_counter() - started)

        started = time.perf_counter()
        patch = patch.to(device)
        sync(device)
        timings[phase_names[1]].append(time.perf_counter() - started)

        optimizer.zero_grad()
        started = time.perf_counter()
        reconstructed, _, _ = model(patch)
        sync(device)
        timings[phase_names[2]].append(time.perf_counter() - started)

        started = time.perf_counter()
        loss = criterion(reconstructed, patch)
        sync(device)
        timings[phase_names[3]].append(time.perf_counter() - started)

        started = time.perf_counter()
        loss.backward()
        optimizer.step()
        sync(device)
        timings[phase_names[4]].append(time.perf_counter() - started)

        started = time.perf_counter()
        last_loss = loss.item()
        timings[phase_names[5]].append(time.perf_counter() - started)
        samples_seen += len(patch)

    measured_seconds = sum(sum(values) for values in timings.values())
    report = {
        "purpose": "diagnostic only; fresh weights, no production checkpoint",
        "input": str(args.input),
        "device": str(device),
        "device_name": torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU",
        "dataset_size": len(dataset),
        "spectral_bins": len(mz_values),
        "patch_size": args.patch_size,
        "batch_size": args.batch_size,
        "normalization": args.normalization,
        "profiled_batches": batches,
        "full_epoch_batches": len(loader),
        "profiled_samples": samples_seen,
        "dataset_load_seconds": dataset_load_seconds,
        "model_setup_seconds": model_setup_seconds,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "parameters_by_tensor": {name: parameter.numel() for name, parameter in model.named_parameters()},
        "approx_float32_batch_payload_mib": args.batch_size * len(mz_values) * args.patch_size**2 * 4 / 1024**2,
        "phase_timings": {name: summarize(values) for name, values in timings.items()},
        "summed_profiled_phase_seconds": measured_seconds,
        "observed_profiled_samples_per_second": samples_seen / measured_seconds,
        "last_diagnostic_loss": last_loss,
        "peak_gpu_allocated_bytes": int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else None,
        "peak_gpu_reserved_bytes": int(torch.cuda.max_memory_reserved(device)) if device.type == "cuda" else None,
        "host_peak_rss_bytes_linux": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "timing_note": "CUDA phases are synchronized; sampled batches are not a complete epoch or end-to-end workflow.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

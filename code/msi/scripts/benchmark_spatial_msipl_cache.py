#!/usr/bin/env python3
"""Check exact sample parity, then compare streaming and cached batch loading.

This diagnostic does not train a model or modify production checkpoints.
The cache loads raw spectra once as float32; both loaders still use the same
TIC-normalization and neighbourhood-building code for each requested sample.
"""

import argparse
import json
import statistics
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
)


def check_parity(streaming, cached, sample_count):
    counts = np.count_nonzero(streaming.neighbour_slots >= 0, axis=1)
    rng = np.random.default_rng(1)
    selected = {
        0,
        len(streaming) - 1,
        int(np.argmin(counts)),
        int(np.argmax(counts)),
    }
    selected.update(
        int(index)
        for index in rng.choice(
            len(streaming), size=min(sample_count, len(streaming)), replace=False
        )
    )
    for index in sorted(selected):
        reference = streaming[index]
        candidate = cached[index]
        if reference.keys() != candidate.keys():
            raise AssertionError(f"sample keys differ at pixel {index}")
        for key in reference:
            if not np.array_equal(reference[key], candidate[key]):
                raise AssertionError(f"cached sample differs at pixel {index}, {key}")
    return len(selected)


def time_batches(dataset, batch_size, batch_count, label):
    loader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=len(dataset) % batch_size == 1,
        num_workers=0,
        generator=torch.Generator().manual_seed(1),
    )
    iterator = iter(loader)
    times = []
    first_indices = None
    for number in range(min(batch_count, len(loader))):
        start = time.perf_counter()
        batch = next(iterator)
        seconds = time.perf_counter() - start
        if number == 0:
            first_indices = batch["index"].tolist()
        times.append(seconds)
        print(f"{label} batch {number + 1}/{min(batch_count, len(loader))}: {seconds:.3f}s", flush=True)
    return {
        "per_batch_seconds": times,
        "mean_seconds": statistics.mean(times),
        "mean_after_first_seconds": statistics.mean(times[1:]) if len(times) > 1 else None,
        "first_batch_indices": first_indices,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--batches", type=int, default=8)
    parser.add_argument("--parity-samples", type=int, default=32)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batches < 2 or args.parity_samples < 1:
        parser.error("batch-size and parity-samples must be positive; batches must be at least 2")

    streaming = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        print("Loading the in-memory float32 copy once...", flush=True)
        start = time.perf_counter()
        cached = CachedH5SpatialContextDataset(args.input, include_neighbourhood=True)
        cache_load_seconds = time.perf_counter() - start
        try:
            print("Checking exact sample parity...", flush=True)
            parity_count = check_parity(streaming, cached, args.parity_samples)
            print(f"Exact parity passed for {parity_count} pixels.", flush=True)
            # Both DataLoaders use identical RNG seeds and sample ordering.
            print("Timing streaming batches...", flush=True)
            streamed = time_batches(streaming, args.batch_size, args.batches, "streaming")
            print("Timing cached batches...", flush=True)
            in_memory = time_batches(cached, args.batch_size, args.batches, "cached")
            if streamed["first_batch_indices"] != in_memory["first_batch_indices"]:
                raise AssertionError("batch ordering differs between loaders")
            report = {
                "purpose": "diagnostic only; no training or checkpoint writes",
                "input": str(streaming.path),
                "dataset_size": len(streaming),
                "spectral_bins": streaming.n_mz,
                "batch_size": args.batch_size,
                "benchmarked_batches": len(streamed["per_batch_seconds"]),
                "exact_parity_pixels": parity_count,
                "cache_dtype": str(cached._spectra.dtype),
                "cache_bytes": int(cached._spectra.nbytes),
                "cache_load_seconds": cache_load_seconds,
                "streaming": streamed,
                "cached": in_memory,
                "steady_batch_speedup": (
                    streamed["mean_after_first_seconds"]
                    / in_memory["mean_after_first_seconds"]
                ),
                "note": "DataLoader batch preparation only; compare full training separately before changing production runs.",
            }
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(json.dumps(report, indent=2), flush=True)
        finally:
            cached.close()
    finally:
        streaming.close()


if __name__ == "__main__":
    main()

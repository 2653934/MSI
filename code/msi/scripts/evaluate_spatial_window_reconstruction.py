#!/usr/bin/env python3
"""Measure deterministic, in-sample reconstruction for one window pilot arm."""

import argparse
import json
from pathlib import Path

import torch

from evaluate_spatial_reconstruction import deterministic_reconstruction_metrics
from run_spatial_msipl_gmm_integrated_gradients import load_model
from spatial_msipl.preprocessing import H5SpatialContextDataset, checkpoint_input_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--variant", required=True,
                        choices=("uniform_mean", "zero_context", "shuffled_uniform", "attention", "attention_shuffled"))
    parser.add_argument("--batch-size", type=int, default=64)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch size must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; reconstruction evaluation stopped")

    checkpoint = torch.load(args.checkpoint, map_location="cpu")
    input_spec = checkpoint_input_spec(checkpoint)
    dataset = H5SpatialContextDataset(
        args.input, include_neighbourhood=True,
        window_size=input_spec["window_size"],
        context_mode=input_spec["context_mode"],
        context_seed=input_spec["context_seed"],
    )
    try:
        if (input_spec["context_mode"] == "shuffled" and
                input_spec["context_permutation_sha256"] != dataset.context_permutation_sha256):
            raise ValueError("checkpoint and evaluation context permutations differ")
        model, _ = load_model(args.checkpoint, dataset.n_mz, args.variant,
                              torch.device("cuda"), checkpoint=checkpoint)
        metrics, pixels = deterministic_reconstruction_metrics(
            model, dataset, args.batch_size, torch.device("cuda")
        )
    finally:
        dataset.close()

    result = {
        "status": "complete",
        "scope": "in-sample, label-free, deterministic encoder-mean reconstruction",
        "dataset": str(args.input),
        "checkpoint": str(args.checkpoint),
        "variant": args.variant,
        "input_specification": input_spec,
        "pixels": pixels,
        "parameters": sum(parameter.numel() for parameter in model.parameters()),
        "metrics": metrics,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reconstruction.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

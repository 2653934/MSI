#!/usr/bin/env python3
"""Compare frozen streaming and cached final model tensors without mutation."""

import argparse
import json
from pathlib import Path

import torch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--streaming", required=True, type=Path)
    parser.add_argument("--cached", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--variant", required=True, choices=("central_only", "uniform_mean"))
    args = parser.parse_args()
    for source in (args.streaming, args.cached):
        if not source.is_file():
            raise FileNotFoundError(source)
    if args.output.exists():
        raise FileExistsError(f"comparison already exists: {args.output}")

    # Both checkpoints include optimizer state, but this audit compares the
    # actual inference model tensors. Loading is CPU-only and read-only.
    streaming = torch.load(args.streaming, map_location="cpu")
    cached = torch.load(args.cached, map_location="cpu")
    old_state = streaming["model_state_dict"]
    new_state = cached["model_state_dict"]
    if old_state.keys() != new_state.keys():
        raise ValueError("model tensor names differ between checkpoints")

    differences = []
    maximum_absolute_difference = 0.0
    for name, old_tensor in old_state.items():
        new_tensor = new_state[name]
        if old_tensor.shape != new_tensor.shape or old_tensor.dtype != new_tensor.dtype:
            differences.append({"name": name, "issue": "shape_or_dtype"})
            continue
        if not torch.equal(old_tensor, new_tensor):
            maximum_absolute_difference = max(
                maximum_absolute_difference,
                float((old_tensor.to(torch.float64) - new_tensor.to(torch.float64)).abs().max()),
            )
            differences.append({"name": name, "issue": "values"})

    report = {
        "purpose": "read-only final checkpoint model-state comparison",
        "variant": args.variant,
        "streaming_checkpoint": str(args.streaming),
        "cached_checkpoint": str(args.cached),
        "streaming_completed_epochs": streaming.get("completed_epochs"),
        "cached_completed_epochs": cached.get("completed_epochs"),
        "model_configuration_equal": (
            streaming.get("model_configuration") == cached.get("model_configuration")
        ),
        "model_tensor_count": len(old_state),
        "all_model_tensors_exact": not differences,
        "different_tensor_count": len(differences),
        "different_tensor_examples": differences[:10],
        "maximum_absolute_tensor_difference": maximum_absolute_difference,
        "note": "Optimizer state and later attribution/evaluation are not compared here.",
    }
    report["status"] = (
        "exact"
        if report["all_model_tensors_exact"]
        and report["model_configuration_equal"]
        and report["streaming_completed_epochs"] == 100
        and report["cached_completed_epochs"] == 100
        else "needs_review"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

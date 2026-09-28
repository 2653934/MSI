#!/usr/bin/env python3
"""One-epoch production-loop parity and timing check for the cached loader.

Runs the same train_vae implementation, full GBM108-positive section, model
settings, seed and batch order with streaming versus cached input. No existing
result directory or production checkpoint is used.
"""

import argparse
import hashlib
import json
from pathlib import Path

import torch

from benchmark_spatial_msipl_cache import check_parity
from spatial_msipl.model import CentralOnlyVAE, NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
)
from spatial_msipl.training import set_random_seed, train_vae


def state_sha256(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def new_model(variant, spectral_dim):
    if variant == "central_only":
        return CentralOnlyVAE(spectral_dim, hidden_dim=512, latent_dim=5)
    return NeighbourhoodSpatialVAE(
        spectral_dim, neighbourhood="uniform_mean", hidden_dim=512, latent_dim=5
    )


def run_once(dataset, variant, loader_name, output_root):
    set_random_seed(1, include_cuda=True)
    model = new_model(variant, dataset.n_mz)
    initial_hash = state_sha256(model)
    metadata, history = train_vae(
        model=model,
        dataset=dataset,
        output_directory=output_root / variant / loader_name,
        epochs=1,
        batch_size=128,
        learning_rate=0.001,
        beta=1.0,
        spatial_lambda=0.0,
        maximum_samples=None,
        seed=1,
        device="cuda",
        experiment_metadata={
            "purpose": "cache loader end-to-end diagnostic, not a scientific result",
            "variant": variant,
            "loader": loader_name,
        },
        save_checkpoint=False,
    )
    state = {
        name: tensor.detach().cpu().clone()
        for name, tensor in model.state_dict().items()
    }
    del model
    torch.cuda.empty_cache()
    return metadata, history[0], initial_hash, state


def compare_states(reference, candidate):
    if reference.keys() != candidate.keys():
        raise AssertionError("final model state keys differ")
    max_absolute_difference = 0.0
    all_exact = True
    all_close = True
    for name in reference:
        left = reference[name]
        right = candidate[name]
        if left.shape != right.shape or left.dtype != right.dtype:
            raise AssertionError(f"final model state structure differs for {name}")
        all_exact &= bool(torch.equal(left, right))
        left_float = left.to(torch.float64)
        right_float = right.to(torch.float64)
        max_absolute_difference = max(
            max_absolute_difference,
            float((left_float - right_float).abs().max()),
        )
        all_close &= bool(torch.allclose(left_float, right_float, rtol=1e-5, atol=1e-6))
    return {
        "all_tensors_exact": all_exact,
        "all_tensors_close_rtol_1e-5_atol_1e-6": all_close,
        "max_absolute_tensor_difference": max_absolute_difference,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; diagnostic stopped before loading the model")
    if args.output.exists():
        raise FileExistsError(f"diagnostic output already exists: {args.output}")

    streaming = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        cached = CachedH5SpatialContextDataset(args.input, include_neighbourhood=True)
        try:
            parity_count = check_parity(streaming, cached, sample_count=32)
            print(json.dumps({"exact_sample_parity_pixels": parity_count}), flush=True)
            summaries = {}
            for variant in ("central_only", "uniform_mean"):
                print(json.dumps({"starting_variant": variant}), flush=True)
                reference_meta, reference_epoch, reference_hash, reference_state = run_once(
                    streaming, variant, "streaming", args.output
                )
                candidate_meta, candidate_epoch, candidate_hash, candidate_state = run_once(
                    cached, variant, "cached", args.output
                )
                if reference_hash != candidate_hash:
                    raise AssertionError(f"initial model weights differ for {variant}")
                if reference_meta["selected_indices"] != candidate_meta["selected_indices"]:
                    raise AssertionError(f"training pixel selection differs for {variant}")
                if reference_epoch["samples_seen"] != candidate_epoch["samples_seen"]:
                    raise AssertionError(f"samples seen differ for {variant}")
                state_comparison = compare_states(reference_state, candidate_state)
                losses = {}
                for name in ("total_loss", "vae_loss", "reconstruction_loss", "kl_loss"):
                    first = float(reference_epoch[name])
                    second = float(candidate_epoch[name])
                    losses[name] = {
                        "streaming": first,
                        "cached": second,
                        "absolute_difference": abs(first - second),
                        "relative_difference": abs(first - second) / max(abs(first), 1e-12),
                    }
                summaries[variant] = {
                    "initial_state_sha256": reference_hash,
                    "same_selected_pixels": True,
                    "same_samples_seen": True,
                    "streaming_epoch_seconds": reference_epoch["epoch_seconds"],
                    "cached_epoch_seconds": candidate_epoch["epoch_seconds"],
                    "epoch_speedup": (
                        reference_epoch["epoch_seconds"] / candidate_epoch["epoch_seconds"]
                    ),
                    "streaming_peak_gpu_bytes": reference_meta["peak_gpu_memory_allocated_bytes"],
                    "cached_peak_gpu_bytes": candidate_meta["peak_gpu_memory_allocated_bytes"],
                    "losses": losses,
                    "final_state": state_comparison,
                    "status": (
                        "matched"
                        if state_comparison["all_tensors_close_rtol_1e-5_atol_1e-6"]
                        and all(value["relative_difference"] <= 1e-6 for value in losses.values())
                        else "needs_review"
                    ),
                }
                print(json.dumps({"finished_variant": variant, **summaries[variant]}), flush=True)
                del reference_state, candidate_state
            report = {
                "purpose": "one-epoch cache diagnostic; not scientific model evaluation",
                "input": str(streaming.path),
                "dataset_size": len(streaming),
                "spectral_bins": streaming.n_mz,
                "device_name": torch.cuda.get_device_name(),
                "cache_bytes": int(cached._spectra.nbytes),
                "exact_sample_parity_pixels": parity_count,
                "controls": {
                    "epochs": 1,
                    "batch_size": 128,
                    "hidden_dim": 512,
                    "latent_dim": 5,
                    "learning_rate": 0.001,
                    "seed": 1,
                    "full_section": True,
                    "same_training_function": True,
                    "checkpoints_saved": False,
                },
                "variants": summaries,
                "status": "matched" if all(
                    item["status"] == "matched" for item in summaries.values()
                ) else "needs_review",
            }
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "summary.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps({"summary": str(args.output / "summary.json"), "status": report["status"]}), flush=True)
        finally:
            cached.close()
    finally:
        streaming.close()


if __name__ == "__main__":
    main()

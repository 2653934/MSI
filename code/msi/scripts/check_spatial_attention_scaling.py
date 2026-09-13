#!/usr/bin/env python3
"""Small matched attention-scaling diagnostic; no production checkpoint writes.

Only the inputs to the attention projection are rescaled. The spectra supplied
to the VAE, reconstruction target and weighted context retain their usual TIC
normalization. Fresh models train on the same cached sample for a few steps.
"""

import argparse
from contextlib import contextmanager
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.preprocessing import H5SpatialContextDataset
from spatial_msipl.training import msipl_vae_loss, set_random_seed


@contextmanager
def projection_scale(model, scale):
    """Temporarily replace the original D scaling with the requested scale."""
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError("scale must be finite and positive")
    factor = scale / model.vae.spectral_dim
    hook = model.aggregator.projection.register_forward_pre_hook(
        lambda module, inputs: (inputs[0] * factor,)
    )
    try:
        yield
    finally:
        hook.remove()


def state_hash(model):
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode())
        digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def measure(model, batch):
    """Measure actual projection outputs and weights using the encoder path."""
    projections = []
    hook = model.aggregator.projection.register_forward_hook(
        lambda module, inputs, output: projections.append(output.detach())
    )
    model.eval()
    try:
        with torch.no_grad():
            _, _, _, weights = model.encode(
                batch["target"], batch["neighbours"], batch["neighbour_mask"]
            )
    finally:
        hook.remove()
    central, neighbours = [torch.tanh(p) for p in projections]
    mask = batch["neighbour_mask"]
    counts = mask.sum(1)
    eligible = counts > 1
    uniform = mask.float() / counts.clamp_min(1)[:, None]
    deviation = (weights - uniform).abs()
    scores = (central[:, None] * neighbours).sum(-1) / math.sqrt(central.shape[-1])
    spread = scores.masked_fill(~mask, -torch.inf).amax(1) - scores.masked_fill(~mask, torch.inf).amin(1)
    positive = weights.double().clamp_min(torch.finfo(torch.float64).tiny)
    entropy = -(weights.double() * positive.log()).sum(1)
    entropy = entropy[eligible] / counts[eligible].double().log()
    valid_embeddings = neighbours[mask]
    return {
        "pixels_with_at_least_two_neighbours": int(eligible.sum()),
        "entropy_mean": float(entropy.mean()) if entropy.numel() else None,
        "weight_deviation_mean": float(deviation[mask].mean()) if mask.any() else None,
        "weight_deviation_max": float(deviation.max()),
        "score_spread_mean": float(spread[eligible].mean()) if eligible.any() else None,
        "score_spread_max": float(spread[eligible].max()) if eligible.any() else None,
        "central_saturation_fraction": float((central.abs() >= 0.99).float().mean()),
        "neighbour_saturation_fraction": float((valid_embeddings.abs() >= 0.99).float().mean()) if valid_embeddings.numel() else None,
        "mean_tanh_derivative": float((1 - central.square()).mean()),
    }


def run_candidate(model, batches, scale, steps):
    optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
    history = []
    with projection_scale(model, scale):
        history.append({"step": 0, **measure(model, batches[0])})
        for step in range(1, steps + 1):
            batch = batches[(step - 1) % len(batches)]
            model.train()
            optimizer.zero_grad(set_to_none=True)
            reconstruction, mean, log_variance, _, _ = model(
                batch["target"], batch["neighbours"], batch["neighbour_mask"]
            )
            loss, _, _ = msipl_vae_loss(reconstruction, batch["target"], mean, log_variance)
            if not torch.isfinite(loss):
                raise RuntimeError(f"non-finite loss at scale={scale}, step={step}")
            loss.backward()
            gradient = model.aggregator.projection.weight.grad
            if gradient is None or not torch.isfinite(gradient).all():
                raise RuntimeError("missing or non-finite projection gradient")
            gradient_norm = float(gradient.norm())
            optimizer.step()
            # Always inspect the same batch, making trajectories comparable.
            record = {"step": step, "training_loss": float(loss.detach()),
                      "projection_gradient_norm": gradient_norm,
                      **measure(model, batches[0])}
            history.append(record)
            print(json.dumps({"scale": scale, **record}, allow_nan=False), flush=True)
    return history


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--checkpoint", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--steps", type=int, default=20)
    args = parser.parse_args()
    if args.steps < 1 or args.batch_size < 2 or args.samples < args.batch_size or args.samples % args.batch_size:
        raise ValueError("use positive steps and samples divisible by batch size >= 2")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; no diagnostic was run")
    # A unique Slurm job directory preserves every attempt.
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    dataset = H5SpatialContextDataset(args.input, include_neighbourhood=True)
    try:
        indices = np.sort(np.random.default_rng(1).choice(len(dataset), args.samples, replace=False))
        batches = []
        print("Reading the fixed sample and its measured neighbours", flush=True)
        for batch in DataLoader(Subset(dataset, indices.tolist()), batch_size=args.batch_size):
            batches.append({k: batch[k].to("cuda") for k in ("target", "neighbours", "neighbour_mask")})
        spectral_dim = dataset.n_mz
    finally:
        dataset.close()

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    config = checkpoint["model_configuration"]
    if config["spectral_dim"] != spectral_dim or config["neighbourhood"]["name"] != "attention" or checkpoint["completed_epochs"] != 100:
        raise ValueError("expected the original complete attention checkpoint")
    def new_model():
        set_random_seed(1, include_cuda=True)
        return NeighbourhoodSpatialVAE(
            spectral_dim, neighbourhood="attention", hidden_dim=config["hidden_dim"],
            latent_dim=config["latent_dim"], attention_dim=config["neighbourhood"]["attention_dim"]
        ).cuda()

    model = new_model()
    model.load_state_dict(checkpoint["model_state_dict"])
    reference = measure(model, batches[0])
    del checkpoint, model
    torch.cuda.empty_cache()
    summary = {
        "purpose": "scaling and gradient diagnostic, not biological evaluation",
        "input": str(args.input), "checkpoint_reference": str(args.checkpoint),
        "seed": 1, "selected_indices": indices.tolist(), "batch_size": args.batch_size,
        "steps": args.steps, "learning_rate": 0.001, "scheduler": "none",
        "device": torch.cuda.get_device_name(), "torch_version": torch.__version__,
        "measurement_batch_indices": indices[:args.batch_size].tolist(),
        "checkpoint_reference_diagnostics": reference, "candidates": {},
    }
    for label, scale in (("unit", 1.0), ("sqrt_bins", math.sqrt(spectral_dim)), ("original_bins", float(spectral_dim))):
        model = new_model()
        initial_hash = state_hash(model)
        # Re-seed after construction to match the VAE sampling noise too.
        set_random_seed(1, include_cuda=True)
        print(f"Starting {label}: projection scale {scale}", flush=True)
        history = run_candidate(model, batches, scale, args.steps)
        summary["candidates"][label] = {"scale": scale, "initial_model_sha256": initial_hash, "history": history}
        (args.output / f"{label}.json").write_text(json.dumps(summary["candidates"][label], indent=2, allow_nan=False))
        del model
        torch.cuda.empty_cache()
    if len({c["initial_model_sha256"] for c in summary["candidates"].values()}) != 1:
        raise RuntimeError("candidate initialization mismatch")
    summary["status"] = "complete"
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, allow_nan=False))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for label, candidate in summary["candidates"].items():
        records = candidate["history"]
        for ax, key, title in zip(axes,
                ("central_saturation_fraction", "weight_deviation_max", "projection_gradient_norm"),
                ("Projection saturation", "Maximum deviation from uniform", "Projection gradient norm")):
            selected = [r for r in records if key in r]
            ax.plot([r["step"] for r in selected], [r[key] for r in selected], label=label)
            ax.set_title(title)
            ax.set_xlabel("Learning step")
    axes[0].set_ylim(-0.02, 1.02)
    axes[1].set_yscale("symlog", linthresh=1e-8)
    axes[2].set_yscale("symlog", linthresh=1e-10)
    axes[0].legend()
    fig.suptitle("Small-sample attention diagnostic: not a biological comparison")
    fig.tight_layout()
    fig.savefig(args.output / "scaling_diagnostic.png", dpi=180)
    plt.close(fig)
    print(f"Diagnostic complete: {args.output}", flush=True)


if __name__ == "__main__":
    main()

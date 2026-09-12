"""Loss and training helpers for the Spatial-msiPL VAE."""

import json
import random
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset


def set_random_seed(seed, include_cuda=False):
    """Seed CPU libraries and, only when requested, PyTorch CUDA generators."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if include_cuda:
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA seeding was requested but CUDA is unavailable")
        torch.cuda.manual_seed_all(seed)


def msipl_vae_loss(reconstruction, target, mean, log_variance, beta=1.0):
    """Return total, reconstruction, and KL losses.

    The reconstruction term reproduces msiPL's categorical cross-entropy rule.
    Decoder values are normalized across m/z before cross-entropy is calculated,
    just as Keras does for categorical predictions. ``beta`` is retained as an
    explicit parameter but is 1.0 for the standard VAE used in this task.
    """
    if reconstruction.shape != target.shape:
        raise ValueError("reconstruction and target must have the same shape")
    if mean.shape != log_variance.shape:
        raise ValueError("mean and log_variance must have the same shape")

    epsilon = torch.finfo(reconstruction.dtype).eps
    probabilities = reconstruction / reconstruction.sum(dim=1, keepdim=True).clamp_min(epsilon)
    probabilities = probabilities.clamp(min=epsilon, max=1.0 - epsilon)
    reconstruction_per_sample = -(
        target * torch.log(probabilities)
    ).sum(dim=1) * target.shape[1]
    reconstruction_loss = reconstruction_per_sample.mean()

    kl_per_sample = -0.5 * torch.sum(
        1.0 + log_variance - mean.pow(2) - log_variance.exp(), dim=1
    )
    kl_loss = kl_per_sample.mean()
    total_loss = reconstruction_loss + float(beta) * kl_loss
    return total_loss, reconstruction_loss, kl_loss


def select_training_indices(dataset_size, maximum_samples, seed):
    """Select a fixed random subset, or every index when no limit is requested."""
    if maximum_samples is None or maximum_samples >= dataset_size:
        return list(range(dataset_size))
    if maximum_samples < 2:
        raise ValueError("maximum_samples must be at least 2")
    generator = np.random.default_rng(seed)
    return sorted(generator.choice(dataset_size, size=maximum_samples, replace=False).tolist())


def train_vae(
    model,
    dataset,
    output_directory,
    checkpoint_directory=None,
    epochs=1,
    batch_size=4,
    learning_rate=1e-3,
    beta=1.0,
    maximum_samples=None,
    seed=1,
    device="cpu",
):
    """Train a VAE and save its checkpoint, history, and experiment metadata."""
    if epochs < 1:
        raise ValueError("epochs must be at least 1")
    if batch_size < 2:
        raise ValueError("batch_size must be at least 2 because the model uses batch normalization")

    torch_device = torch.device(device)
    set_random_seed(seed, include_cuda=torch_device.type == "cuda")
    selected_indices = select_training_indices(len(dataset), maximum_samples, seed)
    if len(selected_indices) < batch_size:
        raise ValueError("the selected training subset must contain at least one full batch")

    model.to(torch_device)
    subset = Subset(dataset, selected_indices)
    loader_generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        subset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=True,
        num_workers=0,
        generator=loader_generator,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    history = []
    for epoch in range(1, epochs + 1):
        model.train()
        totals = {"total": 0.0, "reconstruction": 0.0, "kl": 0.0, "samples": 0}
        for batch in loader:
            contextual = batch["input"].to(torch_device, dtype=torch.float32)
            target = batch["target"].to(torch_device, dtype=torch.float32)

            optimizer.zero_grad(set_to_none=True)
            reconstruction, mean, log_variance = model(contextual)
            total_loss, reconstruction_loss, kl_loss = msipl_vae_loss(
                reconstruction, target, mean, log_variance, beta=beta
            )
            total_loss.backward()
            optimizer.step()

            sample_count = contextual.shape[0]
            totals["total"] += float(total_loss.detach()) * sample_count
            totals["reconstruction"] += float(reconstruction_loss.detach()) * sample_count
            totals["kl"] += float(kl_loss.detach()) * sample_count
            totals["samples"] += sample_count

        record = {
            "epoch": epoch,
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "total_loss": totals["total"] / totals["samples"],
            "reconstruction_loss": totals["reconstruction"] / totals["samples"],
            "kl_loss": totals["kl"] / totals["samples"],
            "samples_seen": totals["samples"],
        }
        history.append(record)
        print(json.dumps(record), flush=True)
        scheduler.step()

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    if checkpoint_directory is None:
        checkpoint_directory = output_directory
    checkpoint_directory = Path(checkpoint_directory)
    checkpoint_directory.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_directory / "checkpoint.pt"
    history_path = output_directory / "training_history.json"
    metadata_path = output_directory / "metadata.json"

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    metadata = {
        "model": "SpatialVAE",
        "data_source": str(getattr(dataset, "path", "unspecified")),
        "model_configuration": model.configuration(),
        "parameter_count": parameter_count,
        "loss": "msiPL categorical cross-entropy + beta * KL divergence",
        "decoder_target": "isolated TIC-normalized central spectrum",
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "scheduler": "cosine annealing",
        "beta": beta,
        "seed": seed,
        "device": str(torch_device),
        "dataset_size": len(dataset),
        "selected_samples": len(selected_indices),
        "samples_per_epoch": history[-1]["samples_seen"],
        "checkpoint": str(checkpoint_path),
        "status": "complete",
    }
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "model_configuration": model.configuration(),
            "training_configuration": metadata,
            "history": history,
        },
        checkpoint_path,
    )
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata, history

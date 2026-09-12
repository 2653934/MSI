"""Loss and training helpers for the Spatial-msiPL VAE."""

import json
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, Subset


def set_random_seed(seed, include_cuda=False):
    """Seed CPU libraries and, only when requested, PyTorch CUDA generators."""
    random.seed(seed)
    np.random.seed(seed)
    # torch.manual_seed also probes CUDA in this PyTorch build. Seed the CPU
    # generator directly so CPU-only validation does not emit GPU warnings.
    torch.random.default_generator.manual_seed(seed)
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


def _atomic_json_write(path, value):
    """Write JSON through a temporary file so interruption cannot truncate it."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    temporary_path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary_path.replace(path)


def _atomic_torch_save(value, path):
    """Write a PyTorch checkpoint atomically on the same filesystem."""
    temporary_path = path.with_name(f"{path.name}.tmp")
    torch.save(value, temporary_path)
    temporary_path.replace(path)


def _optimizer_to(optimizer, device):
    """Move optimizer tensors restored from a CPU checkpoint to the target device."""
    for state in optimizer.state.values():
        for name, value in state.items():
            if torch.is_tensor(value):
                state[name] = value.to(device)


def _capture_random_state(include_cuda):
    state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch_cpu": torch.get_rng_state(),
    }
    if include_cuda:
        state["torch_cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_random_state(state, include_cuda):
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch_cpu"].cpu())
    if include_cuda:
        torch.cuda.set_rng_state_all(
            [generator_state.cpu() for generator_state in state["torch_cuda"]]
        )


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
    experiment_metadata=None,
    save_checkpoint=True,
    checkpoint_interval=0,
    resume_checkpoint=None,
):
    """Train a VAE with optional exact epoch-boundary checkpoint/resume support."""
    if epochs < 1:
        raise ValueError("epochs must be at least 1")
    if batch_size < 2:
        raise ValueError("batch_size must be at least 2 because the model uses batch normalization")
    if checkpoint_interval < 0:
        raise ValueError("checkpoint_interval cannot be negative")
    if resume_checkpoint is not None and not save_checkpoint:
        raise ValueError("resume_checkpoint requires save_checkpoint=True")

    torch_device = torch.device(device)
    uses_cuda = torch_device.type == "cuda"
    set_random_seed(seed, include_cuda=uses_cuda)
    selected_indices = select_training_indices(len(dataset), maximum_samples, seed)
    if len(selected_indices) < batch_size:
        raise ValueError("the selected training subset must contain at least one full batch")

    output_directory = Path(output_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    history_path = output_directory / "training_history.json"
    metadata_path = output_directory / "metadata.json"
    progress_path = output_directory / "progress.json"

    checkpoint_path = None
    latest_checkpoint_path = None
    if save_checkpoint:
        if checkpoint_directory is None:
            checkpoint_directory = output_directory
        checkpoint_directory = Path(checkpoint_directory)
        checkpoint_directory.mkdir(parents=True, exist_ok=True)
        checkpoint_path = checkpoint_directory / "checkpoint.pt"
        latest_checkpoint_path = checkpoint_directory / "checkpoint_latest.pt"

    if uses_cuda:
        torch.cuda.reset_peak_memory_stats(torch_device)
    model.to(torch_device)
    subset = Subset(dataset, selected_indices)
    # BatchNorm cannot train on a one-sample batch. Keep every other partial
    # final batch so a "full dataset" run really does see every selected pixel.
    drop_last = len(subset) % batch_size == 1
    loader_generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        subset,
        batch_size=batch_size,
        shuffle=True,
        drop_last=drop_last,
        num_workers=0,
        generator=loader_generator,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

    resume_signature = {
        "data_source": str(getattr(dataset, "path", "unspecified")),
        "dataset_size": len(dataset),
        "selected_indices": selected_indices,
        "model_configuration": model.configuration(),
        "target_epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "beta": beta,
        "seed": seed,
    }
    history = []
    start_epoch = 1
    resumed_from_epoch = 0
    previous_peak_allocated = 0
    previous_peak_reserved = 0
    if resume_checkpoint is not None:
        resume_checkpoint = Path(resume_checkpoint)
        checkpoint = torch.load(resume_checkpoint, map_location="cpu")
        if checkpoint.get("resume_signature") != resume_signature:
            raise ValueError(
                "checkpoint configuration does not match this training run"
            )
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        _optimizer_to(optimizer, torch_device)
        scheduler.load_state_dict(checkpoint["scheduler_state_dict"])
        loader_generator.set_state(checkpoint["loader_generator_state"].cpu())
        history = checkpoint["history"]
        resumed_from_epoch = int(checkpoint["completed_epochs"])
        start_epoch = resumed_from_epoch + 1
        previous_peak_allocated = int(
            checkpoint.get("peak_gpu_memory_allocated_bytes") or 0
        )
        previous_peak_reserved = int(
            checkpoint.get("peak_gpu_memory_reserved_bytes") or 0
        )
        _restore_random_state(checkpoint["random_state"], uses_cuda)
        print(
            json.dumps(
                {
                    "resumed_from": str(resume_checkpoint),
                    "completed_epochs": resumed_from_epoch,
                    "next_epoch": start_epoch,
                }
            ),
            flush=True,
        )
    if start_epoch > epochs:
        raise ValueError("checkpoint has already completed the requested epochs")

    def checkpoint_payload(completed_epochs, training_configuration):
        peak_allocated = previous_peak_allocated
        peak_reserved = previous_peak_reserved
        if uses_cuda:
            peak_allocated = max(
                peak_allocated, int(torch.cuda.max_memory_allocated(torch_device))
            )
            peak_reserved = max(
                peak_reserved, int(torch.cuda.max_memory_reserved(torch_device))
            )
        return {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "scheduler_state_dict": scheduler.state_dict(),
            "model_configuration": model.configuration(),
            "training_configuration": training_configuration,
            "resume_signature": resume_signature,
            "completed_epochs": completed_epochs,
            "history": history,
            "loader_generator_state": loader_generator.get_state(),
            "random_state": _capture_random_state(uses_cuda),
            "peak_gpu_memory_allocated_bytes": peak_allocated or None,
            "peak_gpu_memory_reserved_bytes": peak_reserved or None,
        }

    session_start = time.perf_counter()
    for epoch in range(start_epoch, epochs + 1):
        if uses_cuda:
            torch.cuda.synchronize(torch_device)
        epoch_start = time.perf_counter()
        model.train()
        totals = {"total": 0.0, "reconstruction": 0.0, "kl": 0.0, "samples": 0}
        for batch in loader:
            target = batch["target"].to(torch_device, dtype=torch.float32)

            optimizer.zero_grad(set_to_none=True)
            if getattr(model, "uses_neighbourhood_batch", False):
                neighbours = batch["neighbours"].to(
                    torch_device, dtype=torch.float32
                )
                neighbour_mask = batch["neighbour_mask"].to(
                    torch_device, dtype=torch.bool
                )
                model_outputs = model(target, neighbours, neighbour_mask)
            else:
                contextual = batch["input"].to(
                    torch_device, dtype=torch.float32
                )
                model_outputs = model(contextual)
            reconstruction, mean, log_variance = model_outputs[:3]
            total_loss, reconstruction_loss, kl_loss = msipl_vae_loss(
                reconstruction, target, mean, log_variance, beta=beta
            )
            total_loss.backward()
            optimizer.step()

            sample_count = target.shape[0]
            totals["total"] += float(total_loss.detach()) * sample_count
            totals["reconstruction"] += float(reconstruction_loss.detach()) * sample_count
            totals["kl"] += float(kl_loss.detach()) * sample_count
            totals["samples"] += sample_count

        if uses_cuda:
            torch.cuda.synchronize(torch_device)
        epoch_seconds = time.perf_counter() - epoch_start
        record = {
            "epoch": epoch,
            "learning_rate": float(optimizer.param_groups[0]["lr"]),
            "total_loss": totals["total"] / totals["samples"],
            "reconstruction_loss": totals["reconstruction"] / totals["samples"],
            "kl_loss": totals["kl"] / totals["samples"],
            "samples_seen": totals["samples"],
            "epoch_seconds": epoch_seconds,
            "samples_per_second": totals["samples"] / epoch_seconds,
        }
        history.append(record)
        print(json.dumps(record), flush=True)
        scheduler.step()

        _atomic_json_write(history_path, history)
        progress = {
            "status": "in_progress" if epoch < epochs else "finalizing",
            "completed_epochs": epoch,
            "target_epochs": epochs,
            "last_epoch": record,
            "resume_checkpoint": (
                str(latest_checkpoint_path) if latest_checkpoint_path else None
            ),
        }
        _atomic_json_write(progress_path, progress)
        if (
            save_checkpoint
            and checkpoint_interval > 0
            and epoch < epochs
            and epoch % checkpoint_interval == 0
        ):
            _atomic_torch_save(
                checkpoint_payload(epoch, progress), latest_checkpoint_path
            )
            print(
                json.dumps(
                    {
                        "saved_resume_checkpoint": str(latest_checkpoint_path),
                        "completed_epochs": epoch,
                    }
                ),
                flush=True,
            )

    session_training_seconds = time.perf_counter() - session_start
    training_seconds = sum(record["epoch_seconds"] for record in history)
    peak_gpu_memory_allocated = None
    peak_gpu_memory_reserved = None
    device_name = "CPU"
    if uses_cuda:
        peak_gpu_memory_allocated = max(
            previous_peak_allocated,
            int(torch.cuda.max_memory_allocated(torch_device)),
        )
        peak_gpu_memory_reserved = max(
            previous_peak_reserved,
            int(torch.cuda.max_memory_reserved(torch_device)),
        )
        device_name = torch.cuda.get_device_name(torch_device)

    parameter_count = sum(parameter.numel() for parameter in model.parameters())
    metadata = {
        "model": model.__class__.__name__,
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
        "device_name": device_name,
        "dataset_size": len(dataset),
        "selected_samples": len(selected_indices),
        "selected_indices": selected_indices,
        "samples_per_epoch": history[-1]["samples_seen"],
        "drop_last": drop_last,
        "training_seconds": training_seconds,
        "session_training_seconds": session_training_seconds,
        "overall_samples_per_second": (
            sum(record["samples_seen"] for record in history) / training_seconds
        ),
        "peak_gpu_memory_allocated_bytes": peak_gpu_memory_allocated,
        "peak_gpu_memory_reserved_bytes": peak_gpu_memory_reserved,
        "checkpoint_saved": bool(save_checkpoint),
        "checkpoint_interval_epochs": checkpoint_interval,
        "checkpoint": str(checkpoint_path) if checkpoint_path is not None else None,
        "resumed_from_checkpoint": (
            str(resume_checkpoint) if resume_checkpoint is not None else None
        ),
        "resumed_from_epoch": resumed_from_epoch,
        "experiment": experiment_metadata or {},
        "status": "complete",
    }
    if save_checkpoint:
        _atomic_torch_save(
            checkpoint_payload(epochs, metadata), checkpoint_path
        )
        if latest_checkpoint_path.exists():
            latest_checkpoint_path.unlink()
    _atomic_json_write(history_path, history)
    _atomic_json_write(metadata_path, metadata)
    _atomic_json_write(
        progress_path,
        {
            "status": "complete",
            "completed_epochs": epochs,
            "target_epochs": epochs,
            "checkpoint": str(checkpoint_path) if checkpoint_path else None,
        },
    )
    return metadata, history

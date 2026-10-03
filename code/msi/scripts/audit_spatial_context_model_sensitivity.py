#!/usr/bin/env python3
"""Probe frozen 3x3 VAE responses to real, shuffled, and zero contexts.

The same sampled central spectra are used under every input condition. Labels
only define the previously sampled boundary/interior groups, never model inputs.
This is an in-sample reconstruction/representation diagnostic, not peak scoring.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
import torch

from run_spatial_msipl_gmm_integrated_gradients import load_model
from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
    checkpoint_input_spec,
    tic_normalize,
)


CONDITIONS = ("real", "shuffled", "zero")


def read_selected_pixels(path):
    with path.open(newline="", encoding="utf-8") as handle:
        selected = list(csv.DictReader(handle))
    if not selected or len({int(row["index"]) for row in selected}) != len(selected):
        raise ValueError("input audit must contain distinct selected pixels")
    if any(row["group"] not in ("boundary", "interior") for row in selected):
        raise ValueError("unknown boundary/interior group")
    return selected


def context_batches(dataset, shuffled_sources, selected, start, batch_size):
    batch_rows = selected[start:start + batch_size]
    samples = [dataset[int(row["index"])] for row in batch_rows]
    central = np.stack([sample["target"] for sample in samples])
    real = np.stack([sample["neighbours"] for sample in samples])
    mask = np.stack([sample["neighbour_mask"] for sample in samples])
    shuffled = np.zeros_like(real)
    for batch_index, row in enumerate(batch_rows):
        sources = shuffled_sources[int(row["index"])]
        valid = mask[batch_index]
        shuffled[batch_index, valid] = tic_normalize(dataset._spectra[sources[valid]])
    return batch_rows, central, mask, {
        "real": real,
        "shuffled": shuffled,
        "zero": np.zeros_like(real),
    }


def scored_outputs(model, central, neighbours, mask):
    """Deterministic encoder-mean reconstruction using the training loss scale."""
    mean, _, _, _ = model.encode(central, neighbours, mask)
    reconstruction = model.vae.decode(mean)
    epsilon = torch.finfo(reconstruction.dtype).eps
    probabilities = reconstruction / reconstruction.sum(dim=1, keepdim=True).clamp_min(epsilon)
    probabilities = probabilities.clamp(min=epsilon, max=1.0 - epsilon)
    cross_entropy = -(central * probabilities.log()).sum(dim=1) * central.shape[1]
    return mean, cross_entropy


def aggregate(rows):
    output = {}
    for training_context in ("real", "shuffled"):
        training_rows = [row for row in rows if row["trained_on"] == training_context]
        output[training_context] = {}
        for group in ("all", "boundary", "interior"):
            group_rows = (
                training_rows if group == "all"
                else [row for row in training_rows if row["group"] == group]
            )
            output[training_context][group] = {"pixels": len(group_rows)}
            for field in (
                "real_cross_entropy", "shuffled_cross_entropy", "zero_cross_entropy",
                "shuffled_minus_real_cross_entropy", "zero_minus_real_cross_entropy",
                "real_shuffled_latent_l2", "real_zero_latent_l2",
            ):
                output[training_context][group][f"mean_{field}"] = (
                    float(np.mean([row[field] for row in group_rows]))
                    if group_rows else None
                )
    return output


def audit(input_path, input_audit, checkpoints, output_dir, batch_size, device):
    selected = read_selected_pixels(input_audit)
    dataset = CachedH5SpatialContextDataset(
        input_path, include_neighbourhood=True, window_size=3
    )
    checkpoint_data = None
    shuffled_dataset = None
    try:
        if any(not 0 <= int(row["index"]) < len(dataset) for row in selected):
            raise ValueError("sampled index outside dataset")
        checkpoint_data = {
            key: torch.load(path, map_location="cpu") for key, path in checkpoints.items()
        }
        real_spec = checkpoint_input_spec(checkpoint_data["real"])
        shuffled_spec = checkpoint_input_spec(checkpoint_data["shuffled"])
        if (real_spec["window_size"] != 3 or real_spec["context_mode"] != "measured"
                or shuffled_spec["window_size"] != 3
                or shuffled_spec["context_mode"] != "shuffled"):
            raise ValueError("checkpoints are not the expected 3x3 real/shuffled pair")
        shuffled_dataset = H5SpatialContextDataset(
            input_path, window_size=3, context_mode="shuffled",
            context_seed=int(shuffled_spec["context_seed"]),
        )
        if (shuffled_dataset.context_permutation_sha256
                != shuffled_spec["context_permutation_sha256"]):
            raise ValueError("shuffled checkpoint input permutation differs")
        if not np.array_equal(dataset.neighbour_slots, shuffled_dataset.neighbour_slots):
            raise ValueError("checkpoint contexts have different geometry")
        audit_summary_path = input_audit.with_name(f"{input_path.stem}.json")
        audit_summary = json.loads(audit_summary_path.read_text(encoding="utf-8"))
        if (audit_summary.get("status") != "valid"
                or audit_summary.get("dataset") != input_path.stem
                or audit_summary.get("context_permutation_sha256")
                != shuffled_spec["context_permutation_sha256"]):
            raise ValueError("sampled pixels do not match this shuffled checkpoint")

        rows = []
        for training_context in ("real", "shuffled"):
            variant = "uniform_mean" if training_context == "real" else "shuffled_uniform"
            model, _ = load_model(
                checkpoints[training_context], dataset.n_mz, variant, device,
                checkpoint=checkpoint_data[training_context],
            )
            model.eval()
            with torch.inference_mode():
                for start in range(0, len(selected), batch_size):
                    batch_rows, central_np, mask_np, contexts_np = context_batches(
                        dataset, shuffled_dataset.context_source_slots,
                        selected, start, batch_size,
                    )
                    central = torch.as_tensor(central_np, dtype=torch.float32, device=device)
                    mask = torch.as_tensor(mask_np, dtype=torch.bool, device=device)
                    outcomes = {}
                    for condition in CONDITIONS:
                        neighbours = torch.as_tensor(
                            contexts_np[condition], dtype=torch.float32, device=device
                        )
                        latent, loss = scored_outputs(model, central, neighbours, mask)
                        outcomes[condition] = (latent, loss)
                    real_latent, real_loss = outcomes["real"]
                    shuffled_latent, shuffled_loss = outcomes["shuffled"]
                    zero_latent, zero_loss = outcomes["zero"]
                    latent_shuffled = torch.linalg.vector_norm(
                        real_latent - shuffled_latent, dim=1
                    ).cpu().numpy()
                    latent_zero = torch.linalg.vector_norm(
                        real_latent - zero_latent, dim=1
                    ).cpu().numpy()
                    losses = {
                        condition: outcome[1].cpu().numpy()
                        for condition, outcome in outcomes.items()
                    }
                    for index, source in enumerate(batch_rows):
                        rows.append({
                            "trained_on": training_context,
                            "index": int(source["index"]),
                            "group": source["group"],
                            "class_label_posthoc": int(source["class_label"]),
                            "real_cross_entropy": float(real_loss[index]),
                            "shuffled_cross_entropy": float(shuffled_loss[index]),
                            "zero_cross_entropy": float(zero_loss[index]),
                            "shuffled_minus_real_cross_entropy": float(
                                losses["shuffled"][index] - losses["real"][index]
                            ),
                            "zero_minus_real_cross_entropy": float(
                                losses["zero"][index] - losses["real"][index]
                            ),
                            "real_shuffled_latent_l2": float(latent_shuffled[index]),
                            "real_zero_latent_l2": float(latent_zero[index]),
                        })
            del model
            if device.type == "cuda":
                torch.cuda.empty_cache()

        result = {
            "status": "valid",
            "dataset": input_path.stem,
            "source_h5": str(input_path),
            "input_audit": str(input_audit),
            "checkpoints": {key: str(value) for key, value in checkpoints.items()},
            "shuffled_context_seed": int(shuffled_spec["context_seed"]),
            "shuffled_context_permutation_sha256": shuffled_spec["context_permutation_sha256"],
            "sampled_pixels": len(selected),
            "device": str(device),
            "evaluation": "frozen, deterministic encoder-mean reconstruction on training sections",
            "cross_entropy": "scaled categorical cross-entropy; lower is better",
            "limitation": (
                "Context swaps are out-of-training-distribution interventions; "
                "they test response, not whether context improves held-out peak picking. "
                "Expert labels only define post-hoc groups."
            ),
            "summary": aggregate(rows),
        }
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"{input_path.stem}.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        with (output_dir / f"{input_path.stem}_pixels.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return result
    finally:
        dataset.close()
        if shuffled_dataset is not None:
            shuffled_dataset.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-audit", type=Path, required=True)
    parser.add_argument("--real-checkpoint", type=Path, required=True)
    parser.add_argument("--shuffled-checkpoint", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("batch size must be positive")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; stopped before loading a model")
    device = torch.device("cuda")
    result = audit(
        args.input, args.input_audit,
        {"real": args.real_checkpoint, "shuffled": args.shuffled_checkpoint},
        args.output_dir, args.batch_size, device,
    )
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()

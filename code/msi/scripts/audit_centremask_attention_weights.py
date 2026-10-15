#!/usr/bin/env python3
"""Item G mechanism check: attention-weight entropy of a centre-masked model.

Reuses the existing diagnostic (audit_attention_weights.weight_statistics and
evaluate_checkpoint) on the same 128 sampled centres as before: measured
centres with at least two valid neighbours, drawn with sample seed 20261007.
Also measures the frozen seed-1 unmasked checkpoint of the same arm with the
same centres, so both numbers come from one code path. Label-free; no peak
scores, GMM or IG are touched. Evaluation uses the unmasked centre.

Rule (supervisor chat, 2026-10-15 13:30, item G rule 1; applied by the
summariser, not here): "masking made attention selective" if the median
normalised entropy of G1 falls below 0.95 on both exploratory sections.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from audit_attention_weights import checkpoint_root, evaluate_checkpoint
from spatial_msipl.provenance import atomic_write_json, require_slurm

SAMPLE_SIZE = 128
SAMPLE_SEED = 20261007


def sampled_centres(dataset, size=SAMPLE_SIZE, seed=SAMPLE_SEED):
    """The historical sampling rule of audit_attention_weights.py."""
    eligible = np.flatnonzero(np.sum(dataset.neighbour_slots >= 0, axis=1) >= 2)
    return np.sort(np.random.default_rng(seed).choice(
        eligible, size=min(size, len(eligible)), replace=False))


def main():
    from spatial_msipl.preprocessing import CachedH5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--arm", choices=("real_attention", "shuffled_attention"), required=True)
    parser.add_argument("--context-seed", type=int, default=1701)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-outside-slurm", action="store_true")
    args = parser.parse_args()
    require_slurm(args.allow_outside_slurm)

    mode = "measured" if args.arm == "real_attention" else "shuffled"
    dataset = CachedH5SpatialContextDataset(
        args.input, include_neighbourhood=True, window_size=3, context_mode=mode,
        context_seed=args.context_seed if mode == "shuffled" else None)
    try:
        indices = sampled_centres(dataset)
        masked = evaluate_checkpoint(args.checkpoint, dataset, indices, args.arm, seed=1)
        unmasked_path = checkpoint_root(args.input.stem, 1, args.arm) / "checkpoint.pt"
        unmasked = evaluate_checkpoint(unmasked_path, dataset, indices, args.arm, seed=1)
    finally:
        dataset.close()
    summary = {
        "status": "valid",
        "scope": "item G mechanism check; label-free sampled attention weights; no peak scores",
        "section": args.input.stem, "arm": args.arm, "context_mode": mode,
        "sample_seed": SAMPLE_SEED, "sampled_centres": int(len(indices)),
        "sampled_indices_sha256": hashlib.sha256(
            np.asarray(indices, dtype=np.int64).tobytes()).hexdigest(),
        "centremask_p50": masked,
        "unmasked_seed1_same_centres": unmasked,
        "rule_reference": "median normalised entropy < 0.95 on both exploratory sections (G1)",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, summary)
    print(f"{args.input.stem} {args.arm}: mechanism check written", flush=True)


if __name__ == "__main__":
    main()

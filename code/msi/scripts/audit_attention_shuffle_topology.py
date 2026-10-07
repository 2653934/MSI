#!/usr/bin/env python3
"""Label-free test of spatial overlap retained by the frozen context shuffle."""

import argparse
import json
from pathlib import Path

import numpy as np


def jaccard(left, right):
    a = set(np.asarray(left)[np.asarray(left) >= 0].tolist())
    b = set(np.asarray(right)[np.asarray(right) >= 0].tolist())
    return len(a & b) / len(a | b) if a or b else 0.0


def adjacent_pairs(x, y):
    locations = {(int(a), int(b)): i for i, (a, b) in enumerate(zip(x, y))}
    pairs = []
    for i, (a, b) in enumerate(zip(x, y)):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == dy == 0:
                    continue
                j = locations.get((int(a) + dx, int(b) + dy))
                if j is not None and i < j:
                    pairs.append((i, j))
    return np.asarray(pairs, dtype=np.int64).reshape(-1, 2)


def distant_pairs(x, y, count, seed):
    rng = np.random.default_rng(seed)
    pairs = []
    for _ in range(count):
        for _attempt in range(1000):
            i, j = rng.choice(len(x), size=2, replace=False)
            if max(abs(int(x[i]) - int(x[j])), abs(int(y[i]) - int(y[j]))) > 2:
                pairs.append((int(i), int(j)))
                break
        else:
            raise ValueError("cannot sample distant measured-pixel pairs")
    return np.asarray(pairs, dtype=np.int64)


def scores(slots, pairs):
    return np.asarray([jaccard(slots[i], slots[j]) for i, j in pairs], dtype=np.float64)


def main():
    from spatial_msipl.preprocessing import H5SpatialContextDataset

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--input-swap-summary", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--seed", type=int, default=20261007)
    args = parser.parse_args()

    previous = json.loads(args.input_swap_summary.read_text(encoding="utf-8"))
    if previous.get("status") != "valid" or previous.get("section") != args.input.stem:
        raise ValueError("input-swap provenance does not validate this section")
    if Path(previous["input"]).resolve() != args.input.resolve():
        raise ValueError("input-swap source HDF5 differs")

    real = H5SpatialContextDataset(args.input, window_size=3)
    shuffled = H5SpatialContextDataset(
        args.input, window_size=3, context_mode="shuffled",
        context_seed=int(previous["shuffle_seed"]),
    )
    if shuffled.context_permutation_sha256 != previous["shuffle_source_slots_sha256"]:
        raise ValueError("frozen shuffle source mapping differs")
    if not np.array_equal(real.neighbour_slots, shuffled.neighbour_slots):
        raise ValueError("measured topology differs")

    adjacent = adjacent_pairs(real.x, real.y)
    if len(adjacent) == 0:
        raise ValueError("no adjacent measured pixels")
    distant = distant_pairs(real.x, real.y, len(adjacent), args.seed)
    groups = {
        "real_adjacent": scores(real.neighbour_slots, adjacent),
        "real_distant": scores(real.neighbour_slots, distant),
        "shuffled_adjacent": scores(shuffled.context_source_slots, adjacent),
        "shuffled_distant": scores(shuffled.context_source_slots, distant),
    }
    summary = {
        "status": "valid",
        "scope": "label-free source-index topology; not model quality or peak performance",
        "section": args.input.stem,
        "source_input_swap_summary": str(args.input_swap_summary),
        "shuffle_source_slots_sha256": shuffled.context_permutation_sha256,
        "distant_sampling_seed": args.seed,
        "adjacent_pair_count": len(adjacent),
        "distant_pair_count": len(distant),
        "source_jaccard": {
            key: {"mean": float(np.mean(value)), "median": float(np.median(value)),
                  "positive_fraction": float(np.mean(value > 0))}
            for key, value in groups.items()
        },
        "interpretation_limit": (
            "A fixed global shuffle can retain neighbouring-window source overlap. "
            "This audit tests that mechanism only. Overlap does not prove a model uses "
            "the signal or explain a peak-score difference; pixels are not independent patients."
        ),
    }

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    labels = ["Real\nadjacent", "Real\ndistant", "Shuffled\nadjacent", "Shuffled\ndistant"]
    values = [groups[k].mean() for k in groups]
    ax.bar(labels, values, color=["#287c64", "#7eb3a3", "#7857a6", "#bdaed1"])
    ax.set_ylabel("Mean Jaccard overlap of context source pixels")
    ax.set_ylim(0, max(values) * 1.2 if max(values) else 1)
    ax.set_title(f"{args.input.stem}: does the fixed shuffle retain neighbourhood structure?")
    fig.tight_layout()
    args.output.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output / "source_overlap.png", dpi=180)
    plt.close(fig)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

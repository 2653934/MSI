#!/usr/bin/env python3
"""Ion-image export for the RCC figures (supervisor chat 2026-10-16 20:41, item 2).

Read-only, CPU only. For one run and arm it writes one .npz (at most a few MB) with:
the 3-class label mask and the GMM hard-assignment map on the pixel grid, the pixel
coordinates, and the raw-intensity ion images (the representation the reference
PCCs use) of the top 6 bins under IG, posterior-|PCC| (balanced) and the oracle,
with their m/z, ranks and per-class PCC. Rankings come from the saved fair-scoring
rankings_prefix.npz; nothing is re-ranked or re-scored. Labels are used only for
display and the stored per-class PCC.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_feature_matrix,
    read_h5_metadata,
)
from spatial_msipl.provenance import file_record, require_slurm

METHODS = ("integrated_gradients", "posterior_abs_pcc_balanced", "oracle")
TOP = 6
MAX_BYTES = 20 * 1024 * 1024


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--fair-scoring-dir", required=True, type=Path,
                        help="RCC bin-level fair-scoring folder for this run and arm")
    parser.add_argument("--output", required=True, type=Path, help=".npz path")
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real runs must be inside Slurm")
    return parser.parse_args()


def grid(values, x, y, fill=-1):
    image = np.full((int(y.max()), int(x.max())), fill, dtype=np.int64)
    image[y - 1, x - 1] = values
    return image


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    if args.output.exists():
        print(f"STALE: {args.output} exists; move it aside to rerun", file=sys.stderr)
        raise SystemExit(3)
    summary = json.loads((args.fair_scoring_dir / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete":
        raise SystemExit(f"{args.fair_scoring_dir}: fair scoring not complete")
    mz, labels, x, y, pixels_first = read_h5_metadata(args.input)
    gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    if not (np.array_equal(gmm["x"], x) and np.array_equal(gmm["y"], y)):
        raise SystemExit("attribution coordinates do not match the input")
    prefixes = np.load(args.fair_scoring_dir / "rankings_prefix.npz")
    correlations = load_correlations(args.input, labels, len(mz), pixels_first, args.chunk_size)
    classes = sorted(correlations)

    arrays = {
        "label_mask": grid(labels, x, y),
        "gmm_assignment_map": grid(gmm["component"].astype(np.int64), x, y),
        "x": x, "y": y, "mz_axis": mz,
        "class_values": np.asarray(classes, dtype=np.int64),
    }
    for method in METHODS:
        bins = np.asarray(prefixes[method][:TOP], dtype=np.int64)
        arrays[f"{method}__bins"] = bins
        arrays[f"{method}__ranks"] = np.arange(1, TOP + 1, dtype=np.int64)
        arrays[f"{method}__mz"] = mz[bins]
        arrays[f"{method}__pcc_per_class"] = np.stack(
            [correlations[c][bins] for c in classes], axis=1)
        arrays[f"{method}__ion_values"] = read_feature_matrix(args.input, bins, pixels_first)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, **arrays)
    size = args.output.stat().st_size
    if size > MAX_BYTES:
        args.output.unlink()
        raise SystemExit(f"export is {size} bytes, above the 20 MB limit; removed")
    record = {
        "status": "complete", "output": str(args.output), "bytes": size,
        "methods": list(METHODS), "top": TOP,
        "ion_value_representation": "raw intensity (as the reference PCCs)",
        "rankings_source": str(args.fair_scoring_dir / "rankings_prefix.npz"),
        "input": file_record(args.input),
        "label_use": "display and stored per-class PCC only; no ranking uses labels except the oracle",
    }
    args.output.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n",
                                                encoding="utf-8")
    print(f"wrote {args.output} ({size} bytes)")


if __name__ == "__main__":
    main()

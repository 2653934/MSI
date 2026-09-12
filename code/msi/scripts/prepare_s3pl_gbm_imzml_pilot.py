#!/usr/bin/env python3
"""Prepare one official GBM imzML section for a two-class S3PL pilot."""

import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np
from pyimzml.ImzMLParser import ImzMLParser


ALLOWED_DATASETS = {"GBM108_positive", "GBM108_negative"}


def create_ibd_link(source, destination):
    if destination.exists() or destination.is_symlink():
        if not destination.is_symlink() or destination.resolve() != source.resolve():
            raise FileExistsError(f"Unexpected existing IBD path: {destination}")
        return
    os.symlink(source, destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=sorted(ALLOWED_DATASETS))
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    args = parser.parse_args()

    source_root = args.source_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()
    source_imzml = source_root / f"{args.dataset}.imzML"
    source_ibd = source_root / f"{args.dataset}.ibd"
    source_mask = source_root / "masks" / f"{args.dataset}_mask.npy"
    for path in (source_imzml, source_ibd, source_mask):
        if not path.is_file():
            raise FileNotFoundError(path)

    output_imzml = output_root / f"{args.dataset}.imzML"
    output_ibd = output_root / f"{args.dataset}.ibd"
    output_mask = output_root / "masks" / f"{args.dataset}_mask.npy"
    summary_path = output_root / "preparation_summary.json"
    for path in (output_imzml, output_mask, summary_path):
        if path.exists():
            raise FileExistsError(f"Pilot input already prepared: {path}")

    imzml = ImzMLParser(str(source_imzml))
    coordinates = np.asarray(imzml.coordinates, dtype=np.int64)
    if coordinates.ndim != 2 or coordinates.shape[1] < 2:
        raise ValueError("Unexpected imzML coordinate array")
    x = coordinates[:, 0]
    y = coordinates[:, 1]

    official_mask = np.load(source_mask)
    rows = y - 1
    columns = x - 1
    if np.any(rows < 0) or np.any(columns < 0):
        raise ValueError("Coordinates must be one-based")
    if np.any(rows >= official_mask.shape[0]) or np.any(columns >= official_mask.shape[1]):
        raise ValueError("Spectrum coordinates exceed the official mask")

    official_measured = official_mask[rows, columns]
    measured_values = set(np.unique(official_measured).tolist())
    if measured_values != {1.0, 2.0}:
        raise ValueError(
            f"Expected official measured labels 1 and 2, found {measured_values}"
        )

    # S3PL evaluates two classes numbered 0 and 1. Background is left as zero,
    # but it is excluded because label correlations use measured coordinates only.
    semantic_mask = np.zeros(official_mask.shape, dtype=np.uint8)
    semantic_mask[rows, columns] = official_measured.astype(np.uint8) - 1

    output_root.mkdir(parents=True, exist_ok=True)
    output_mask.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_imzml, output_imzml)
    create_ibd_link(source_ibd, output_ibd)
    np.save(output_mask, semantic_mask)

    normal_count = int(np.count_nonzero(official_measured == 1))
    tumour_count = int(np.count_nonzero(official_measured == 2))
    summary = {
        "dataset": args.dataset,
        "source_imzml": str(source_imzml),
        "source_ibd": str(source_ibd),
        "source_mask": str(source_mask),
        "prepared_imzml": str(output_imzml),
        "prepared_ibd_is_symlink": output_ibd.is_symlink(),
        "prepared_mask": str(output_mask),
        "mask_rule": "at measured coordinates: official 1/2 -> S3PL 0/1",
        "measured_pixels": int(len(coordinates)),
        "normal_pixels": normal_count,
        "tumour_pixels": tumour_count,
        "status": "valid",
    }
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()

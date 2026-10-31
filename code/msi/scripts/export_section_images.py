#!/usr/bin/env python3
"""Read-only: per-pixel total ion current (TIC) or base-peak intensity, coordinates and
labels for the dataset figure and contact sheet.

The same computation as cluster jobs 79301 (TIC, all 24 sections) and 79303 (base peak,
the 8 GBM sections; the GBM HDF5 spectra are TIC-normalised, so their TIC is 1), which ran
it inline. Writes <section>.npz (x, y, tic or base_peak[, base_peak_bin], labels) and
summary.json; refuses existing files.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import h5py
import numpy as np

from evaluate_spatial_msipl_attributed_peaks import read_h5_metadata

FOLDERS = {"GBM": "gbm_massnet/", "CAC": "cac_msipl/", "RCC": "rcc_cardinal/"}
SECTIONS = {
    "GBM": ["GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2", "GBM22_1", "GBM22_2",
            "GBM39_1", "GBM39_2"],
    "CAC": ["40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL",
            "520TopL"],
    "RCC": ["RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
            "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01"],
}
STEP = 2048


def tic(path, mz, labels, pixels_first):
    values = np.zeros(len(labels), dtype=np.float64)
    with h5py.File(path, "r") as handle:
        data = handle["Data"]
        if pixels_first:
            for start in range(0, len(labels), STEP):
                values[start:start + STEP] = np.asarray(data[start:start + STEP, :],
                                                        dtype=np.float64).sum(axis=1)
        else:
            for start in range(0, len(mz), STEP):
                values += np.asarray(data[start:start + STEP, :], dtype=np.float64).sum(axis=0)
    return values


def base_peak(path, mz, labels, pixels_first):
    base = np.full(len(labels), -np.inf)
    argmax_bin = np.zeros(len(labels), dtype=np.int64)
    with h5py.File(path, "r") as handle:
        data = handle["Data"]
        if pixels_first:
            for start in range(0, len(labels), STEP):
                block = np.asarray(data[start:start + STEP, :], dtype=np.float64)
                base[start:start + STEP] = block.max(axis=1)
                argmax_bin[start:start + STEP] = block.argmax(axis=1)
        else:
            for start in range(0, len(mz), STEP):
                block = np.asarray(data[start:start + STEP, :], dtype=np.float64)
                better = block.max(axis=0) > base
                argmax_bin[better] = start + block.argmax(axis=0)[better]
                base = np.maximum(base, block.max(axis=0))
    return base, argmax_bin


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path,
                        help="folder holding gbm_massnet/, cac_msipl/ and rcc_cardinal/")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--measure", choices=("tic", "base_peak"), default="tic")
    parser.add_argument("--collections", nargs="+", default=list(SECTIONS),
                        choices=list(SECTIONS))
    args = parser.parse_args(argv)
    record = {}
    for collection in args.collections:
        for name in SECTIONS[collection]:
            path = str(args.data_root / FOLDERS[collection] / f"{name}.h5")
            target = os.path.join(args.output, name + ".npz")
            if os.path.exists(target):
                sys.exit("exists: " + target)
            mz, labels, x, y, pixels_first = read_h5_metadata(path)
            os.makedirs(args.output, exist_ok=True)
            if args.measure == "tic":
                np.savez_compressed(target, x=x, y=y, tic=tic(path, mz, labels, pixels_first),
                                    labels=labels)
                record[name] = {"input": path, "pixels": int(len(labels)), "bins": int(len(mz)),
                                "label_counts": {str(k): int(v) for k, v in
                                                 zip(*np.unique(labels, return_counts=True))},
                                "x_range": [int(x.min()), int(x.max())],
                                "y_range": [int(y.min()), int(y.max())]}
            else:
                base, argmax_bin = base_peak(path, mz, labels, pixels_first)
                np.savez_compressed(target, x=x, y=y, base_peak=base, base_peak_bin=argmax_bin,
                                    labels=labels)
                values, counts = np.unique(argmax_bin, return_counts=True)
                top = values[np.argsort(-counts)[:3]]
                record[name] = {"input": path, "pixels": int(len(labels)), "bins": int(len(mz)),
                                "base_peak_range": [float(base.min()), float(base.max())],
                                "most_common_base_peak_mz": [float(mz[b]) for b in top]}
    with open(os.path.join(args.output, "summary.json"), "w") as stream:
        json.dump(record, stream, indent=2)
    print(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())

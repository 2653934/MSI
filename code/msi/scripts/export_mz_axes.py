#!/usr/bin/env python3
"""Read-only: the m/z axis of every section, summarised per collection (dataset table).

The same computation as cluster job 79057 (which ran it inline): per collection, the
m/z range, the number of bins, the bin spacing in Da and ppm (minimum, median, maximum),
the Da spacing at several m/z, and whether all sections share one axis.
Refuses an existing output.
"""

import argparse
import json
import sys
from pathlib import Path

import h5py
import numpy as np

SECTIONS = {
    "GBM": ("gbm_massnet", ("GBM108_positive", "GBM108_negative", "GBM12_1", "GBM12_2",
                            "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2")),
    "CAC": ("cac_msipl", ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
                          "400TopL", "520TopL")),
    "RCC": ("rcc_cardinal", tuple(f"RCC_{run}" for run in (
        "MH0204_33", "UH0505_12", "UH0710_33", "UH9610_15", "UH9812_03", "UH9905_18",
        "UH9911_05", "UH9912_01"))),
}


def summarise(paths):
    axes = []
    for path in paths:
        with h5py.File(path, "r") as handle:
            axes.append(np.asarray(handle["mzArray"], dtype=np.float64).reshape(-1))
    first = axes[0]
    da = np.diff(first)
    ppm = da / first[:-1] * 1e6
    return {
        "sections": [Path(p).name for p in paths],
        "all_sections_identical_axis": bool(all(a.shape == first.shape and np.array_equal(a, first)
                                                for a in axes)),
        "max_abs_difference_to_first_section": float(max(
            np.max(np.abs(a - first)) if a.shape == first.shape else np.inf for a in axes)),
        "bins": int(first.size), "mz_min": float(first.min()), "mz_max": float(first.max()),
        "spacing_da": {"min": float(da.min()), "median": float(np.median(da)),
                       "max": float(da.max()), "mean": float(da.mean())},
        "spacing_ppm": {"min": float(ppm.min()), "median": float(np.median(ppm)),
                        "max": float(ppm.max())},
        "spacing_da_at_mz": {str(q): float(np.interp(q, first[:-1], da))
                             for q in (200, 400, 600, 800, 1000)
                             if first.min() <= q <= first.max()},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path,
                        help="folder holding gbm_massnet/, cac_msipl/ and rcc_cardinal/")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if args.output.exists():
        print(f"exists: {args.output}", file=sys.stderr)
        return 3
    out = {collection: summarise([str(args.data_root / folder / f"{name}.h5") for name in names])
           for collection, (folder, names) in SECTIONS.items()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w") as stream:
        json.dump(out, stream, indent=2)
    print(json.dumps({c: (v["bins"], v["all_sections_identical_axis"]) for c, v in out.items()}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

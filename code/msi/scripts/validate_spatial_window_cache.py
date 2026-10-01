#!/usr/bin/env python3
"""Check real-section cached and streaming inputs before fast GBM training."""

import argparse
import json

import numpy as np

from spatial_msipl.preprocessing import (
    CachedH5SpatialContextDataset,
    H5SpatialContextDataset,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--window-size", required=True, type=int, choices=(3, 5))
    parser.add_argument("--variant", required=True,
                        choices=("uniform_p5", "zero_p3", "shuffled_p3"))
    args = parser.parse_args()
    context_mode = "shuffled" if args.variant == "shuffled_p3" else "measured"
    kwargs = dict(include_neighbourhood=True, window_size=args.window_size,
                  context_mode=context_mode,
                  context_seed=1701 if context_mode == "shuffled" else None)
    streamed = H5SpatialContextDataset(args.input, **kwargs)
    cached = CachedH5SpatialContextDataset(args.input, **kwargs)
    try:
        if len(streamed) != len(cached):
            raise AssertionError("Cached and streamed dataset lengths differ")
        indices = sorted(set((0, 1, len(streamed) // 3, len(streamed) // 2,
                              2 * len(streamed) // 3, len(streamed) - 2,
                              len(streamed) - 1)))
        for index in indices:
            a, b = streamed[index], cached[index]
            for key in a:
                np.testing.assert_array_equal(a[key], b[key],
                                              err_msg=f"pixel={index} field={key}")
        print(json.dumps({"status": "valid", "input": args.input,
                          "variant": args.variant, "window_size": args.window_size,
                          "checked_indices": indices,
                          "cached_host_matrix_bytes": int(cached._spectra.nbytes)}),
              flush=True)
    finally:
        streamed.close()
        cached.close()


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Re-evaluate an existing S3PL checkpoint at an explicit peak budget."""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--number-peaks", required=True, type=int)
    args = parser.parse_args()

    if args.number_peaks < 1:
        raise ValueError("--number-peaks must be positive")
    if not args.config.is_file():
        raise FileNotFoundError(f"S3PL configuration does not exist: {args.config}")

    project_root = Path(__file__).resolve().parents[1]
    s3pl_root = project_root / "baselines" / "s3pl"
    sys.path.insert(0, str(s3pl_root))

    from test import test

    config = json.loads(args.config.read_text(encoding="utf-8"))
    training_name = config.get("training_name")
    if not training_name:
        raise ValueError(f"Missing training_name in {args.config}")

    suffix = f"_matched_{args.number_peaks}peaks"
    print(
        json.dumps(
            {
                "source_training_name": training_name,
                "matched_peak_count": args.number_peaks,
                "result_suffix": suffix,
                "training": False,
            },
            indent=2,
        ),
        flush=True,
    )
    score = test(
        config,
        test_indices=None,
        number_peaks_override=args.number_peaks,
        result_suffix=suffix,
    )
    print(json.dumps({"matched_mSCF1": score}, indent=2), flush=True)


if __name__ == "__main__":
    main()

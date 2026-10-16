#!/usr/bin/env python3
"""Per-section S3PL seed table against the published values (overnight items 2 and 3).

Reads each seed's released-protocol metrics.json, recomputes mSCF1 unrounded as
the mean of the four mixed F1 values, and writes section_table.csv and
summary.json with each seed, the published value (IonMorphNet
sota_comparison.py, investigation 19), the per-seed collection means and whether
each mean lies inside the published 95% CI. Descriptive only: a seed is never
selected. Reads local files only.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = {
    "cac": {
        "sections": ["40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL",
                     "400TopL", "520TopL"],
        "published": [0.68, 0.53, 0.61, 0.67, 0.63, 0.64, 0.35, 0.70],
        "published_mean": 0.601, "published_ci": [0.506, 0.697],
        "name": "{}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9",
        "seeds": {1: "results/baselines/s3pl",
                  2: "reproducibility/s3pl_cac_seeds/seed2_released/results/baselines/s3pl",
                  3: "reproducibility/s3pl_cac_seeds/seed3_released/results/baselines/s3pl"},
    },
    "rcc": {
        "sections": ["MH0204_33", "UH0505_12", "UH0710_33", "UH9610_15", "UH9812_03",
                     "UH9905_18", "UH9911_05", "UH9912_01"],
        "published": [0.56, 0.44, 0.48, 0.14, 0.50, 0.51, 0.56, 0.57],
        "published_mean": 0.470, "published_ci": [0.352, 0.588],
        "name": "{}_Attention3DConvAutoencoder_10epochs_1024_spectral_patch_size_5",
        "seeds": {s: f"reproducibility/s3pl_rcc/seed{s}_released/results/baselines/s3pl"
                  for s in (1, 2, 3)},
    },
}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collection", required=True, choices=sorted(COLLECTIONS))
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main():
    args = parse_arguments()
    spec = COLLECTIONS[args.collection]
    rows = []
    for section, published in zip(spec["sections"], spec["published"]):
        row = {"collection": args.collection.upper(), "section": section,
               "published_mSCF1": published}
        values = []
        for seed, root in spec["seeds"].items():
            path = ROOT / root / spec["name"].format(section) / "metrics.json"
            metrics = json.loads(path.read_text(encoding="utf-8"))
            value = float(np.mean([float(v) for v in metrics["mixed_f1"].values()]))
            row[f"seed{seed}_mSCF1"] = value
            row[f"seed{seed}_picked_peaks"] = int(metrics["number_picked_peaks"])
            values.append(value)
        row["seed_min"], row["seed_max"] = min(values), max(values)
        row["published_within_seed_range"] = min(values) <= published <= max(values)
        rows.append(row)
    low, high = spec["published_ci"]
    means = {seed: float(np.mean([r[f"seed{seed}_mSCF1"] for r in rows])) for seed in spec["seeds"]}
    summary = {
        "collection": args.collection.upper(),
        "descriptive": "seeds reported side by side; no seed is selected",
        "published_source": "IonMorphNet msianalyzer/external/s3pl/sota_comparison.py at 640406a (investigation 19)",
        "published_mean": spec["published_mean"], "published_95ci": spec["published_ci"],
        "seed_means": {str(s): m for s, m in means.items()},
        "seed_mean_inside_published_ci": {str(s): low <= m <= high for s, m in means.items()},
        "seed_mean_minus_published": {str(s): m - spec["published_mean"] for s, m in means.items()},
        "sections": rows,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with open(args.output / "section_table.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for seed, mean in means.items():
        print(f"seed {seed}: mean {mean:.4f} (published {spec['published_mean']}, CI {low}-{high})")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Hardware behind each runtime-table row (supervisor chat 2026-10-30 20:16, request 3).
Local only, from saved files. Training rows: the GPU recorded per run in
runtime_all_sections_v2.csv (cached loader; the report's 100-epoch VAE arms and the
10-epoch S3PL protocol). Ranking rows: the CPU model recorded per section in the
ranking-stage timing summaries (GBM/CAC ranking_stage_runtime, RCC
ranking_stage_runtime_rcc_bigbatch_shared, uniform_mean). Refuses an existing output.
"""

import argparse
import collections
import csv
import glob
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path("results/publication/current_evidence/runtime_all_sections_v2.csv")
RANKING = {"GBM": "results/diagnostics/ranking_stage_runtime",
           "CAC": "results/diagnostics/ranking_stage_runtime",
           "RCC": "results/diagnostics/ranking_stage_runtime_rcc_bigbatch_shared"}
TRAINING = {"VAE training": ("vae_central_only", "vae_uniform_mean"),
            "S3PL training": ("s3pl_10_epochs",)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root, output = args.project_root, args.output
    if output.exists():
        print(f"Output exists: {output} (never overwritten)", file=sys.stderr)
        return 3
    rows = []
    with open(root / RUNTIME, newline="", encoding="utf-8") as stream:
        runtime = [r for r in csv.DictReader(stream) if r["loader"] == "cached"]
    for label, methods in TRAINING.items():
        for collection in ("GBM", "CAC", "RCC"):
            runs = [r for r in runtime if r["collection"] == collection and r["method"] in methods]
            minutes = [float(r["training_seconds"]) / 60 for r in runs]
            rows.append({"row": label, "collection": collection, "runs": len(runs),
                         "median_minutes": statistics.median(minutes),
                         "hardware": "; ".join(f"{k} ({v})" for k, v in
                                               collections.Counter(r["gpu"] for r in runs).items())})
    for collection, folder in RANKING.items():
        cpus, sections = collections.Counter(), 0
        for path in sorted(glob.glob(str(root / folder / "*" / "uniform_mean" / "summary.json"))):
            section = Path(path).parents[1].name
            is_gbm, is_rcc = section.startswith("GBM"), section.startswith("RCC_")
            if (collection == "GBM") != is_gbm or (collection == "RCC") != is_rcc:
                continue
            cpus[json.loads(Path(path).read_text(encoding="utf-8"))["environment"]["cpu_model"]] += 1
            sections += 1
        rows.append({"row": "ranking (posterior corr., Moran's I, mean intensity, IG)",
                     "collection": collection, "runs": sections, "median_minutes": None,
                     "hardware": "; ".join(f"{k} ({v})" for k, v in cpus.items())})
    output.mkdir(parents=True)
    with open(output / "runtime_hardware.csv", "w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())

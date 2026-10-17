#!/usr/bin/env python3
"""Table of the ranking-stage timings (supervisor chat 2026-10-17 09:48, item 2).

Reads only the per-section summary.json files written by time_ranking_stages.py
(locally, after the download sync) and writes one row per section/run:
uniform_mean, seed 1, median of the repeats, seconds. Descriptive only.

Refuses a table that mixes CPU models (the request is one node type for all).
A section without a complete summary is listed as missing, never filled in.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from time_ranking_stages import STAGES  # noqa: E402

DEFAULT_ROOT = ROOT / "results" / "diagnostics" / "ranking_stage_runtime"
RCC = ("RCC_MH0204_33", "RCC_UH0505_12", "RCC_UH0710_33", "RCC_UH9610_15",
       "RCC_UH9812_03", "RCC_UH9905_18", "RCC_UH9911_05", "RCC_UH9912_01")
CAC = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL")
GBM = ("GBM108_negative", "GBM108_positive", "GBM12_1", "GBM12_2",
       "GBM22_1", "GBM22_2", "GBM39_1", "GBM39_2")
SECTIONS = RCC + CAC + GBM   # slurm_jobs/test_r_sections.sh order


def collection(section):
    if section.startswith("RCC_"):
        return "RCC"
    return "GBM" if section.startswith("GBM") else "CAC"


def reproduction_label(rankings):
    if isinstance(rankings, str):
        return rankings
    return f"identical (full-ranking SHA-256), {len(rankings)} rankings"


def collect(root, expected=SECTIONS):
    rows, cpus = [], set()
    for section in expected:
        path = Path(root) / f"{section}_seed1" / "uniform_mean" / "summary.json"
        row = {"section": section, "collection": collection(section), "arm": "uniform_mean",
               "seed": 1}
        summary = (json.loads(path.read_text(encoding="utf-8")) if path.exists() else None)
        if summary is None or summary.get("status") != "complete":
            row.update({"status": "missing", "posterior_abs_pcc_seconds": None})
            rows.append(row)
            continue
        median = summary["stage_seconds_median"]
        ig = summary["integrated_gradients"]
        environment = summary["environment"]
        cpus.add(environment["cpu_model"])
        row.update({
            "status": "complete",
            "pixels": summary["pixels"], "spectral_bins": summary["spectral_bins"],
            "data_load_seconds": summary["data_load_seconds"],
            "tic_normalisation_seconds": summary["tic_normalisation_seconds"],
            **{f"{stage}_seconds": median[stage] for stage in STAGES},
            "posterior_abs_pcc_incl_gmm_posterior_seconds":
                summary["posterior_abs_pcc_including_gmm_posterior_median"],
            "ig_seconds": ig["seconds"], "ig_label": ig["label"],
            "ig_attribution_status": ig.get("attribution_status"),
            "ranking_reproduction": reproduction_label(summary["reproduction"]["rankings"]),
            "cpu_model": environment["cpu_model"], "node": environment.get("node"),
            "source": path.as_posix(),
        })
        rows.append(row)
    if len(cpus) > 1:
        raise SystemExit(f"Mixed CPU models {sorted(cpus)}: not one node type; no table written")
    return rows, (next(iter(cpus)) if cpus else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=None,
                        help="Default: <root>/table_local/")
    args = parser.parse_args()
    output = args.output or args.root / "table_local"
    rows, cpu = collect(args.root)
    output.mkdir(parents=True, exist_ok=True)
    fields = list(next(r for r in rows if r["status"] == "complete")) if any(
        r["status"] == "complete" for r in rows) else list(rows[0])
    for row in rows:
        fields += [key for key in row if key not in fields]
    with open(output / "ranking_stage_runtime.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    complete = sum(r["status"] == "complete" for r in rows)
    record = {"sections_complete": complete, "sections_expected": len(rows), "cpu_model": cpu,
              "missing": [r["section"] for r in rows if r["status"] != "complete"],
              "note": "uniform_mean, seed 1; median of repeats; descriptive only "
                      "(supervisor chat 2026-10-17 09:48)"}
    (output / "summary.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Item A(b): reproduce a saved IG/L2 list at its own count before re-evaluation.

The frozen GBM attention peak evaluations used pre-tuning counts (supervisor
chat, 2026-10-15 15:35, point 1). Before those attributions are re-evaluated at
the production K_bin, this check rebuilds the IG and first-layer-L2 rankings
from the saved attributions with the fair-scoring code and requires, at the
saved count: the same bins, any order difference only between exactly tied
scores, and the saved mSCF1 to 1e-12 (the Section 2 rule). Exit 4 on failure.
Writes a status JSON; prints a status line only.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from evaluate_fair_scoring_baselines import SCORE_TOLERANCE, read_saved_list
from evaluate_spatial_msipl_attributed_peaks import load_correlations, read_h5_metadata, score_indices
from spatial_msipl.provenance import atomic_write_json, file_record, require_slurm
from spatial_msipl.simple_baselines import (
    balanced_ranking_from_component_scores,
    production_ig_scores,
    production_l2_ranking,
    tie_permuted_positions,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--saved-evaluation-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true")
    args = parser.parse_args()
    require_slurm(args.allow_outside_slurm)

    saved_summary_path = args.saved_evaluation_dir / "summary.json"
    saved_summary = json.loads(saved_summary_path.read_text(encoding="utf-8"))
    count = int(saved_summary["matched_peak_evaluation"]["count"])
    lists = {"integrated_gradients": args.saved_evaluation_dir / f"ig_matched_{count}_bins.csv",
             "first_layer_l2": args.saved_evaluation_dir / f"first_layer_l2_matched_{count}_bins.csv"}
    attributions_path = args.attribution_dir / "attributions.npz"
    attributions = np.load(attributions_path)
    ig_scores = production_ig_scores(attributions)
    ig_ranking, ig_sources = balanced_ranking_from_component_scores(ig_scores, with_sources=True)
    l2_scores = np.asarray(attributions["first_layer_combined_l2"], dtype=np.float64)
    rankings = {"integrated_gradients": ig_ranking, "first_layer_l2": production_l2_ranking(attributions)}
    score_at = {"integrated_gradients": lambda i, b: ig_scores[int(ig_sources[i])][b],
                "first_layer_l2": lambda i, b: l2_scores[b]}

    record = {"status": "failed", "saved_count": count,
              "inputs": {"input": str(args.input), "attributions": file_record(attributions_path),
                         "saved_evaluation_summary": file_record(saved_summary_path),
                         **{f"saved_{k}_list": file_record(p) for k, p in lists.items()}},
              "checks": {}}
    try:
        mz, labels, _, _, pixels_first = read_h5_metadata(args.input)
        correlations = load_correlations(args.input, labels, len(mz), pixels_first, args.chunk_size)
        for name, path in lists.items():
            prefix = rankings[name][:count]
            ties = tie_permuted_positions(prefix, read_saved_list(path), score_at[name])
            rescored = score_indices(prefix, correlations, len(mz))["mSCF1"]
            saved = float(saved_summary["matched_peak_evaluation"]["methods"][name]["mSCF1"])
            difference = rescored - saved
            if abs(difference) > SCORE_TOLERANCE:
                raise ValueError(f"{name}: rescored mSCF1 differs from saved by {difference}")
            record["checks"][name] = {"same_bins": True, "tie_permuted_positions": ties,
                                      "mSCF1_difference": difference}
        record["status"] = "passed"
    except ValueError as error:
        record["error"] = str(error)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(args.output, record)
    print(f"{args.input.stem}: saved-list reproduction {record['status']}", flush=True)
    if record["status"] != "passed":
        sys.exit(4)


if __name__ == "__main__":
    main()

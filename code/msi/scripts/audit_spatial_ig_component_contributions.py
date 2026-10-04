#!/usr/bin/env python3
"""Score frozen IG centre, neighbour, and combined rankings at one peak count.

This is a ranking ablation of a fixed GMM/IG explanation, not a new model or
an independent centre-only training run. Expert masks are used only for scoring.
"""

import argparse
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from evaluate_spatial_msipl_attributed_peaks import (
    load_correlations,
    read_h5_metadata,
    score_indices,
)
from spatial_msipl.peak_selection import balanced_round_robin_rankings


RANKINGS = {
    "combined": "combined_absolute_mean",
    "central": "central_absolute_mean",
    "neighbours": "context_absolute_mean",
}


def load_attribution(path, source_mz, expected_context):
    summary = json.loads((path / "summary.json").read_text(encoding="utf-8"))
    if summary.get("status") != "valid":
        raise ValueError(f"IG attribution is not valid: {path}")
    if summary["input_specification"]["context_mode"] != expected_context:
        raise ValueError(f"Unexpected context mode in {path}")
    with np.load(path / "attributions.npz", allow_pickle=False) as saved:
        if not np.array_equal(saved["mz"], source_mz):
            raise ValueError(f"m/z axis differs from source HDF5: {path}")
        components = sorted({
            int(key.split("_")[1]) for key in saved.files
            if key.startswith("component_")
        })
        if len(components) != int(summary["gmm"]["components"]):
            raise ValueError(f"GMM component count differs from IG arrays: {path}")
        scores = {
            name: {
                component: np.asarray(
                    saved[f"component_{component}_{suffix}"], dtype=np.float64
                ).copy()
                for component in components
            }
            for name, suffix in RANKINGS.items()
        }
    for component in components:
        for name in RANKINGS:
            if scores[name][component].shape != source_mz.shape:
                raise ValueError(f"Wrong score length: {path}, {name}, {component}")
            if not np.all(np.isfinite(scores[name][component])):
                raise ValueError(f"Non-finite scores: {path}, {name}, {component}")
        if not np.allclose(
            scores["combined"][component],
            scores["central"][component] + scores["neighbours"][component],
            rtol=1e-5, atol=1e-8,
        ):
            raise ValueError(f"Combined IG does not equal centre plus neighbours: {path}")
    return summary, scores


def select_bins(scores, count):
    # Match the production selection rule exactly, including tie ordering.
    rankings = {
        component: np.argsort(values)[::-1].copy()
        for component, values in scores.items()
    }
    selected, _ = balanced_round_robin_rankings(rankings, count)
    return selected


def audit(input_path, attribution_dirs, count, output, chunk_size):
    mz, labels, _, _, pixels_first = read_h5_metadata(input_path)
    if count < 1 or count > len(mz):
        raise ValueError("Matched count must be within the m/z axis")
    correlations = load_correlations(
        input_path, labels, len(mz), pixels_first, chunk_size
    )
    records = []
    details = {}
    for arm, path in attribution_dirs.items():
        expected_context = "measured" if arm == "real" else "shuffled"
        summary, scores = load_attribution(path, mz, expected_context)
        selected_by_ranking = {}
        arm_details = {
            "attribution_dir": str(path),
            "model_state_sha256": summary["model_state_sha256"],
            "rankings": {},
        }
        for name, component_scores in scores.items():
            selected = select_bins(component_scores, count)
            result = score_indices(selected, correlations, len(mz))
            selected_by_ranking[name] = selected
            arm_details["rankings"][name] = result
            records.append({
                "dataset": input_path.stem,
                "arm": arm,
                "ranking": name,
                "matched_count": count,
                "mSCF1": result["mSCF1"],
                **{
                    f"F1_{threshold}": result["mixed_f1"][str(threshold)]
                    for threshold in (0.3, 0.4, 0.5, 0.6)
                },
            })
        original = json.loads(
            (path.parent / "peak_evaluation" / "summary.json").read_text(
                encoding="utf-8"
            )
        )
        original_score = original["matched_peak_evaluation"]["methods"][
            "integrated_gradients"
        ]["mSCF1"]
        new_score = arm_details["rankings"]["combined"]["mSCF1"]
        if not np.isclose(new_score, original_score, rtol=0, atol=1e-12):
            raise RuntimeError(
                f"Combined ranking failed to reproduce saved evaluation for {arm}: "
                f"{new_score} versus {original_score}"
            )
        combined = set(selected_by_ranking["combined"].tolist())
        arm_details["selected_bin_overlap_with_combined"] = {
            name: len(combined.intersection(selected.tolist()))
            for name, selected in selected_by_ranking.items()
        }
        arm_details["central_absolute_ig_fraction_by_component"] = {
            str(component): float(
                scores["central"][component].sum()
                / scores["combined"][component].sum()
            )
            for component in scores["combined"]
        }
        details[arm] = arm_details

    output.mkdir(parents=True, exist_ok=True)
    with (output / "scores.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    result = {
        "status": "valid",
        "dataset": input_path.stem,
        "source_h5": str(input_path),
        "matched_count": count,
        "comparison": "same frozen attention VAE, GMM, IG target, and sampling; only the per-bin ranking contribution changes",
        "limitation": "centre/neighbour rankings are components of a jointly trained contextual model, not separately trained models",
        "combined_score_reproduction": "passed for both arms",
        "arms": details,
    }
    (output / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )

    fig, axis = plt.subplots(figsize=(9, 5))
    names = list(RANKINGS)
    x = np.arange(len(names))
    width = 0.35
    colours = {"real": "#457B9D", "shuffled": "#E76F51"}
    for offset, arm in enumerate(("real", "shuffled")):
        values = [
            details[arm]["rankings"][name]["mSCF1"] for name in names
        ]
        axis.bar(x + (offset - 0.5) * width, values, width,
                 color=colours[arm], label=arm)
    axis.set_xticks(x, ["Centre + neighbours", "Centre only", "Neighbours only"])
    axis.set_ylabel("Matched-count mSCF1 (higher is better)")
    axis.set_title(f"{input_path.stem}: which IG contribution ranks useful bins?")
    axis.set_ylim(0, 1)
    axis.legend(title="Context supplied to model")
    fig.tight_layout()
    fig.savefig(output / "ig_component_ablation.png", dpi=220)
    plt.close(fig)
    return result, records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--real-attribution", required=True, type=Path)
    parser.add_argument("--shuffled-attribution", required=True, type=Path)
    parser.add_argument("--matched-count", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-size", default=1024, type=int)
    args = parser.parse_args()
    result, records = audit(
        args.input,
        {"real": args.real_attribution, "shuffled": args.shuffled_attribution},
        args.matched_count, args.output, args.chunk_size,
    )
    print(json.dumps({
        "status": result["status"],
        "dataset": result["dataset"],
        "scores": records,
        "output": str(args.output),
    }, indent=2), flush=True)


if __name__ == "__main__":
    main()

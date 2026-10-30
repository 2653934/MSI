#!/usr/bin/env python3
"""GMM gate v2 for the IG completeness reruns (protocol 18 Section 6.3 amendment,
"Gate correction after 78483 tasks 1/4/8"; supervisor chat 2026-10-30 14:46 and
14:54; decision log D33).

Compares one rerun attribution folder with its saved 64-step folder and writes
gmm_gate_v2.json. The gate passes only if all of these hold:
- the model state is equal (model_state_sha256) and the step count is the task's;
- the refit GMM was aligned to the saved assignment (exactly one permutation,
  posterior within 1e-4; recorded by --align-gmm-labels-to-production) and the
  hard assignment is identical;
- per component: identical attribution pixel indices (saved per-pixel diagnostics),
  identical faithfulness pixel indices (not saved by the IG script, so both runs'
  sets are rebuilt from their saved labels with the IG script's own sampling
  function; the rebuild must reproduce both runs' saved attribution indices), an
  identical IG target per attribution pixel, and the aligned component mean and
  covariance within 1e-6.
The component order sklearn chose (the v1 identity-permutation condition) is
recorded but no longer decides. Read only; never overwrites (exit 3).
Exit 0: passed; 5: failed (stop and post).
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

PARAMETER_TOLERANCE = 1e-6
POSTERIOR_TOLERANCE = 1e-4


def choose_disjoint_samples(labels, n_attribution, n_faithfulness, seed):
    rng = np.random.default_rng(seed)
    selected = {}
    for component in np.unique(labels):
        candidates = np.flatnonzero(labels == component)
        required = n_attribution + n_faithfulness
        if len(candidates) < required:
            raise ValueError(
                f"component {component} has {len(candidates)} pixels; {required} required"
            )
        shuffled = rng.permutation(candidates)
        selected[int(component)] = {
            "attribution": np.sort(shuffled[:n_attribution]),
            "faithfulness": np.sort(shuffled[n_attribution:required]),
        }
    return selected


def load_run(folder):
    folder = Path(folder)
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    ig = summary["integrated_gradients"]
    labels = np.load(folder / "coordinates_and_gmm.npz")["component"]
    attribution, target = {}, {}
    for record in ig["per_pixel_diagnostics"]:
        attribution.setdefault(int(record["component"]), []).append(int(record["pixel_index"]))
        target[int(record["pixel_index"])] = int(record["component"])
    attribution = {component: np.sort(np.asarray(pixels)) for component, pixels in attribution.items()}
    seed = int(ig.get("selection_seed", int(ig.get("sampling_seed", 1)) + 700))
    rebuilt = choose_disjoint_samples(
        labels, int(ig["attribution_pixels_per_component"]),
        int(summary["faithfulness"]["pixels_per_component"]), seed)
    rebuild_reproduces_saved = (sorted(rebuilt) == sorted(attribution) and all(
        np.array_equal(rebuilt[component]["attribution"], attribution[component])
        for component in attribution))
    with np.load(folder / "gmm_parameters.npz") as parameters:
        parameters = {name: parameters[name] for name in parameters.files}
    return {"summary": summary, "labels": labels, "attribution": attribution, "target": target,
            "rebuilt": rebuilt, "rebuild_reproduces_saved": rebuild_reproduces_saved,
            "parameters": parameters, "selection_seed": seed}


def max_abs(first, second):
    first, second = np.asarray(first, dtype=np.float64), np.asarray(second, dtype=np.float64)
    if first.shape != second.shape:
        return float("inf")
    return float(np.max(np.abs(first - second))) if first.size else 0.0


def gate(new_dir, saved_dir, steps):
    new, saved = load_run(new_dir), load_run(saved_dir)
    alignment = new["summary"].get("gmm_label_alignment") or {}
    components = sorted(saved["attribution"])
    per_component = {}
    for component in components:
        per_component[str(component)] = {
            "attribution_pixels_equal": bool(np.array_equal(
                new["attribution"].get(component, np.array([])), saved["attribution"][component])),
            "faithfulness_pixels_equal": bool(
                component in new["rebuilt"] and np.array_equal(
                    new["rebuilt"][component]["faithfulness"],
                    saved["rebuilt"][component]["faithfulness"])),
            "mean_max_abs_diff": max_abs(new["parameters"]["component_means"][component],
                                         saved["parameters"]["component_means"][component]),
            "covariance_max_abs_diff": max_abs(new["parameters"]["covariances"][component],
                                               saved["parameters"]["covariances"][component]),
        }
    posterior_difference = alignment.get("max_posterior_diff")
    record = {
        "gate_version": 2,
        "rule": "protocol 18 Section 6.3, gate correction after 78483 tasks 1/4/8; decision log D33",
        "model_state_equal": new["summary"]["model_state_sha256"] == saved["summary"]["model_state_sha256"],
        "steps_recorded": int(new["summary"]["integrated_gradients"]["steps"]),
        "alignment_applied": bool(alignment.get("enabled")),
        "alignment_max_posterior_diff": posterior_difference,
        "alignment_within_tolerance": (posterior_difference is not None
                                       and float(posterior_difference) <= POSTERIOR_TOLERANCE),
        "identity_permutation_recorded_only": alignment.get("identity"),
        "hard_assignment_equal": bool(np.array_equal(new["labels"], saved["labels"])),
        "component_sets_equal": sorted(new["attribution"]) == components,
        "ig_targets_equal": new["target"] == saved["target"],
        "faithfulness_rebuild_validated": bool(new["rebuild_reproduces_saved"]
                                               and saved["rebuild_reproduces_saved"]),
        "selection_seeds": [new["selection_seed"], saved["selection_seed"]],
        "per_component": per_component,
        "descriptive": {
            "mixture_weights_max_abs_diff": max_abs(new["parameters"]["mixture_weights"],
                                                    saved["parameters"]["mixture_weights"]),
            "scaler_max_abs_diff": max(max_abs(new["parameters"][name], saved["parameters"][name])
                                       for name in ("scaler_mean", "scaler_scale")),
        },
        "new_status": new["summary"]["status"],
        "new_attribution": str(new_dir),
        "saved_attribution": str(saved_dir),
        "saved_summary_sha256": hashlib.sha256(
            (Path(saved_dir) / "summary.json").read_bytes()).hexdigest(),
    }
    record["passed"] = bool(
        record["model_state_equal"] and record["steps_recorded"] == int(steps)
        and record["alignment_applied"] and record["alignment_within_tolerance"]
        and record["hard_assignment_equal"] and record["component_sets_equal"]
        and record["ig_targets_equal"] and record["faithfulness_rebuild_validated"]
        and all(entry["attribution_pixels_equal"] and entry["faithfulness_pixels_equal"]
                and entry["mean_max_abs_diff"] <= PARAMETER_TOLERANCE
                and entry["covariance_max_abs_diff"] <= PARAMETER_TOLERANCE
                for entry in per_component.values()))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new-attribution", required=True, type=Path)
    parser.add_argument("--saved-attribution", required=True, type=Path)
    parser.add_argument("--steps", required=True, type=int)
    parser.add_argument("--output", required=True, type=Path, help="gmm_gate_v2.json path")
    args = parser.parse_args()
    if args.output.exists():
        print(f"Output exists: {args.output} (never overwritten)", file=sys.stderr)
        return 3
    record = gate(args.new_attribution, args.saved_attribution, args.steps)
    args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(json.dumps({key: record[key] for key in (
        "passed", "model_state_equal", "hard_assignment_equal", "ig_targets_equal",
        "identity_permutation_recorded_only", "new_status")}), flush=True)
    return 0 if record["passed"] else 5


if __name__ == "__main__":
    sys.exit(main())

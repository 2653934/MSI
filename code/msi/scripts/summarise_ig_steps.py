#!/usr/bin/env python3
"""Summarise the IG completeness reruns (protocol 18 Section 6.3 amendment
"30 October: IG completeness reruns"; supervisor chat 2026-10-30 12:58 item 1
and the 13:30 ruling).

Local, after the download sync; reads saved files only. Writes:
- residuals.csv: median and 95th-percentile normalised completeness residuals of
  each arm at the saved 64 steps and at every rerun step count;
- gmm_gate.csv: the GMM gate of every rerun (identity permutation, same model
  state, identical hard assignment) and the descriptive latent/parameter differences;
- controls.csv: for each step-count control, fair-scoring bin-level IG mSCF1 at
  K_bin and the Jaccard of the first K_bin IG bins, 128 steps against the saved
  64-step run and against the rerun 64-step run, and the rerun 64 against the saved
  64 (reproduction; the GBM39_2 uniform_mean s1 check of the 13:30 ruling);
- summary.json: all of the above plus the step count that enters the decisions for
  each failed arm (the first passing of 128 and 256; otherwise "not done").
Descriptive only. Controls never enter a decision. Refuses an existing output folder.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
# Must equal IG_STEPS_TASKS in slurm_jobs/ig_steps_sections.sh (checked by a test).
TASKS = (
    ("RCC_UH0505_12", 1, "uniform_mean", 128, "rerun"),
    ("RCC_UH0505_12", 2, "central_only", 128, "rerun"),
    ("RCC_UH9912_01", 3, "uniform_mean", 128, "rerun"),
    ("GBM39_2", 3, "uniform_mean", 128, "rerun"),
    ("RCC_UH0505_12", 1, "central_only", 64, "control"),
    ("RCC_UH9912_01", 1, "uniform_mean", 64, "control"),
    ("GBM39_2", 1, "uniform_mean", 64, "control"),
    ("40TopL", 1, "uniform_mean", 64, "control"),
    ("RCC_UH0505_12", 1, "central_only", 128, "control"),
    ("RCC_UH9912_01", 1, "uniform_mean", 128, "control"),
    ("GBM39_2", 1, "uniform_mean", 128, "control"),
    ("40TopL", 1, "uniform_mean", 128, "control"),
    ("RCC_UH0505_12", 1, "uniform_mean", 256, "rerun"),
    ("RCC_UH0505_12", 2, "central_only", 256, "rerun"),
    ("RCC_UH9912_01", 3, "uniform_mean", 256, "rerun"),
    ("GBM39_2", 3, "uniform_mean", 256, "rerun"),
)
RERUN_STEPS = (128, 256)
REPRODUCTION_MSCF1_TOLERANCE = 0.005   # 13:30 ruling, GBM39_2 uniform_mean s1
FOLDERS = {"rerun": "ig_steps_rerun_20261030", "control": "ig_steps_control_20261030"}


def collection(section):
    if section.startswith("RCC_"):
        return "RCC"
    if section.startswith("GBM"):
        return "GBM"
    if section.endswith("TopL"):
        return "CAC"
    raise ValueError(f"unknown section: {section}")


def result_root(project, section, seed, arm, steps, kind):
    return (project / "results" / "experiments" / FOLDERS[kind]
            / f"{section}_seed{seed}" / arm / f"steps{steps}")


def saved_attribution(project, section, seed, arm):
    experiments = project / "results" / "experiments"
    if seed != 1:
        return experiments / "test_r_training_seeds" / f"{section}_seed{seed}" / arm / "attribution"
    return {
        "RCC": experiments / "rcc_spatial_msipl" / f"{section}_seed1" / arm / "attribution",
        "GBM": experiments / "spatial_msipl_gmm_integrated_gradients" / f"{section}_seed1" / arm,
        "CAC": experiments / "spatial_msipl_cac_gmm_integrated_gradients" / f"{section}_seed1" / arm,
    }[collection(section)]


def saved_fair_bin_level(project, section, seed, arm):
    """The saved seed-1 bin-level fair-scoring folder (controls are all seed 1)."""
    if seed != 1:
        raise ValueError("controls are seed-1 arms")
    fair = project / "results" / "diagnostics" / "fair_scoring_baselines"
    if collection(section) == "RCC":
        return fair / "rcc" / "bin_level_only" / f"{section}_seed1" / arm
    return fair / "bin_level_only" / f"{section}_seed1" / arm


def rerun_fair_bin_level(project, section, seed, arm, steps):
    return (project / "results" / "diagnostics" / "fair_scoring_baselines" / "ig_steps_20261030"
            / "bin_level_only" / f"{section}_seed{seed}" / arm / f"steps{steps}")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def completeness_row(summary):
    completeness = summary["integrated_gradients"]["completeness"]
    return {
        "status": summary["status"],
        "steps": int(summary["integrated_gradients"]["steps"]),
        "median_normalized_residual": completeness["median_normalized_residual"],
        "percentile_95_normalized_residual": completeness["percentile_95_normalized_residual"],
        "passed": bool(completeness["passed"]),
    }


def ig_at_k_bin(fair_dir):
    """IG mSCF1 at K_bin and the first K_bin IG bins from one fair-scoring output."""
    summary = load_json(Path(fair_dir) / "summary.json")
    if summary.get("status") != "complete":
        raise ValueError(f"fair-scoring summary not complete: {fair_dir}")
    k_bin = int(summary["K_bin"])
    bins = np.load(Path(fair_dir) / "rankings_prefix.npz")["integrated_gradients"][:k_bin]
    if len(bins) != k_bin:
        raise ValueError(f"saved IG prefix shorter than K_bin: {fair_dir}")
    return k_bin, float(summary["bin_level"]["integrated_gradients"]["1.0"]["mSCF1"]), bins


def compare(reference, candidate):
    """Delta mSCF1 (candidate - reference), Jaccard and the differing bins' ranks."""
    k_reference, score_reference, bins_reference = reference
    k_candidate, score_candidate, bins_candidate = candidate
    if k_reference != k_candidate:
        raise ValueError("K_bin differs between the compared runs")
    first, second = set(bins_reference.tolist()), set(bins_candidate.tolist())
    rank_reference = {int(b): r for r, b in enumerate(bins_reference.tolist(), start=1)}
    rank_candidate = {int(b): r for r, b in enumerate(bins_candidate.tolist(), start=1)}
    return {
        "K_bin": k_reference,
        "delta_mSCF1": score_candidate - score_reference,
        "jaccard": len(first & second) / len(first | second),
        "bins_only_in_reference_ranks": sorted(rank_reference[b] for b in first - second),
        "bins_only_in_candidate_ranks": sorted(rank_candidate[b] for b in second - first),
    }


def decision_steps(rows):
    """First passing rerun step count of one failed arm, or "not done"."""
    by_steps = {row["steps"]: row for row in rows}
    for steps in RERUN_STEPS:
        row = by_steps.get(steps)
        if row is None:
            return "pending"
        if not row.get("gmm_gate_passed"):
            return f"GMM gate failed at {steps} steps (stop and post)"
        if row["status"] == "valid":
            return steps
    return "not done"


def summarise(project):
    residuals, gates, missing = [], [], []
    arms = {}
    for section, seed, arm, steps, kind in TASKS:
        arms.setdefault((section, seed, arm, kind), [])
    for (section, seed, arm, kind) in arms:
        saved = load_json(saved_attribution(project, section, seed, arm) / "summary.json")
        row = completeness_row(saved)
        if row["steps"] != 64:
            raise ValueError(f"saved run is not 64 steps: {section} {seed} {arm}")
        row.update(section=section, seed=seed, arm=arm, kind=kind, source="saved 64-step run")
        residuals.append(row)
    for section, seed, arm, steps, kind in TASKS:
        root = result_root(project, section, seed, arm, steps, kind)
        if not (root / "gmm_gate.json").exists():
            missing.append(f"{section} s{seed} {arm} {steps} ({kind})")
            continue
        gate = load_json(root / "gmm_gate.json")
        row = completeness_row(load_json(root / "attribution" / "summary.json"))
        if row["steps"] != steps:
            raise ValueError(f"step count mismatch in {root}")
        row.update(section=section, seed=seed, arm=arm, kind=kind, source="rerun",
                   gmm_gate_passed=bool(gate["passed"]))
        residuals.append(row)
        arms[(section, seed, arm, kind)].append(row)
        gates.append({"section": section, "seed": seed, "arm": arm, "steps": steps, "kind": kind,
                      "passed": gate["passed"], "identity_permutation": gate["identity_permutation"],
                      "model_state_equal": gate["model_state_equal"],
                      "hard_assignment_equal": gate["hard_assignment_equal"],
                      "alignment_max_posterior_diff": gate["alignment_max_posterior_diff"],
                      **{f"max_abs_diff_{k}": v for k, v in gate["descriptive"].items()
                         if not isinstance(v, dict)},
                      "max_abs_diff_gmm_parameters": max(
                          gate["descriptive"]["gmm_parameters_max_abs_diff"].values())})
    decisions = {f"{s} s{seed} {arm}": decision_steps(rows)
                 for (s, seed, arm, kind), rows in arms.items() if kind == "rerun"}

    controls = []
    for (section, seed, arm, kind) in arms:
        if kind != "control":
            continue
        record = {"section": section, "seed": seed, "arm": arm}
        try:
            saved64 = ig_at_k_bin(saved_fair_bin_level(project, section, seed, arm))
            rerun64 = ig_at_k_bin(rerun_fair_bin_level(project, section, seed, arm, 64))
            rerun128 = ig_at_k_bin(rerun_fair_bin_level(project, section, seed, arm, 128))
        except FileNotFoundError as error:
            record["status"] = f"missing: {error.filename}"
            controls.append(record)
            continue
        reproduction = compare(saved64, rerun64)
        record.update(
            status="complete",
            mSCF1_saved64=saved64[1], mSCF1_rerun64=rerun64[1], mSCF1_rerun128=rerun128[1],
            rerun128_vs_saved64=compare(saved64, rerun128),
            rerun128_vs_rerun64=compare(rerun64, rerun128),
            rerun64_vs_saved64=reproduction,
            rerun64_reproduces_saved=bool(
                reproduction["jaccard"] == 1.0
                and abs(reproduction["delta_mSCF1"]) <= REPRODUCTION_MSCF1_TOLERANCE),
        )
        controls.append(record)
    return {"residuals": residuals, "gmm_gate": gates, "controls": controls,
            "decision_steps": decisions, "missing_tasks": missing,
            "reproduction_rule": ("rerun 64 reproduces saved 64 if Jaccard = 1 and "
                                  f"|delta mSCF1| <= {REPRODUCTION_MSCF1_TOLERANCE}; otherwise post "
                                  "with the numbers (13:30 ruling); near-tie swaps are judged "
                                  "from the listed ranks")}


def write_csv(path, rows):
    fields = []
    for row in rows:
        fields.extend(key for key in row if key not in fields)
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: (json.dumps(value) if isinstance(value, (dict, list)) else value)
                             for key, value in row.items()})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT,
                        help="code/msi root holding results/ (tests pass a temporary root)")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        print(f"Output exists: {args.output} (move it aside; never overwritten)", file=sys.stderr)
        return 3
    result = summarise(args.project_root)
    args.output.mkdir(parents=True)
    write_csv(args.output / "residuals.csv", result["residuals"])
    write_csv(args.output / "gmm_gate.csv", result["gmm_gate"])
    write_csv(args.output / "controls.csv", result["controls"])
    (args.output / "summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"decision_steps": result["decision_steps"],
                      "missing_tasks": result["missing_tasks"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

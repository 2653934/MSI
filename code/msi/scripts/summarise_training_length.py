#!/usr/bin/env python3
"""Item 3, C3 training length (supervisor chat 2026-10-30 12:58 item 3 and 20:16
request 4). Local only, on pulled results.

Per development section (GBM108_positive, 40TopL) and arm (central_only, uniform_mean),
seed 1:
1. scores at epochs 10, 25, 50 and 100: IG and posterior-|PCC| (balanced) mSCF1 at
   K_bin, bin level, from the unchanged fair evaluator's summaries;
2. the training loss of every epoch (total, reconstruction, KL) from
   training_history.json, so the report can show where the loss levels off;
3. the reproduction check: the epoch-100 rerun must give the production seed-1 IG and
   posterior-|PCC| mSCF1 (1e-12) and the same ranking prefixes. A failure is reported
   as "epoch 100 not reproduced" beside the numbers; nothing is tuned on mSCF1.
An epoch whose IG was not valid is "not done". Refuses an existing output.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SECTIONS = ("GBM108_positive", "40TopL")
ARMS = ("central_only", "uniform_mean")
EPOCHS = (10, 25, 50, 100)
RANKINGS = ("integrated_gradients", "posterior_abs_pcc_balanced")
TOLERANCE = 1e-12
EXPERIMENT = Path("results/experiments/training_length_20261030")
FAIR = Path("results/diagnostics/fair_scoring_baselines/training_length_20261030/bin_level_only")
PRODUCTION = Path("results/diagnostics/fair_scoring_baselines/bin_level_only")


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def bin_scores(summary):
    return {name: float(summary["bin_level"][name]["1.0"]["mSCF1"]) for name in RANKINGS}


def reproduction(root, section, arm, epoch_100):
    """Compare the epoch-100 rerun with the production seed-1 fair-scoring result."""
    production_dir = root / PRODUCTION / f"{section}_seed1" / arm
    production = bin_scores(read_json(production_dir / "summary.json"))
    differences = {name: abs(epoch_100["scores"][name] - production[name]) for name in RANKINGS}
    rerun_prefix = np.load(epoch_100["directory"] / "rankings_prefix.npz")
    production_prefix = np.load(production_dir / "rankings_prefix.npz")
    prefixes_equal = all(name in rerun_prefix.files and
                         np.array_equal(rerun_prefix[name], production_prefix[name])
                         for name in RANKINGS)
    return {"production": production, "abs_difference": differences,
            "ranking_prefixes_identical": bool(prefixes_equal),
            "reproduced": bool(prefixes_equal and max(differences.values()) <= TOLERANCE)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    root, output = args.project_root, args.output
    if output.exists():
        print(f"Output exists: {output} (never overwritten)", file=sys.stderr)
        return 3
    score_rows, loss_rows, checks = [], [], {}
    for section in SECTIONS:
        for arm in ARMS:
            history = read_json(root / EXPERIMENT / f"{section}_seed1" / arm /
                                "training_history.json")
            if [record["epoch"] for record in history] != list(range(1, 101)):
                raise ValueError(f"{section}/{arm}: training history is not epochs 1-100")
            for record in history:
                loss_rows.append({"section": section, "arm": arm, "epoch": record["epoch"],
                                  **{k: record[k] for k in
                                     ("total_loss", "reconstruction_loss", "kl_loss")}})
            per_epoch = {}
            for epoch in EPOCHS:
                directory = root / FAIR / f"{section}_seed1" / arm / f"epoch{epoch}"
                summary_path = directory / "summary.json"
                record = {"section": section, "arm": arm, "epoch": epoch,
                          "total_loss": history[epoch - 1]["total_loss"]}
                if summary_path.exists() and read_json(summary_path).get("status") == "complete":
                    scores = bin_scores(read_json(summary_path))
                    per_epoch[epoch] = {"scores": scores, "directory": directory}
                    record.update({"status": "complete", "K_bin":
                                   int(read_json(summary_path)["K_bin"]),
                                   **{f"{name}_mSCF1": scores[name] for name in RANKINGS}})
                else:
                    record.update({"status": "not done", "K_bin": None,
                                   **{f"{name}_mSCF1": None for name in RANKINGS}})
                score_rows.append(record)
            checks[f"{section}/{arm}"] = (reproduction(root, section, arm, per_epoch[100])
                                          if 100 in per_epoch else
                                          {"reproduced": False, "reason": "epoch 100 not done"})
    output.mkdir(parents=True)
    for name, rows in (("scores_by_epoch.csv", score_rows), ("training_loss.csv", loss_rows)):
        with open(output / name, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    summary = {
        "status": "complete",
        "item": "C3 training length (supervisor chat 2026-10-30 12:58 item 3, 20:16 request 4)",
        "scope": "development sections only; descriptive; no epoch is chosen on mSCF1 (D20g)",
        "epoch_100_reproduction": checks,
        "all_epoch_100_reproduced": all(c["reproduced"] for c in checks.values()),
        "scores_by_epoch": score_rows,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n",
                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())

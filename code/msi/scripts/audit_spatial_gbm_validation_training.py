#!/usr/bin/env python3
"""Audit frozen GBM validation training without loading large checkpoints."""

import argparse
import json
from pathlib import Path


DATASETS = (
    "GBM108_negative",
    "GBM12_1",
    "GBM12_2",
    "GBM22_1",
    "GBM22_2",
    "GBM39_1",
    "GBM39_2",
)
VARIANTS = ("uniform_mean", "central_only")


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--checkpoint-root", required=True, type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def locations(project_root, checkpoint_root, dataset, variant):
    if variant == "uniform_mean":
        result_group = "spatial_msipl_neighbourhood"
        checkpoint_group = "production"
    else:
        result_group = "spatial_msipl_reconstruction"
        checkpoint_group = "reconstruction"
    result = (
        project_root
        / "results"
        / "experiments"
        / result_group
        / f"{dataset}_seed1"
        / variant
    )
    checkpoint = (
        checkpoint_root
        / checkpoint_group
        / f"{dataset}_seed1"
        / variant
    )
    return result, checkpoint


def read_json(path):
    if not path.is_file():
        return None, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as error:
        return None, str(error)


def inspect_run(project_root, checkpoint_root, dataset, variant):
    result_dir, checkpoint_dir = locations(
        project_root, checkpoint_root, dataset, variant
    )
    progress, progress_error = read_json(result_dir / "progress.json")
    summary, summary_error = read_json(result_dir / "summary.json")
    completed_epochs = int(progress.get("completed_epochs", 0)) if progress else 0
    target_epochs = int(progress.get("target_epochs", 100)) if progress else 100
    final_checkpoint = checkpoint_dir / "checkpoint.pt"
    latest_checkpoint = checkpoint_dir / "checkpoint_latest.pt"
    final_exists = final_checkpoint.is_file()
    latest_exists = latest_checkpoint.is_file()
    summary_complete = bool(summary and summary.get("status") == "complete")

    problems = []
    if progress_error:
        problems.append(f"invalid progress.json: {progress_error}")
    if summary_error:
        problems.append(f"invalid summary.json: {summary_error}")
    if completed_epochs > target_epochs:
        problems.append("completed epochs exceed target")
    if final_exists and not summary_complete:
        problems.append("final checkpoint exists but complete summary is missing")
    if summary_complete and not final_exists:
        problems.append("complete summary exists but final checkpoint is missing")
    if summary_complete and completed_epochs != 100:
        problems.append("complete summary does not agree with 100 progress epochs")

    complete = (
        completed_epochs == 100
        and target_epochs == 100
        and final_exists
        and summary_complete
        and not problems
    )
    if complete:
        status = "COMPLETE"
    elif problems:
        status = "INCONSISTENT"
    elif completed_epochs > 0 or latest_exists:
        status = "IN_PROGRESS"
    else:
        status = "NOT_STARTED"

    return {
        "dataset": dataset,
        "variant": variant,
        "status": status,
        "completed_epochs": completed_epochs,
        "target_epochs": target_epochs,
        "latest_checkpoint": latest_exists,
        "final_checkpoint": final_exists,
        "summary_complete": summary_complete,
        "problems": problems,
        "result_directory": str(result_dir),
        "checkpoint_directory": str(checkpoint_dir),
        "resubmit_command": (
            "sbatch slurm_jobs/run_spatial_msipl_gbm_validation_training.sh "
            f"{dataset} {variant}"
        ),
    }


def main():
    args = parse_arguments()
    records = [
        inspect_run(
            args.project_root,
            args.checkpoint_root,
            dataset,
            variant,
        )
        for dataset in DATASETS
        for variant in VARIANTS
    ]
    complete_count = sum(record["status"] == "COMPLETE" for record in records)
    inconsistent_count = sum(
        record["status"] == "INCONSISTENT" for record in records
    )

    print(
        f"{'DATASET':<18} {'VARIANT':<14} {'EPOCHS':<9} "
        f"{'LATEST':<8} {'FINAL':<7} {'SUMMARY':<9} STATUS"
    )
    for record in records:
        epochs = f"{record['completed_epochs']}/{record['target_epochs']}"
        print(
            f"{record['dataset']:<18} {record['variant']:<14} {epochs:<9} "
            f"{str(record['latest_checkpoint']):<8} "
            f"{str(record['final_checkpoint']):<7} "
            f"{str(record['summary_complete']):<9} {record['status']}"
        )
        for problem in record["problems"]:
            print(f"  problem: {problem}")

    incomplete = [record for record in records if record["status"] != "COMPLETE"]
    print()
    print(f"Complete configurations: {complete_count}/{len(records)}")
    if incomplete:
        print("Incomplete configurations and safe restart commands:")
        for record in incomplete:
            print(f"  {record['resubmit_command']}")
    else:
        print("All frozen GBM validation training configurations are complete.")

    report = {
        "status": "complete" if not incomplete else "incomplete",
        "complete_configurations": complete_count,
        "total_configurations": len(records),
        "inconsistent_configurations": inconsistent_count,
        "records": records,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if inconsistent_count:
        raise SystemExit(2)
    if args.require_complete and incomplete:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

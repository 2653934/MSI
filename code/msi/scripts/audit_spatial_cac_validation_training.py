#!/usr/bin/env python3
"""Audit frozen CAC validation training without loading checkpoints."""

import argparse
import json
from pathlib import Path


DATASETS = (
    "40TopL",
    "160TopL",
    "200TopL",
    "240TopL",
    "280TopL",
    "360TopL",
    "400TopL",
    "520TopL",
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
        result_group = "spatial_msipl_cac_neighbourhood"
        checkpoint_group = "production"
    else:
        result_group = "spatial_msipl_cac_reconstruction"
        checkpoint_group = "reconstruction"
    result = (
        project_root / "results" / "experiments" / result_group
        / f"{dataset}_seed1" / variant
    )
    checkpoint = (
        checkpoint_root / checkpoint_group / f"{dataset}_seed1" / variant
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
    completed = int(progress.get("completed_epochs", 0)) if progress else 0
    target = int(progress.get("target_epochs", 100)) if progress else 100
    final_exists = (checkpoint_dir / "checkpoint.pt").is_file()
    latest_exists = (checkpoint_dir / "checkpoint_latest.pt").is_file()
    summary_complete = bool(summary and summary.get("status") == "complete")

    problems = []
    if progress_error:
        problems.append(f"invalid progress.json: {progress_error}")
    if summary_error:
        problems.append(f"invalid summary.json: {summary_error}")
    if completed > target:
        problems.append("completed epochs exceed target")
    if final_exists != summary_complete:
        problems.append("final checkpoint and complete summary disagree")
    if summary_complete and completed != 100:
        problems.append("complete summary does not agree with 100 epochs")

    complete = (
        completed == target == 100
        and final_exists
        and summary_complete
        and not problems
    )
    if complete:
        status = "COMPLETE"
    elif problems:
        status = "INCONSISTENT"
    elif completed > 0 or latest_exists:
        status = "IN_PROGRESS"
    else:
        status = "NOT_STARTED"
    return {
        "dataset": dataset,
        "variant": variant,
        "status": status,
        "completed_epochs": completed,
        "target_epochs": target,
        "latest_checkpoint": latest_exists,
        "final_checkpoint": final_exists,
        "summary_complete": summary_complete,
        "problems": problems,
        "result_directory": str(result_dir),
        "checkpoint_directory": str(checkpoint_dir),
        "resubmit_command": (
            "sbatch slurm_jobs/run_spatial_msipl_cac_validation_training.sh "
            f"{dataset} {variant}"
        ),
    }


def main():
    args = parse_arguments()
    records = [
        inspect_run(args.project_root, args.checkpoint_root, dataset, variant)
        for dataset in DATASETS
        for variant in VARIANTS
    ]
    complete_count = sum(item["status"] == "COMPLETE" for item in records)
    inconsistent_count = sum(
        item["status"] == "INCONSISTENT" for item in records
    )
    print(
        f"{'DATASET':<12} {'VARIANT':<14} {'EPOCHS':<9} "
        f"{'LATEST':<8} {'FINAL':<7} {'SUMMARY':<9} STATUS"
    )
    for item in records:
        epochs = f"{item['completed_epochs']}/{item['target_epochs']}"
        print(
            f"{item['dataset']:<12} {item['variant']:<14} {epochs:<9} "
            f"{str(item['latest_checkpoint']):<8} "
            f"{str(item['final_checkpoint']):<7} "
            f"{str(item['summary_complete']):<9} {item['status']}"
        )
        for problem in item["problems"]:
            print(f"  problem: {problem}")

    incomplete = [item for item in records if item["status"] != "COMPLETE"]
    print(f"\nComplete configurations: {complete_count}/{len(records)}")
    if incomplete:
        print("Incomplete configurations and safe restart commands:")
        for item in incomplete:
            print(f"  {item['resubmit_command']}")
    else:
        print("All frozen CAC validation training configurations are complete.")

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

#!/usr/bin/env python3
"""Item C2: evaluate saved S3PL epoch checkpoints after training has finished.

Evaluation runs only after training because S3PL's test() draws from the
global torch RNG (SubsetRandomSampler); evaluating mid-training would change
the later epochs. For each epoch E this writes a configuration named
<training_name>_epochE (pointing at the <training_name>_epochE.pt weights the
training run saved) and calls the released test() at the training-default
peak count and, when given, at the matched count, exactly as the existing
10-epoch and matched evaluations did. Nothing existing is overwritten.
Status lines only; scores go to the S3PL result folders.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log-json", required=True, type=Path,
                        help="the finished training run's S3PL log configuration")
    parser.add_argument("--epochs", required=True, type=int, nargs="+")
    parser.add_argument("--matched-count", type=int)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(project_root / "baselines" / "s3pl"))
    from test import test
    from utils.helpers import artifact_directories

    base = json.loads(args.log_json.read_text(encoding="utf-8"))
    name = base["training_name"]
    saved = base.get("epoch_checkpoints") or {}
    directories = artifact_directories(base, str(project_root / "baselines" / "s3pl"))
    for epoch in sorted(set(args.epochs)):
        if str(epoch) not in saved:
            raise SystemExit(f"no saved checkpoint for epoch {epoch} in {args.log_json}")
        epoch_name = f"{name}_epoch{epoch}"
        weights = directories["weights"] / f"{epoch_name}.pt"
        if not weights.is_file():
            raise SystemExit(f"missing checkpoint {weights}")
        config_path = directories["logs"] / f"{epoch_name}.json"
        runs = [(None, "")]
        if args.matched_count is not None:
            runs.append((args.matched_count, f"_matched_{args.matched_count}peaks"))
        pending = [(count, suffix) for count, suffix in runs
                   if not (directories["results"] / f"{epoch_name}{suffix}" / "metrics.json").is_file()]
        if not pending:
            print(f"epoch {epoch}: already evaluated", flush=True)
            continue
        config = {key: value for key, value in base.items()
                  if key not in ("train_history", "epoch_details", "epoch_checkpoints")}
        config.update({"training_name": epoch_name, "n_epochs": epoch,
                       "checkpoint_of": name, "checkpoint_epoch": epoch,
                       "train_history": base["train_history"][:epoch]})
        if not config_path.is_file():
            config_path.write_text(json.dumps(config, indent=4), encoding="utf-8")
        for count, suffix in pending:
            test(config, test_indices=None, number_peaks_override=count, result_suffix=suffix)
            print(f"epoch {epoch}{suffix or ' (default count)'}: evaluated", flush=True)


if __name__ == "__main__":
    main()

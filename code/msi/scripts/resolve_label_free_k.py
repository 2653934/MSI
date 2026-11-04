#!/usr/bin/env python3
"""Label-free K (protocol 18 Section 6.10; D56): read the GMM K from a BIC selection.

The K is never typed by hand. It is the ``selected_k`` of an unchanged
``select_gmm_k_bic.py`` record, or, when BIC selects K = 1, the recorded
``best_k_at_least_2`` (flagged). The record must be complete and must have been made
on the same latent as the production attribution folder the IG run starts from
(SHA-256 of ``latent_mean.npy``); otherwise this script stops (exit 1).

Writes ``label_free_k.json`` (refuses to overwrite, exit 3) and prints only the K.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

BOUNDARY_K = 6  # largest candidate of the predeclared range K in {1, ..., 6}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve(selection, production_latent_sha256):
    """The label-free K and its record, from a parsed bic_selection.json."""
    if selection.get("status") != "complete":
        raise ValueError(f"BIC selection is not complete: {selection.get('status')}")
    recorded = selection["provenance"]["source_artifacts"]["latent_mean.npy"]["sha256"]
    if recorded != production_latent_sha256:
        raise ValueError("BIC selection was made on a different latent "
                         f"({recorded} != {production_latent_sha256})")
    selected = int(selection["selected_k"])
    if selected == 1:
        best = selection.get("best_k_at_least_2")
        if best is None:
            raise ValueError("BIC selected K = 1 and recorded no best K >= 2")
        k, flag = int(best), "K = 1 under BIC; best K >= 2 used"
    else:
        k, flag = selected, None
    candidates = selection["provenance"]["parameters"]["candidates"]
    return {
        "label_free_k": k,
        "bic_selected_k": selected,
        "flag": flag,
        "at_boundary_of_tested_range": selected == max(candidates),
        "candidates": candidates,
        "production_k": int(selection["production_k"]),
        "latent_sha256": recorded,
    }


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bic-selection", required=True, type=Path)
    parser.add_argument("--production-attribution", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path,
                        help="label_free_k.json to write (never overwritten)")
    return parser.parse_args()


def main():
    args = parse_arguments()
    if args.output.exists():
        print(f"Output already exists: {args.output}", file=sys.stderr)
        raise SystemExit(3)
    selection = json.loads(args.bic_selection.read_text(encoding="utf-8"))
    try:
        record = resolve(selection, sha256(args.production_attribution / "latent_mean.npy"))
    except (KeyError, ValueError) as error:
        print(f"Label-free K not resolved: {error}", file=sys.stderr)
        raise SystemExit(1)
    record.update({"bic_selection": str(args.bic_selection),
                   "production_attribution": str(args.production_attribution)})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(record["label_free_k"])


if __name__ == "__main__":
    main()

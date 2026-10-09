#!/usr/bin/env python3
"""Gate (d) pixel-count decision table (protocol 18 Section 6).

Reads <root>/<section>_seed1/<arm>/evaluation/summary.json for the two
development sections and both arms, and applies the predeclared rule: a
pixel count n triggers the 16-section rerun for an arm only if mSCF1 at K_bin
rises by >= +0.02 over the saved production n=12 on both sections. It never
chooses a setting from the outcomes; it only reports them. An arm whose n=12
reproduction failed gets no verdict.
"""

import argparse
import json
from pathlib import Path

from spatial_msipl.gate_d_helpers import (
    PIXEL_COUNT_ARMS,
    PIXEL_COUNT_SECTIONS,
    pixel_count_decision,
)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main():
    args = parse_arguments()
    changes, distinct, status, campaign = {}, {}, {}, set()
    for arm in PIXEL_COUNT_ARMS:
        for section in PIXEL_COUNT_SECTIONS:
            path = args.root / f"{section}_seed1" / arm / "evaluation" / "summary.json"
            if not path.exists():
                status.setdefault(arm, {})[section] = "missing"
                continue
            summary = json.loads(path.read_text(encoding="utf-8"))
            status.setdefault(arm, {})[section] = summary["status"]
            prov = summary["provenance"]
            campaign.add(json.dumps({k: prov[k] for k in
                                     ("evaluation_version", "protocol", "parameters", "code")},
                                    sort_keys=True))
            if summary["status"] != "complete":
                continue
            changes.setdefault(arm, {})[section] = {
                int(n): v for n, v in summary["change_vs_saved_n12_at_K_bin"].items()}
            distinct.setdefault(arm, {})[section] = {
                int(n): v for n, v in summary["distinct_from_next_smaller"].items()}
    if len(campaign) > 1:
        raise SystemExit("evaluations come from different code or parameters; "
                         "refusing to mix them in one decision table")

    decisions = pixel_count_decision(changes, distinct)
    decisions["_evaluation_status"] = status
    decisions["_campaign_provenance"] = json.loads(next(iter(campaign))) if campaign else None
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decisions.json").write_text(json.dumps(decisions, indent=2) + "\n",
                                                encoding="utf-8")
    for arm in PIXEL_COUNT_ARMS:
        for n, record in decisions[arm].items():
            print(f"{arm} n={n}: {record['verdict']}")


if __name__ == "__main__":
    main()

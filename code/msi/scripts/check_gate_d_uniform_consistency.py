#!/usr/bin/env python3
"""Gate (d) consistency check after GMM label alignment (protocol 18 Section 6).

For 40TopL uniform_mean the alignment must be the identity in every rerun
(n = 12, 48, 192), and the rerun evaluation must match the superseded,
pre-alignment evaluation to 1e-12: mSCF1 at every n and budget multiplier,
and the change at K_bin. Reads JSON only. Exit 0 = pass, 1 = fail; a report is
written either way. A failure is reported, never explained away.
"""

import argparse
import json
import sys
from pathlib import Path

TOLERANCE = 1e-12
ROOT = Path("results/diagnostics/gate_d_pixel_counts")
DEFAULT_NEW = ROOT / "40TopL_seed1/uniform_mean/evaluation/summary.json"
DEFAULT_OLD = ROOT / "superseded_label_order/40TopL_seed1/uniform_mean/evaluation/summary.json"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--new", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--superseded", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--report", type=Path,
                        default=ROOT / "40TopL_seed1/uniform_mean/consistency_vs_superseded.json")
    return parser.parse_args()


def compare(new, old):
    problems = []
    for n, record in sorted(new["gmm_label_alignment"].items()):
        if not record.get("identity"):
            problems.append(f"n={n}: alignment is not the identity ({record.get('permutation')})")
    differences = {}
    for n in sorted(old["mSCF1"]):
        for m in sorted(old["mSCF1"][n]):
            a, b = new["mSCF1"].get(n, {}).get(m), old["mSCF1"][n][m]
            differences[f"mSCF1 n={n} m={m}"] = None if a is None else abs(a - b)
        a, b = new["change_vs_saved_n12_at_K_bin"].get(n), old["change_vs_saved_n12_at_K_bin"][n]
        differences[f"change n={n}"] = None if a is None else abs(a - b)
    for key, value in differences.items():
        if value is None:
            problems.append(f"{key}: missing from the rerun evaluation")
        elif value > TOLERANCE:
            problems.append(f"{key}: differs by {value:.3e} (> {TOLERANCE})")
    if set(new["mSCF1"]) != set(old["mSCF1"]):
        problems.append("the two evaluations cover different pixel counts")
    return differences, problems


def main():
    args = parse_arguments()
    new = json.loads(args.new.read_text(encoding="utf-8"))
    old = json.loads(args.superseded.read_text(encoding="utf-8"))
    problems = []
    for name, summary in (("rerun", new), ("superseded", old)):
        if summary.get("status") != "complete":
            problems.append(f"{name} evaluation status is {summary.get('status')!r}")
    differences, found = compare(new, old) if not problems else ({}, [])
    problems += found
    report = {"passed": not problems, "tolerance": TOLERANCE,
              "rerun": str(args.new), "superseded": str(args.superseded),
              "max_difference": max((v for v in differences.values() if v is not None),
                                    default=None),
              "differences": differences, "problems": problems}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("PASS" if not problems else "FAIL")
    for problem in problems:
        print(" -", problem)
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()

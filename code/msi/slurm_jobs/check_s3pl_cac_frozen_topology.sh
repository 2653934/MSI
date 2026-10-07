#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import json
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_cac_frozen_topology.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
root = Path("results/diagnostics/s3pl_cac_frozen_topology")
sections = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL")
complete = 0
details = []
drift_sections = []
print(f'{"SECTION":<10} {"REAL":>7} {"ROTATED":>8} {"RING":>8} STATUS')
for section in sections:
    path = root / f"{section}.json"
    if not path.is_file():
        print(f"{section:<10} {'-':>7} {'-':>8} {'-':>8} NO RESULT")
        details.append(f"{section}: missing report: {path}")
        continue
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        assert result["status"] in ("valid", "valid_pair_with_prior_drift")
        real = result["real_mscf1"]
        rotated = result["comparisons"]["rotate_90"]["intervention_mscf1"]
        ring = result["comparisons"]["permute_within_rings"]["intervention_mscf1"]
        status = "COMPLETE*" if result["status"] == "valid_pair_with_prior_drift" else "COMPLETE"
        if status == "COMPLETE*":
            drift_sections.append(section)
        print(f"{section:<10} {real:>7.3f} {rotated:>8.3f} {ring:>8.3f} {status}")
        complete += 1
    except (OSError, KeyError, ValueError, TypeError, AssertionError) as exc:
        print(f"{section:<10} {'-':>7} {'-':>8} {'-':>8} INVALID")
        details.append(f"{section}: {type(exc).__name__}: {exc}")
print(f"Verified topology reports: {complete}/8")
if drift_sections:
    print("* Fresh real result differs from the historical matched-count result: " + ", ".join(drift_sections))
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
PY

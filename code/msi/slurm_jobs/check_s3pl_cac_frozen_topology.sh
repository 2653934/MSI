#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - <<'PY'
import json
from pathlib import Path

root = Path("results/diagnostics/s3pl_cac_frozen_topology")
sections = ("40TopL", "160TopL", "200TopL", "240TopL", "280TopL", "360TopL", "400TopL", "520TopL")
complete = 0
print(f'{"SECTION":<10} {"REAL":>7} {"ROTATED":>8} {"RING":>8} STATUS')
for section in sections:
    path = root / f"{section}.json"
    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        assert result["status"] in ("valid", "valid_pair_with_prior_drift")
        real = result["real_mscf1"]
        rotated = result["comparisons"]["rotate_90"]["intervention_mscf1"]
        ring = result["comparisons"]["permute_within_rings"]["intervention_mscf1"]
        print(f"{section:<10} {real:>7.3f} {rotated:>8.3f} {ring:>8.3f} {result['status']}")
        complete += 1
    except (OSError, KeyError, ValueError, TypeError, AssertionError) as exc:
        print(f"{section:<10} {'-':>7} {'-':>8} {'-':>8} MISSING ({exc})")
print(f"Verified topology reports: {complete}/8")
PY

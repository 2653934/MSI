#!/bin/bash
set -euo pipefail

cd "$HOME/msi"
python - "$@" <<'PY'
import json
import sys
from pathlib import Path

if sys.argv[1:] not in ([], ["--verbose"]):
    raise SystemExit("Usage: check_s3pl_cac_trained_centre_control.sh [--verbose]")
verbose = "--verbose" in sys.argv[1:]
root = Path.cwd()
sections = (
    ("40TopL", 315), ("160TopL", 210), ("200TopL", 221),
    ("240TopL", 255), ("280TopL", 245), ("360TopL", 247),
    ("400TopL", 133), ("520TopL", 232),
)
complete = 0
details = []
print(f'{"SECTION":<10} {"COUNT":>5} {"REAL":>8} {"CENTRE":>8} {"DELTA":>8} STATUS')
for section, count in sections:
    base = f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9"
    control = base + "_train_tile_centre"
    source_path = root / "results/baselines/s3pl" / f"{base}_matched_{count}peaks/metrics.json"
    control_path = root / "results/baselines/s3pl" / control / "metrics.json"
    checkpoint = root / "checkpoints/baselines/s3pl" / f"{control}.pt"
    config_path = root / "logs/s3pl" / f"{control}.json"
    if not control_path.is_file():
        print(f"{section:<10} {count:>5} {'-':>8} {'-':>8} {'-':>8} NO RESULT")
        details.append(f"{section}: missing control metrics: {control_path}")
        continue
    try:
        source = json.loads(source_path.read_text())
        result = json.loads(control_path.read_text())
        config = json.loads(config_path.read_text())
        assert checkpoint.stat().st_size > 0
        assert source["number_picked_peaks"] == count
        assert result["number_picked_peaks"] == count
        assert config["input_context_mode"] == "tile_centre"
        assert result["training_input_context_mode"] == "tile_centre"
        assert result["effective_input_context_mode"] == "tile_centre"
        assert result["source_training_name"] == control
        real = float(source["mSCF1"])
        centre = float(result["mSCF1"])
        assert 0 <= real <= 1 and 0 <= centre <= 1
        print(f"{section:<10} {count:>5} {real:>8.3f} {centre:>8.3f} {real-centre:>+8.3f} COMPLETE")
        complete += 1
    except FileNotFoundError as exc:
        print(f"{section:<10} {count:>5} {'-':>8} {'-':>8} {'-':>8} INCOMPLETE")
        details.append(f"{section}: {type(exc).__name__}: {exc}")
    except (OSError, KeyError, ValueError, AssertionError) as exc:
        print(f"{section:<10} {count:>5} {'-':>8} {'-':>8} {'-':>8} INVALID")
        details.append(f"{section}: {type(exc).__name__}: {exc}")
print(f"Verified controls: {complete}/8")
if verbose and details:
    print("\nDetails:")
    print("\n".join(details))
PY

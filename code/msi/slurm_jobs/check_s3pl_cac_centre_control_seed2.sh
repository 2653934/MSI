#!/bin/bash
# Status-only audit of the S3PL CAC retrained-centre control, seed 2. It checks
# that every artifact exists and is labelled correctly, and prints no scores:
# mSCF1 is read from the synced metrics.json files locally, after Zayd's sync.
#   bash slurm_jobs/check_s3pl_cac_centre_control_seed2.sh [--verbose]
# Exit 0 only when all 16 runs verify; exit 1 if any is MISSING or INVALID.
set -euo pipefail
cd "$HOME/msi"
"$HOME/miniconda3/envs/s3pl_env/bin/python" - "$@" <<'PY'
import json
import sys
from pathlib import Path

verbose = "--verbose" in sys.argv[1:]
root = Path("reproducibility/s3pl_cac_centre_control/seed2_init2_order1")
sections = (("40TopL", 315), ("160TopL", 210), ("200TopL", 221), ("240TopL", 255),
            ("280TopL", 245), ("360TopL", 247), ("400TopL", 133), ("520TopL", 232))
complete, details = 0, []
print(f'{"SECTION":<10} {"ARM":<12} STATUS')
for arm, mode, suffix in (("real", "none", ""), ("tile_centre", "tile_centre", "_train_tile_centre")):
    for section, count in sections:
        name = f"{section}_Attention3DConvAutoencoder_10epochs_256_spectral_patch_size_9{suffix}"
        try:
            result = json.loads((root / "results/baselines/s3pl" / name / "metrics.json").read_text())
            config = json.loads((root / "logs/s3pl" / f"{name}.json").read_text())
            assert (root / "checkpoints/baselines/s3pl" / f"{name}.pt").stat().st_size > 0
            assert config["initialization_seed"] == 2 and config["sample_order_seed"] == 1
            assert config["random_seed"] == 1 and config["n_epochs"] == 10
            assert config["spectral_patch_size"] == 9 and config["number_peaks"] == count
            assert config.get("input_context_mode", "none") == mode
            assert result["number_picked_peaks"] == count
            assert result["training_input_context_mode"] == mode
            assert result["source_training_name"] == name
            assert 0 <= float(result["mSCF1"]) <= 1
            status = "COMPLETE"
            complete += 1
        except FileNotFoundError as exc:
            status = "MISSING"
            details.append(f"{section}/{arm}: {exc}")
        except (OSError, KeyError, ValueError, AssertionError) as exc:
            status = "INVALID"
            details.append(f"{section}/{arm}: {type(exc).__name__}: {exc}")
        print(f"{section:<10} {arm:<12} {status}")
expected = 2 * len(sections)
print(f"Verified seed-2 runs: {complete}/{expected}")
if verbose and details:
    print("\n".join(details))
if complete != expected:
    print(f"INCOMPLETE: {expected - complete} run(s) missing or invalid"
          + ("" if verbose else "; rerun with --verbose for details"), file=sys.stderr)
    sys.exit(1)
PY

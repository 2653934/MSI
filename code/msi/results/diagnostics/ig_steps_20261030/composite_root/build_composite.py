"""Composite fair-scoring root for the downstream regeneration (P18 Section 6.3
amendment "30 October: IG completeness reruns"; decision log D32).

Copies (never moves) every arm-level summary.json of the saved fair-scoring trees
into a new mini project root, then fills the four slots that were "not done"
with the rerun summaries at their decision step counts. Each slot must be empty
in the source tree; otherwise it stops. Writes manifest.csv (destination, source,
SHA-256, role) and refuses an existing composite.
"""
import csv
import hashlib
import shutil
import sys
from pathlib import Path

PROJECT = Path(sys.argv[1])
COMPOSITE = Path(sys.argv[2])
FAIR = PROJECT / "results" / "diagnostics" / "fair_scoring_baselines"
TARGET = COMPOSITE / "results" / "diagnostics" / "fair_scoring_baselines"
RERUN = FAIR / "ig_steps_20261030"
TREES = ("rcc/bin_level_only", "test_r/bin_level_only", "test_r/with_approved_partitions",
         "bin_level_only", "with_approved_partitions")
# (composite tree, section_seed, arm, rerun scopes, decision steps) from summary_post_fair_scoring.
SLOTS = (
    ("rcc/bin_level_only", "RCC_UH0505_12_seed1", "uniform_mean", ("bin_level_only",), 128),
    ("test_r/bin_level_only", "RCC_UH0505_12_seed2", "central_only", ("bin_level_only",), 256),
    ("test_r/bin_level_only", "RCC_UH9912_01_seed3", "uniform_mean", ("bin_level_only",), 128),
    ("test_r/bin_level_only", "GBM39_2_seed3", "uniform_mean", ("bin_level_only",), 128),
    ("test_r/with_approved_partitions", "GBM39_2_seed3", "uniform_mean",
     ("with_approved_partitions",), 128),
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if COMPOSITE.exists():
    sys.exit(f"composite exists: {COMPOSITE} (never overwritten)")
rows = []
for tree in TREES:
    for source in sorted((FAIR / tree).glob("*_seed*/*/summary.json")):
        destination = TARGET / tree / source.relative_to(FAIR / tree)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        rows.append((destination, source, "saved (unchanged)"))
for tree, section_seed, arm, scopes, steps in SLOTS:
    slot = FAIR / tree / section_seed / arm / "summary.json"
    if slot.exists():
        sys.exit(f"slot not empty in the saved tree: {slot}")
    (scope,) = scopes
    source = RERUN / scope / section_seed / arm / f"steps{steps}" / "summary.json"
    if not source.is_file():
        sys.exit(f"rerun summary missing: {source}")
    destination = TARGET / tree / section_seed / arm / "summary.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    rows.append((destination, source, f"IG rerun at {steps} steps (fills a 'not done' slot)"))
with (COMPOSITE / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
    writer = csv.writer(handle)
    writer.writerow(("destination", "source", "sha256", "role"))
    for destination, source, role in rows:
        digest = sha256(destination)
        if digest != sha256(source):
            sys.exit(f"copy differs from source: {destination}")
        writer.writerow((destination.relative_to(COMPOSITE).as_posix(),
                         source.relative_to(PROJECT).as_posix(), digest, role))
shutil.copy2(__file__, COMPOSITE / "build_composite.py")
print({"files": len(rows), "reruns": sum(1 for r in rows if r[2] != "saved (unchanged)")})

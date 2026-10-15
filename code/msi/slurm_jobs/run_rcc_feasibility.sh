#!/bin/bash
# Item D: RCC feasibility go/no-go (supervisor chat 2026-10-15 13:00 and 15:35).
# Go requires all four: (1) Cardinal in a separate env (rcc_env; s3pl_env
# untouched), (2) rcc.rda loads, (3) pixel-level class labels on >= 4 sections,
# (4) the exported HDF5s pass the existing data-contract audit (collection rcc).
# CPU only; no model, clustering or peak scoring. Writes
# results/validation/rcc_feasibility/go_no_go.json. Status lines only.
#SBATCH --job-name=rcc-feasibility
#SBATCH --partition=batch
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
# Memory: 8G, no measured peak yet. rcc.rda is 24.8 MB compressed; the loaded
# object plus one run's dense matrix and its transpose fit well within 8G.
# An out-of-memory stop is reported as a failed run, not silently resubmitted.
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --output=logs/rcc-feasibility-%j.out
#SBATCH --error=logs/rcc-feasibility-%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Submit with sbatch}"
PROJECT_ROOT="$HOME/msi"
ARCHIVE="/datasets/zsuliman/msi_data/zips/CardinalWorkflows_1.44.0.tar.gz"
EXPECTED_SHA256="301a38159adc03243459095b5d7836f5900687e48e332b5e704b98e28a18c485"
EXPORT_DIR="/datasets/zsuliman/msi_data/rcc_cardinal"
REPORT_DIR="$PROJECT_ROOT/results/validation/rcc_feasibility"
RSCRIPT="$HOME/miniconda3/envs/rcc_env/bin/Rscript"
PYTHON="$HOME/miniconda3/envs/s3pl_env/bin/python"
SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/rcc-${SLURM_JOB_ID}-XXXX")"
trap 'rm -rf "$SCRATCH"' EXIT
cd "$PROJECT_ROOT"
export PYTHONPATH="$PROJECT_ROOT/src:$PROJECT_ROOT/scripts${PYTHONPATH:+:$PYTHONPATH}"
export OMP_NUM_THREADS=2 MPLBACKEND=Agg
if [ -e "$REPORT_DIR/go_no_go.json" ] || compgen -G "$EXPORT_DIR/*.h5" > /dev/null; then
    echo "RCC feasibility outputs already exist; move them aside first" >&2; exit 3
fi
mkdir -p "$REPORT_DIR" "$EXPORT_DIR"
echo "RCC feasibility on ${SLURMD_NODENAME:-unknown}"
printf '%s  %s\n' "$EXPECTED_SHA256" "$ARCHIVE" | sha256sum --check --status \
    || { echo "Archive SHA-256 mismatch" >&2; exit 1; }
tar -xzf "$ARCHIVE" -C "$SCRATCH" CardinalWorkflows/data/rcc.rda
"$RSCRIPT" -e 'cat(R.version.string, "| Cardinal", as.character(packageVersion("Cardinal")), "\n")' \
    > "$REPORT_DIR/environment.txt"

set +e
"$RSCRIPT" scripts/rcc_feasibility_export.R "$SCRATCH/CardinalWorkflows/data/rcc.rda" \
    "$EXPORT_DIR" "$REPORT_DIR/export_report.json" > "$REPORT_DIR/export_stdout.log" 2>&1
export_status=$?
set -e
echo "export step exit $export_status"

audits=0
if [ "$export_status" -eq 0 ]; then
    for h5 in "$EXPORT_DIR"/*.h5; do
        [ -e "$h5" ] || continue
        name="$(basename "$h5" .h5)"
        mask="$EXPORT_DIR/${name}_mask.npy"
        "$PYTHON" - "$h5" "$mask" <<'PY'
import sys
import h5py
import numpy as np
with h5py.File(sys.argv[1], "r") as handle:
    x = np.asarray(handle["xLocation"]).astype(np.int64).reshape(-1)
    y = np.asarray(handle["yLocation"]).astype(np.int64).reshape(-1)
    labels = np.asarray(handle["Class_Label"]).astype(np.int64).reshape(-1)
mask = np.full((y.max(), x.max()), -1, dtype=np.int64)
mask[y - 1, x - 1] = labels
np.save(sys.argv[2], mask)
PY
        set +e
        "$PYTHON" -u scripts/audit_spatial_msipl_data_contract.py --h5 "$h5" --mask "$mask" \
            --collection rcc --windows 3 5 --output "$REPORT_DIR/audit/$name" \
            > "$REPORT_DIR/audit_${name}_stdout.log" 2>&1
        set -e
        audits=$((audits + 1))
    done
fi
echo "audited exports: $audits"

"$PYTHON" - "$REPORT_DIR" "$export_status" <<'PY'
import json
import sys
from pathlib import Path
root, export_status = Path(sys.argv[1]), int(sys.argv[2])
environment = (root / "environment.txt").read_text().strip()
report_path = root / "export_report.json"
report = json.loads(report_path.read_text()) if report_path.is_file() else {}
labelled = [r["run"] for r in report.get("runs", [])
            if r.get("unlabelled_pixels") == 0 and r.get("classes_present", 0) >= 2]
audited = {}
for run in report.get("runs", []):
    if "export" in run:
        summary = root / "audit" / Path(run["export"]).stem / "summary.json"
        audited[run["run"]] = (json.loads(summary.read_text()).get("status")
                               if summary.is_file() else "missing")
passing_labelled = [r for r in labelled if audited.get(r) == "valid"]
criteria = {
    "1_cardinal_in_separate_env": "Cardinal" in environment,
    "2_rcc_rda_loads": bool(report.get("criteria", {}).get("loads")) and export_status == 0,
    "3_pixel_labels_on_at_least_4_sections": len(labelled) >= 4,
    "4_exported_hdf5_passes_data_contract_audit": len(passing_labelled) >= 4,
}
decision = {
    "status": "complete",
    "decision": "go" if all(criteria.values()) else "no-go",
    "criteria": criteria,
    "criterion_4_reading": "at least 4 labelled sections must also pass the audit, "
                           "otherwise criterion 3 has no usable sections",
    "environment": environment,
    "labelled_runs": labelled, "audit_status_by_run": audited,
    "label_levels": report.get("label_levels"), "label_column": report.get("label_column"),
    "export_report": str(report_path),
}
(root / "go_no_go.json").write_text(json.dumps(decision, indent=2) + "\n")
print(f"RCC feasibility decision written ({decision['decision']})")
PY

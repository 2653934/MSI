#!/bin/bash
#SBATCH --job-name=rcc-audit
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --partition=bigbatch
#SBATCH --time=00:20:00
#SBATCH --mem=8G
#SBATCH --output=logs/rcc-audit-%j.out
#SBATCH --error=logs/rcc-audit-%j.err

set -eo pipefail

PROJECT_ROOT="$HOME/msi"
ARCHIVE="${RCC_ARCHIVE:-/datasets/zsuliman/msi_data/zips/CardinalWorkflows_1.44.0.tar.gz}"
EXPECTED_SHA256="301a38159adc03243459095b5d7836f5900687e48e332b5e704b98e28a18c485"
OUTPUT="$PROJECT_ROOT/results/validation/rcc"

echo "RCC archive audit on $(hostname) at $(date -u)"
echo "Archive: $ARCHIVE"
test -f "$ARCHIVE" || { echo "Archive is missing" >&2; exit 1; }
printf '%s  %s\n' "$EXPECTED_SHA256" "$ARCHIVE" | sha256sum --check --status || {
    echo "SHA-256 mismatch; do not use this archive" >&2
    exit 1
}
echo "SHA-256 verified"
tar -tzf "$ARCHIVE" CardinalWorkflows/data/rcc.rda >/dev/null
echo "rcc.rda exists inside the archive"

if ! command -v Rscript >/dev/null 2>&1; then
    if ! type module >/dev/null 2>&1 && [ -f /etc/profile.d/lmod.sh ]; then
        # Batch shells may not initialize Lmod even when login shells do.
        source /etc/profile.d/lmod.sh
    fi
    if ! type module >/dev/null 2>&1; then
        echo "Lmod is unavailable in this batch shell; cannot load the cluster R module." >&2
        exit 2
    fi
    module load R/r-ubuntu-26.04-all-packages-00
fi
if ! command -v Rscript >/dev/null 2>&1; then
    echo "Rscript is still unavailable after loading the R module. Dataset-content audit not run." >&2
    exit 2
fi
echo "Rscript: $(command -v Rscript)"
Rscript --version
if ! Rscript -e 'quit(status=if (requireNamespace("Cardinal", quietly=TRUE)) 0 else 1)'; then
    echo "R is present but the Cardinal package is unavailable. Dataset-content audit not run." >&2
    exit 2
fi

mkdir -p "$OUTPUT"
cd "$PROJECT_ROOT"
Rscript --vanilla scripts/audit_rcc_dataset.R "$ARCHIVE" "$OUTPUT"

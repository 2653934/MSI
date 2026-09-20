# Upstream msiPL provenance

The code in this directory originated from the public msiPL repository.

- Upstream: <https://github.com/wabdelmoula/msiPL.git>
- Imported upstream commit: `1e8d5cff2d48851bf4b24dd43dbf8c9600ed9174`
- Local status at the repository audit on 2026-09-20:
  - `Computational_Model.py` had local modifications.
  - `Computational_Model_legacy.py` was a local untracked compatibility copy
    inside the nested upstream checkout, but is tracked by the main research
    repository.

The surrounding research repository is the source of truth for the adapted
version. The nested `baselines/msipl/.git` directory is historical metadata,
not a required runtime dependency, and must be excluded from rsync transfers.
It may be removed locally after the main repository has captured all wanted
changes and this provenance record has been committed.

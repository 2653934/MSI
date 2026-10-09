"""Provenance and restart-validation helpers for the fair-scoring campaign.

A result is reused only if its saved provenance block is identical to the one
the current code, parameters and inputs would produce. Anything else is a
stale result that must be moved aside by a person; it is never overwritten or
silently reused.
"""

import hashlib
import json
import os
from pathlib import Path

import numpy as np


class StaleResultError(RuntimeError):
    """An existing result does not match the current provenance."""


def file_sha256(path, chunk_bytes=8 * 1024 * 1024):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            block = stream.read(chunk_bytes)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def array_sha256(values, dtype=np.int64):
    array = np.ascontiguousarray(np.asarray(values, dtype=dtype))
    return hashlib.sha256(array.tobytes()).hexdigest()


def file_record(path):
    path = Path(path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": file_sha256(path)}


def code_record(paths):
    return {Path(p).name: file_sha256(p) for p in paths}


def canonical(value):
    """JSON round-trip so tuples, numpy scalars and key order compare stably."""
    return json.loads(json.dumps(value, sort_keys=True, default=_json_default))


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"not JSON serialisable: {type(value)}")


def check_existing(summary_path, expected_provenance, complete_status):
    """Return 'absent' or 'valid'; raise StaleResultError for anything else."""
    summary_path = Path(summary_path)
    if not summary_path.exists():
        return "absent"
    try:
        saved = json.loads(summary_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StaleResultError(f"{summary_path} is unreadable: {error}") from error
    if saved.get("status") != complete_status:
        raise StaleResultError(
            f"{summary_path} has status {saved.get('status')!r}; move it aside to rerun")
    if canonical(saved.get("provenance")) != canonical(expected_provenance):
        raise StaleResultError(
            f"{summary_path} was produced with different code, parameters or inputs; "
            "move it aside to rerun (results are never overwritten silently)")
    return "valid"


def atomic_write_json(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=_json_default) + "\n",
                         encoding="utf-8")
    os.replace(temporary, path)


def require_slurm(allow_outside_slurm):
    """Scientific processing must run inside a Slurm allocation, not on the login node."""
    if allow_outside_slurm:
        return
    if not os.environ.get("SLURM_JOB_ID"):
        raise SystemExit(
            "Refusing to process data outside a Slurm job (no SLURM_JOB_ID). "
            "Submit through slurm_jobs/; --allow-outside-slurm is for tests only.")

"""Tests for restart validation and the Slurm guard."""

import json
import os
import tempfile
import unittest
from pathlib import Path

import numpy as np

from spatial_msipl.provenance import (
    StaleResultError,
    array_sha256,
    atomic_write_json,
    check_existing,
    file_record,
    require_slurm,
)


class ProvenanceTests(unittest.TestCase):
    def test_check_existing_states(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            expected = {"version": 2, "parameters": {"draws": (1, 2)}, "n": 3}
            self.assertEqual(check_existing(path, expected, "complete"), "absent")
            atomic_write_json(path, {"status": "complete", "provenance": expected})
            self.assertEqual(check_existing(path, expected, "complete"), "valid")
            with self.assertRaises(StaleResultError):
                check_existing(path, {**expected, "version": 3}, "complete")
            path.write_text(json.dumps({"status": "complete"}))
            with self.assertRaises(StaleResultError):
                check_existing(path, expected, "complete")
            path.write_text(json.dumps({"status": "running", "provenance": expected}))
            with self.assertRaises(StaleResultError):
                check_existing(path, expected, "complete")

    def test_file_and_array_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.bin"
            path.write_bytes(b"abc")
            self.assertEqual(file_record(path)["sha256"],
                             "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        self.assertNotEqual(array_sha256([1, 2]), array_sha256([2, 1]))

    def test_slurm_guard(self):
        saved = os.environ.pop("SLURM_JOB_ID", None)
        try:
            with self.assertRaises(SystemExit):
                require_slurm(False)
            require_slurm(True)
            os.environ["SLURM_JOB_ID"] = "1"
            require_slurm(False)
        finally:
            os.environ.pop("SLURM_JOB_ID", None)
            if saved is not None:
                os.environ["SLURM_JOB_ID"] = saved


if __name__ == "__main__":
    unittest.main()

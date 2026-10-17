#!/usr/bin/env python3
"""Ranking-stage timing on saved artifacts (supervisor chat 2026-10-17 09:48, item 2).

Descriptive only; no decision depends on it. For one section/run (uniform_mean,
seed 1) this times, with time.perf_counter around the fair-scoring evaluator's own
functions, each ranking stage after the GMM:

  gmm_posterior        gmm_posterior_numpy on the saved latents and GMM parameters
  posterior_abs_pcc    PCC of every TIC-normalised bin with the soft posterior maps,
                       then the balanced |PCC| ranking (the primary ranking only)
  morans_i             Moore edges, Moran's I per bin, ranking
  mean_intensity       mean TIC-normalised intensity per bin, ranking
  oracle               one-vs-rest class PCC on the raw spectra (as the reference),
                       then the supervised oracle ranking

The evaluator computes the label-free statistics in one chunked HDF5 pass; here the
section is read into memory once (data_load, timed once) and TIC-normalised once
(tic_normalisation, timed once), and each stage then runs the same per-chunk calls
(chunk 1024 bins) on the in-memory arrays. Each stage is repeated (default 3) and
the median is reported. Every ranking must reproduce the saved seed-1 fair-scoring
ranking exactly (full-ranking SHA-256), and the posterior must reproduce the saved
GMM assignments; otherwise nothing is reported as timed (exit 4).

IG is not re-run: its time is the attribution script's runtime_seconds, which
includes the GMM fit and deletion faithfulness, so it is labelled that way.

Output: <output>/summary.json. An existing summary is never overwritten (exit 3).
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from evaluate_msipl_massnet_peaks import pearson_by_feature  # noqa: E402
from evaluate_spatial_msipl_attributed_peaks import read_h5_metadata  # noqa: E402
from spatial_msipl.provenance import (  # noqa: E402
    array_sha256,
    atomic_write_json,
    require_slurm,
)
from spatial_msipl.simple_baselines import (  # noqa: E402
    balanced_ranking_from_component_scores,
    check_posterior_against_saved,
    gmm_posterior_numpy,
    moore_edges,
    morans_i_per_feature,
    nan_to_lowest,
    pearson_features_vs_maps,
    rank_descending,
    supervised_oracle_ranking,
)

STAGES = ("gmm_posterior", "posterior_abs_pcc", "morans_i", "mean_intensity", "oracle")
# Name of each timed ranking in the fair-scoring summary's "rankings" record.
SAVED_NAME = {"posterior_abs_pcc": "posterior_abs_pcc_balanced", "morans_i": "morans_i",
              "mean_intensity": "mean_intensity", "oracle": "oracle"}
IG_LABEL = ("IG incl. GMM + faithfulness: the attribution script's runtime_seconds "
            "(GMM fit, integrated gradients, first-layer comparator and deletion "
            "faithfulness); the attribution step is not recorded separately")
COMPLETE = "complete"


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--attribution-dir", type=Path, required=True)
    parser.add_argument("--fair-summary", type=Path, default=None,
                        help="Seed-1 fair-scoring summary.json; its full-ranking hashes "
                             "are the reproduction check. Omit only where none exists.")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--chunk-size", type=int, default=1024)
    parser.add_argument("--allow-outside-slurm", action="store_true")
    return parser.parse_args(argv)


def cpu_model():
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as stream:
            for line in stream:
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def load_section(path):
    """Raw spectra in memory as float64, pixels x bins (the evaluator's orientation)."""
    import h5py

    mz, labels, x, y, pixels_first = read_h5_metadata(path)
    with h5py.File(path, "r") as handle:
        raw = np.asarray(handle["Data"], dtype=np.float64)
    if not pixels_first:
        raw = np.ascontiguousarray(raw.T)
    return mz, labels, x, y, raw


def tic_normalise(raw, chunk_size):
    """TIC normalisation exactly as tic_statistics: chunked TIC sum, then scale."""
    n_bins = raw.shape[1]
    tic = np.zeros(raw.shape[0])
    for start in range(0, n_bins, chunk_size):
        tic += raw[:, start:min(start + chunk_size, n_bins)].sum(axis=1)
    scale = np.zeros_like(tic)
    np.divide(1.0, tic, out=scale, where=tic > 0)
    return raw * scale[:, None]


def chunks(n_bins, chunk_size):
    for start in range(0, n_bins, chunk_size):
        yield start, min(start + chunk_size, n_bins)


def stage_gmm_posterior(latent, gmm_parameters):
    return gmm_posterior_numpy(latent, **gmm_parameters)


def stage_posterior_abs_pcc(tic, posterior, chunk_size):
    pcc = np.zeros((tic.shape[1], posterior.shape[1]))
    for start, stop in chunks(tic.shape[1], chunk_size):
        pcc[start:stop] = pearson_features_vs_maps(tic[:, start:stop], posterior)
    # The primary ranking of posterior_pcc_rankings, without the secondary ones.
    return balanced_ranking_from_component_scores(
        {c: np.abs(pcc[:, c]) for c in range(pcc.shape[1])})


def stage_morans_i(tic, x, y, chunk_size):
    sources, targets = moore_edges(x, y)
    values = np.zeros(tic.shape[1])
    for start, stop in chunks(tic.shape[1], chunk_size):
        values[start:stop] = morans_i_per_feature(tic[:, start:stop], sources, targets)
    return rank_descending(nan_to_lowest(values))


def stage_mean_intensity(tic, chunk_size):
    values = np.zeros(tic.shape[1])
    for start, stop in chunks(tic.shape[1], chunk_size):
        values[start:stop] = tic[:, start:stop].mean(axis=0)
    return rank_descending(values)


class CopyingReader:
    """Returns a copy of each slice, as an h5py dataset read does.

    pearson_by_feature centres every chunk in place, which is harmless on an HDF5
    read but would overwrite an in-memory matrix.
    """

    def __init__(self, array):
        self.array = array
        self.shape = array.shape

    def __getitem__(self, key):
        return np.array(self.array[key], dtype=np.float64, copy=True)


def stage_oracle(raw, labels, chunk_size):
    reader = CopyingReader(raw)
    correlations = {int(v): pearson_by_feature(reader, (labels == v).astype(np.uint8), True,
                                               chunk_size)
                    for v in sorted(np.unique(labels).tolist())}
    return supervised_oracle_ranking(correlations)


def timed(function, *arguments):
    started = time.perf_counter()
    value = function(*arguments)
    return value, time.perf_counter() - started


def run_stages(raw, tic, labels, x, y, latent, gmm_parameters, chunk_size):
    """One repeat: every stage once, in order. Returns (outputs, seconds)."""
    outputs, seconds = {}, {}
    outputs["gmm_posterior"], seconds["gmm_posterior"] = timed(
        stage_gmm_posterior, latent, gmm_parameters)
    outputs["posterior_abs_pcc"], seconds["posterior_abs_pcc"] = timed(
        stage_posterior_abs_pcc, tic, outputs["gmm_posterior"], chunk_size)
    outputs["morans_i"], seconds["morans_i"] = timed(stage_morans_i, tic, x, y, chunk_size)
    outputs["mean_intensity"], seconds["mean_intensity"] = timed(
        stage_mean_intensity, tic, chunk_size)
    outputs["oracle"], seconds["oracle"] = timed(stage_oracle, raw, labels, chunk_size)
    return outputs, seconds


def reproduction(outputs, saved_gmm, fair_summary):
    """Posterior vs saved GMM outputs; rankings vs the saved full-ranking hashes."""
    record = {"posterior_max_abs_difference": check_posterior_against_saved(
        outputs["gmm_posterior"], saved_gmm["component"], saved_gmm["assigned_posterior"])}
    if fair_summary is None:
        record["rankings"] = "not available (no seed-1 fair-scoring summary)"
        return record
    saved = fair_summary["rankings"]
    record["rankings"] = {}
    for stage, name in SAVED_NAME.items():
        observed = array_sha256(outputs[stage])
        if observed != saved[name]["full_ranking_sha256"]:
            raise ValueError(f"{stage}: ranking differs from the saved {name} ranking")
        record["rankings"][name] = "identical (full-ranking SHA-256)"
    return record


def ig_record(attribution_dir):
    summary = json.loads((attribution_dir / "summary.json").read_text(encoding="utf-8"))
    return {"seconds": summary.get("runtime_seconds"), "label": IG_LABEL,
            "attribution_status": summary.get("status"),
            "attribution_version": summary.get("attribution_version")}


def main(argv=None):
    args = parse_arguments(argv)
    require_slurm(args.allow_outside_slurm)
    if args.repeats < 1:
        raise SystemExit("--repeats must be at least 1")
    summary_path = args.output / "summary.json"
    if summary_path.exists():
        print(f"STALE: {summary_path} exists; move it aside, never overwrite", file=sys.stderr)
        raise SystemExit(3)
    args.output.mkdir(parents=True, exist_ok=True)

    fair_summary = None
    if args.fair_summary is not None:
        fair_summary = json.loads(args.fair_summary.read_text(encoding="utf-8"))
        if fair_summary.get("status") != COMPLETE:
            raise SystemExit(f"{args.fair_summary}: fair-scoring summary is not complete")
        if Path(fair_summary["provenance"]["input"]["path"]).name != args.input.name:
            raise SystemExit("fair-scoring summary belongs to a different input")

    (mz, labels, x, y, raw), load_seconds = timed(load_section, args.input)
    tic, tic_seconds = timed(tic_normalise, raw, args.chunk_size)
    latent = np.load(args.attribution_dir / "latent_mean.npy")
    gmm_parameters = dict(np.load(args.attribution_dir / "gmm_parameters.npz"))
    saved_gmm = np.load(args.attribution_dir / "coordinates_and_gmm.npz")
    if not (np.array_equal(x, saved_gmm["x"]) and np.array_equal(y, saved_gmm["y"])):
        raise SystemExit("attribution coordinates do not match the HDF5 input")

    repeats = []
    for _ in range(args.repeats):
        outputs, seconds = run_stages(raw, tic, labels, x, y, latent, gmm_parameters,
                                      args.chunk_size)
        repeats.append(seconds)
    try:
        checks = reproduction(outputs, saved_gmm, fair_summary)
    except ValueError as error:
        print(f"Reproduction failed; timings not reported: {error}", file=sys.stderr)
        raise SystemExit(4)

    median = {stage: statistics.median(r[stage] for r in repeats) for stage in STAGES}
    summary = {
        "status": COMPLETE,
        "purpose": "ranking-stage timing, descriptive only (supervisor chat 2026-10-17 09:48)",
        "dataset": args.input.stem,
        "input": str(args.input),
        "attribution_dir": str(args.attribution_dir),
        "fair_summary": None if args.fair_summary is None else str(args.fair_summary),
        "pixels": int(raw.shape[0]), "spectral_bins": int(raw.shape[1]),
        "gmm_components": int(len(gmm_parameters["mixture_weights"])),
        "chunk_size": args.chunk_size, "repeats": args.repeats,
        "timer": "time.perf_counter around each stage function",
        "data_load_seconds": load_seconds,
        "data_load_scope": "HDF5 metadata and the full Data matrix read into memory as float64, once",
        "tic_normalisation_seconds": tic_seconds,
        "tic_normalisation_scope": ("shared by posterior_abs_pcc, morans_i and mean_intensity; "
                                    "once, not in their stage times"),
        "stage_seconds_median": median,
        "stage_seconds_repeats": repeats,
        "posterior_abs_pcc_including_gmm_posterior_median":
            median["gmm_posterior"] + median["posterior_abs_pcc"],
        "integrated_gradients": ig_record(args.attribution_dir),
        "reproduction": checks,
        "environment": {
            "node": platform.node(), "cpu_model": cpu_model(),
            "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
            "slurm_array_task_id": os.environ.get("SLURM_ARRAY_TASK_ID"),
            "omp_num_threads": os.environ.get("OMP_NUM_THREADS"),
            "python": platform.python_version(), "numpy": np.__version__,
        },
    }
    atomic_write_json(summary_path, summary)
    print(json.dumps({"dataset": summary["dataset"], "median_seconds": median,
                      "data_load_seconds": load_seconds}, indent=2))


if __name__ == "__main__":
    main()

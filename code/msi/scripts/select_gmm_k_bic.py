#!/usr/bin/env python3
"""Gate (d): predeclared BIC choice of GMM K on saved latent means (CPU-only).

Reads ``latent_mean.npy`` and ``coordinates_and_gmm.npz`` from a production
attribution folder. It first checks that refitting the production K with the
production settings reproduces the saved component assignments, then applies
the protocol Section 6 rule. No labels are read. If BIC selects K=1, that is the
primary result; any K>=2 follow-up must be labelled as a forced sensitivity run.
"""

import argparse
from pathlib import Path

import numpy as np
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler

from spatial_msipl import gate_d_helpers, provenance
from spatial_msipl.gate_d_helpers import select_gmm_k_by_bic
from spatial_msipl.provenance import (
    StaleResultError, atomic_write_json, check_existing, code_record, file_record,
    require_slurm,
)

SELECTION_VERSION = 2


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attribution-dir", required=True, type=Path)
    parser.add_argument("--production-k", required=True, type=int)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--n-init", type=int, default=20)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--allow-outside-slurm", action="store_true",
                        help="tests only; real latents must be processed inside Slurm")
    return parser.parse_args()


def main():
    args = parse_arguments()
    require_slurm(args.allow_outside_slurm)
    args.output.mkdir(parents=True, exist_ok=True)
    expected = {
        "selection_version": SELECTION_VERSION,
        "parameters": {"production_k": args.production_k, "seed": args.seed,
                       "n_init": args.n_init,
                       "candidates": list(gate_d_helpers.BIC_CANDIDATES),
                       "tie_delta": gate_d_helpers.BIC_TIE_DELTA},
        "source_artifacts": {
            name: file_record(args.attribution_dir / name)
            for name in ("latent_mean.npy", "coordinates_and_gmm.npz")},
        "code": code_record([Path(__file__).resolve(),
                             Path(gate_d_helpers.__file__).resolve(),
                             Path(provenance.__file__).resolve()]),
    }
    try:
        if check_existing(args.output / "bic_selection.json", expected, "complete") == "valid":
            print("Existing BIC selection matches current provenance; skipped")
            return
    except StaleResultError as error:
        raise SystemExit(f"STALE: {error}")
    latent = np.load(args.attribution_dir / "latent_mean.npy").astype(np.float64)
    saved = np.load(args.attribution_dir / "coordinates_and_gmm.npz")["component"]

    standardized = StandardScaler().fit_transform(latent)
    production = GaussianMixture(
        n_components=args.production_k, covariance_type="full",
        n_init=args.n_init, random_state=args.seed,
    ).fit(standardized)
    refit_ari = float(adjusted_rand_score(saved, production.predict(standardized)))
    if refit_ari < 0.999:
        raise RuntimeError(f"production GMM refit does not reproduce saved labels (ARI {refit_ari})")

    result = select_gmm_k_by_bic(latent, seed=args.seed, n_init=args.n_init)
    result.update({
        "status": "complete",
        "provenance": expected,
        "attribution_dir": str(args.attribution_dir),
        "production_k": args.production_k,
        "production_refit_ari_to_saved": refit_ari,
        "labels_read": False,
        "convergence_note": (
            "sklearn reports convergence of the best of n_init initialisations; "
            "a K whose best fit did not converge is excluded"
        ),
    })
    atomic_write_json(args.output / "bic_selection.json", result)
    print(result["primary_result"])


if __name__ == "__main__":
    main()

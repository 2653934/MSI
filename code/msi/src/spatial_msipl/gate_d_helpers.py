"""Helpers for the bounded gate-(d) tests (protocol Section 6).

Nothing here changes the production attribution script. ``nested_attribution_samples``
reproduces ``choose_disjoint_samples`` exactly at n=12 and extends it without
moving the production faithfulness block.
"""

import numpy as np

BIC_CANDIDATES = (1, 2, 3, 4, 5, 6)
BIC_TIE_DELTA = 10.0


def production_disjoint_samples(labels, n_attribution, n_faithfulness, seed):
    """Verbatim copy of ``choose_disjoint_samples`` (production reference)."""
    rng = np.random.default_rng(seed)
    selected = {}
    for component in np.unique(labels):
        candidates = np.flatnonzero(labels == component)
        required = n_attribution + n_faithfulness
        if len(candidates) < required:
            raise ValueError(
                f"component {component} has {len(candidates)} pixels; {required} required"
            )
        shuffled = rng.permutation(candidates)
        selected[int(component)] = {
            "attribution": np.sort(shuffled[:n_attribution]),
            "faithfulness": np.sort(shuffled[n_attribution:required]),
        }
    return selected


def nested_attribution_samples(labels, n_attribution_total, seed,
                               n_base=12, n_faithfulness=32):
    """Production sample plus extra attribution pixels from the same permutation.

    Positions [0, n_base) are the production attribution pixels, positions
    [n_base, n_base + n_faithfulness) the unchanged production faithfulness
    pixels, and extra attribution pixels come from position n_base + n_faithfulness
    onward. One generator is shared sequentially across components in label
    order, exactly as in production, so the permutations are identical.
    """
    if n_attribution_total < n_base:
        raise ValueError("total attribution count must be at least the production count")
    rng = np.random.default_rng(seed)
    reserved = n_base + n_faithfulness
    selected = {}
    for component in np.unique(labels):
        candidates = np.flatnonzero(labels == component)
        if len(candidates) < reserved:
            raise ValueError(
                f"component {component} has {len(candidates)} pixels; {reserved} required"
            )
        shuffled = rng.permutation(candidates)
        extra_target = n_attribution_total - n_base
        extra_available = len(candidates) - reserved
        extra = min(extra_target, extra_available)
        attribution = np.concatenate((shuffled[:n_base], shuffled[reserved:reserved + extra]))
        selected[int(component)] = {
            "attribution": np.sort(attribution),
            "faithfulness": np.sort(shuffled[n_base:reserved]),
            "requested_attribution": int(n_attribution_total),
            "actual_attribution": int(len(attribution)),
            "capped": bool(extra < extra_target),
        }
    return selected


def mark_distinct_arms(actual_counts_by_arm):
    """Flag arms whose capped count equals the next smaller arm's count.

    ``actual_counts_by_arm`` maps requested n to {component: actual n}.
    """
    flags = {}
    previous = None
    for requested in sorted(actual_counts_by_arm):
        counts = actual_counts_by_arm[requested]
        flags[requested] = previous is None or counts != previous
        previous = counts
    return flags


GMM_ALIGNMENT_EXIT_CODE = 5
SKLEARN_COMPONENT_ATTRIBUTES = ("weights_", "means_", "covariances_", "precisions_",
                                "precisions_cholesky_")


class GmmLabelAlignmentError(ValueError):
    """The refitted GMM cannot be mapped onto the production assignment."""


def production_label_permutation(refit_labels, production_labels, n_components):
    """Return the unique relabelling that makes the refit identical to production.

    ``permutation[r]`` is the production label given to refit component ``r``.
    Only the hard assignments are used; attributions, scores and F1 never are.
    Raises GmmLabelAlignmentError unless exactly one permutation makes the
    relabelled assignment identical pixel for pixel.
    """
    from itertools import permutations

    refit_labels = np.asarray(refit_labels, dtype=np.int64)
    production_labels = np.asarray(production_labels, dtype=np.int64)
    if refit_labels.shape != production_labels.shape:
        raise GmmLabelAlignmentError("refit and production assignments differ in length")
    production_k = len(np.unique(production_labels))
    if production_k != n_components or not np.array_equal(
            np.unique(production_labels), np.arange(n_components)):
        raise GmmLabelAlignmentError(
            f"production assignment uses {production_k} components "
            f"({np.unique(production_labels).tolist()}); the refit has K={n_components}")
    if len(np.unique(refit_labels)) != n_components:
        raise GmmLabelAlignmentError(
            f"refit assignment uses {len(np.unique(refit_labels))} of its "
            f"K={n_components} components")
    matches = [p for p in permutations(range(n_components))
               if np.array_equal(np.asarray(p)[refit_labels], production_labels)]
    if len(matches) != 1:
        raise GmmLabelAlignmentError(
            f"{len(matches)} label permutations make the refitted GMM assignment identical "
            "to production; exactly one is required")
    return tuple(int(p) for p in matches[0])


def component_order(permutation):
    """Index array giving, for each production label p, the refit component it came from."""
    order = np.empty(len(permutation), dtype=np.int64)
    order[np.asarray(permutation)] = np.arange(len(permutation))
    return order


def reorder_gmm_components(gmm, order):
    """Reorder a fitted sklearn GaussianMixture in place so component p is old order[p]."""
    for attribute in SKLEARN_COMPONENT_ATTRIBUTES:
        setattr(gmm, attribute, np.asarray(getattr(gmm, attribute))[order].copy())
    return gmm


PIXEL_COUNTS = (12, 48, 192)
PIXEL_COUNT_SECTIONS = ("GBM108_positive", "40TopL")
PIXEL_COUNT_ARMS = ("central_only", "uniform_mean")
PIXEL_COUNT_TRIGGER = 0.02


def pixel_count_decision(changes, distinct):
    """Apply the predeclared gate-(d) pixel-count rule (protocol Section 6).

    ``changes[arm][section][n]`` is mSCF1(n) - mSCF1(n=12, saved production) at
    K_bin, and ``distinct[arm][section][n]`` says whether arm n differs from the
    next smaller arm after capping. A setting n triggers the 16-section rerun
    for an arm only if the change is >= +0.02 on both development sections
    (and n is distinct on both). Anything else keeps the production n=12.
    Missing sections or arms give no verdict rather than a guess.
    """
    decisions = {}
    for arm in PIXEL_COUNT_ARMS:
        record = {}
        for n in PIXEL_COUNTS[1:]:
            values = [changes.get(arm, {}).get(s, {}).get(n) for s in PIXEL_COUNT_SECTIONS]
            flags = [distinct.get(arm, {}).get(s, {}).get(n) for s in PIXEL_COUNT_SECTIONS]
            if any(v is None for v in values) or any(f is None for f in flags):
                verdict = "incomplete; no verdict"
            elif not all(flags):
                verdict = "not distinct from the next smaller count on every section; no verdict"
            elif all(v >= PIXEL_COUNT_TRIGGER for v in values):
                verdict = "triggers the predeclared 16-section rerun of this setting"
            else:
                verdict = "production n=12 stands"
            record[str(n)] = {
                "change_by_section": dict(zip(PIXEL_COUNT_SECTIONS, values)),
                "distinct_by_section": dict(zip(PIXEL_COUNT_SECTIONS, flags)),
                "verdict": verdict,
            }
        decisions[arm] = record
    return decisions


def select_gmm_k_by_bic(latent, seed, n_init=20, candidates=BIC_CANDIDATES,
                        tie_delta=BIC_TIE_DELTA):
    """Fit full-covariance GMMs on standardized latents and choose K by BIC.

    Settings match production (StandardScaler; sklearn defaults otherwise;
    ``n_init`` and ``random_state`` as production). Returns a record that never
    uses labels. If K=1 is selected, ``primary_result`` says so and
    ``sensitivity_k_ge_2`` gives the best K>=2 for a separately labelled run.
    """
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    standardized = StandardScaler().fit_transform(np.asarray(latent, dtype=np.float64))
    records = []
    for k in candidates:
        try:
            model = GaussianMixture(
                n_components=k, covariance_type="full", n_init=n_init,
                random_state=seed,
            ).fit(standardized)
        except (ValueError, np.linalg.LinAlgError) as error:
            records.append({"k": int(k), "status": "failed", "error": str(error)})
            continue
        if not model.converged_:
            records.append({"k": int(k), "status": "not_converged",
                            "bic": float(model.bic(standardized))})
            continue
        records.append({"k": int(k), "status": "converged",
                        "bic": float(model.bic(standardized)),
                        "n_iter": int(model.n_iter_)})

    valid = [r for r in records if r["status"] == "converged"]
    if not valid:
        return {"records": records, "selected_k": None,
                "primary_result": "no converged GMM for any candidate K"}

    def choose(pool):
        best = min(r["bic"] for r in pool)
        within = [r for r in pool if r["bic"] - best < tie_delta]
        return min(r["k"] for r in within)

    selected = choose(valid)
    result = {"records": records, "selected_k": int(selected),
              "tie_rule": f"smallest K within dBIC < {tie_delta}"}
    if selected == 1:
        result["primary_result"] = (
            "no supported multi-cluster latent structure under BIC"
        )
        multi = [r for r in valid if r["k"] >= 2]
        result["sensitivity_k_ge_2"] = choose(multi) if multi else None
        result["sensitivity_label"] = (
            "forced K>=2 sensitivity analysis; not BIC-selected IG"
        )
    else:
        result["primary_result"] = f"BIC selects K={selected}"
    # Note: n_init inits are internal to sklearn; it reports convergence of the
    # best init only. Per-init convergence counts would need n_init=1 refits.
    return result

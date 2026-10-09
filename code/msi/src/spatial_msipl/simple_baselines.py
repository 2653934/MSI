"""Label-free saved-artifact baselines for isolating GMM-targeted IG.

Every function here is NumPy-only. The posterior is recomputed from the saved
StandardScaler + full-covariance GMM parameters, so no retraining or GPU is
needed. See docs/research/18 Fair Scoring and Simple Baselines Protocol.md, Section 4.
"""

import numpy as np

from .peak_selection import balanced_round_robin_rankings

RANDOM_SEED = 20261009
BUDGET_MULTIPLIERS = (0.5, 0.75, 1.0, 1.5, 2.0)
MOORE_OFFSETS = (
    (-1, -1), (0, -1), (1, -1),
    (-1, 0), (1, 0),
    (-1, 1), (0, 1), (1, 1),
)


def rank_descending(scores):
    """Descending ranking with a deterministic tie-break (lower bin index first).

    The historical production lists used ``np.argsort(scores)[::-1]``, whose
    order among *exactly tied* scores depends on the NumPy version and CPU sort
    kernel. Rankings here are therefore platform-independent, and saved lists
    are compared with ``tie_permuted_positions`` rather than exact order.
    """
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    return np.lexsort((np.arange(len(scores)), -scores)).astype(np.int64)


def tie_permuted_positions(reconstructed, saved, score_at):
    """Count positions where two rankings differ only by exactly tied scores.

    ``score_at(position, bin)`` returns the score that ranked ``bin`` at that
    position. Raises ValueError unless both prefixes hold the same bins and every
    differing position swaps bins with identical scores.
    """
    reconstructed = np.asarray(reconstructed, dtype=np.int64)
    saved = np.asarray(saved, dtype=np.int64)
    if reconstructed.shape != saved.shape:
        raise ValueError("ranking prefixes have different lengths")
    if set(reconstructed.tolist()) != set(saved.tolist()):
        raise ValueError("ranking prefixes select different bins")
    differing = np.flatnonzero(reconstructed != saved)
    for position in differing:
        if score_at(position, reconstructed[position]) != score_at(position, saved[position]):
            raise ValueError(
                f"rankings differ at position {position} between bins with unequal scores")
    return int(len(differing))


def gmm_posterior_numpy(latent, scaler_mean, scaler_scale, mixture_weights,
                        component_means, precision_cholesky, **_unused):
    """Full-covariance GMM posterior, matching sklearn and attribution.gmm_posterior."""
    latent = np.asarray(latent, dtype=np.float64)
    standardized = (latent - np.asarray(scaler_mean)) / np.asarray(scaler_scale)
    means = np.asarray(component_means, dtype=np.float64)
    chol = np.asarray(precision_cholesky, dtype=np.float64)
    weights = np.asarray(mixture_weights, dtype=np.float64)
    differences = standardized[:, None, :] - means[None, :, :]
    transformed = np.einsum("bkd,kde->bke", differences, chol)
    mahalanobis = np.sum(transformed ** 2, axis=2)
    log_det = np.sum(np.log(np.diagonal(chol, axis1=1, axis2=2)), axis=1)
    dims = latent.shape[1]
    log_prob = (
        np.log(weights)[None, :] + log_det[None, :]
        - 0.5 * (dims * np.log(2.0 * np.pi) + mahalanobis)
    )
    log_prob -= log_prob.max(axis=1, keepdims=True)
    probability = np.exp(log_prob)
    return probability / probability.sum(axis=1, keepdims=True)


def check_posterior_against_saved(posterior, saved_component, saved_assigned,
                                  tolerance=1e-4):
    """Fail unless the recomputed posterior reproduces the saved GMM outputs."""
    component = np.argmax(posterior, axis=1)
    if not np.array_equal(component, np.asarray(saved_component)):
        raise ValueError("recomputed GMM components differ from saved assignments")
    assigned = posterior[np.arange(len(component)), component]
    difference = float(np.max(np.abs(assigned - np.asarray(saved_assigned))))
    if difference > tolerance:
        raise ValueError(f"recomputed assigned posterior differs by {difference}")
    return difference


def one_hot_maps(component, n_components):
    component = np.asarray(component, dtype=np.int64)
    maps = np.zeros((len(component), n_components), dtype=np.float64)
    maps[np.arange(len(component)), component] = 1.0
    return maps


def pearson_features_vs_maps(features, maps):
    """PCC between every feature column and every map column.

    ``features``: pixels x bins; ``maps``: pixels x M. Constant columns give 0,
    matching ``pearson_by_feature``.
    """
    features = np.asarray(features, dtype=np.float64)
    maps = np.asarray(maps, dtype=np.float64)
    if features.shape[0] != maps.shape[0]:
        raise ValueError("features and maps must have the same pixel count")
    centred_features = features - features.mean(axis=0, keepdims=True)
    centred_maps = maps - maps.mean(axis=0, keepdims=True)
    feature_norm = np.sqrt(np.sum(centred_features ** 2, axis=0))
    map_norm = np.sqrt(np.sum(centred_maps ** 2, axis=0))
    numerator = centred_features.T @ centred_maps
    denominator = feature_norm[:, None] * map_norm[None, :]
    result = np.zeros_like(numerator)
    np.divide(numerator, denominator, out=result, where=denominator != 0)
    return result


def moore_edges(x, y):
    """Directed Moore-neighbour edges between measured pixels (both directions)."""
    x = np.asarray(x, dtype=np.int64).reshape(-1)
    y = np.asarray(y, dtype=np.int64).reshape(-1)
    lookup = {(int(a), int(b)): index for index, (a, b) in enumerate(zip(x, y))}
    if len(lookup) != len(x):
        raise ValueError("coordinates must be unique")
    sources, targets = [], []
    for index, (a, b) in enumerate(zip(x, y)):
        for dx, dy in MOORE_OFFSETS:
            neighbour = lookup.get((int(a + dx), int(b + dy)))
            if neighbour is not None:
                sources.append(index)
                targets.append(neighbour)
    return np.asarray(sources, dtype=np.int64), np.asarray(targets, dtype=np.int64)


def morans_i_per_feature(features, sources, targets):
    """Global Moran's I for each column, as ``evaluation.morans_i``.

    Constant columns return NaN; rank them last with ``nan_to_lowest``.
    """
    features = np.asarray(features, dtype=np.float64)
    if len(sources) == 0:
        return np.full(features.shape[1], np.nan)
    centred = features - features.mean(axis=0, keepdims=True)
    denominator = np.sum(centred ** 2, axis=0)
    numerator = np.sum(centred[sources] * centred[targets], axis=0)
    values = np.full(features.shape[1], np.nan)
    valid = denominator > 0
    values[valid] = (
        features.shape[0] * numerator[valid] / (len(sources) * denominator[valid])
    )
    return values


def nan_to_lowest(scores):
    scores = np.asarray(scores, dtype=np.float64).copy()
    scores[~np.isfinite(scores)] = -np.inf
    return scores


def balanced_ranking_from_component_scores(component_scores, with_sources=False):
    """Per-component descending rankings followed by production round-robin."""
    rankings = {int(c): rank_descending(s) for c, s in component_scores.items()}
    n_bins = len(next(iter(component_scores.values())))
    selected, sources = balanced_round_robin_rankings(rankings, n_bins)
    return (selected, sources) if with_sources else selected


def posterior_pcc_rankings(pcc_by_component, hard_pcc_by_component=None):
    """Return the primary and secondary posterior-PCC rankings.

    ``pcc_by_component``: bins x K signed PCC with the soft posterior maps.
    """
    pcc = np.asarray(pcc_by_component, dtype=np.float64)
    components = range(pcc.shape[1])
    rankings = {
        "posterior_abs_pcc_balanced": balanced_ranking_from_component_scores(
            {c: np.abs(pcc[:, c]) for c in components}
        ),
        "posterior_abs_pcc_max": rank_descending(np.max(np.abs(pcc), axis=1)),
        "posterior_signed_pcc_balanced": balanced_ranking_from_component_scores(
            {c: pcc[:, c] for c in components}
        ),
    }
    if hard_pcc_by_component is not None:
        hard = np.asarray(hard_pcc_by_component, dtype=np.float64)
        rankings["hard_assignment_abs_pcc_balanced"] = (
            balanced_ranking_from_component_scores(
                {c: np.abs(hard[:, c]) for c in range(hard.shape[1])}
            )
        )
    return rankings


def production_ig_scores(attributions):
    keys = sorted(
        key for key in attributions
        if key.startswith("component_") and key.endswith("_combined_absolute_mean")
    )
    if not keys:
        raise KeyError("no per-component combined IG scores")
    return {
        int(key.split("_")[1]): np.asarray(attributions[key], dtype=np.float64)
        for key in keys
    }


def production_ig_ranking(attributions):
    """Reproduce the production IG ranking from a saved ``attributions.npz``.

    Identical to production except that exact ties are broken by bin index.
    """
    return balanced_ranking_from_component_scores(production_ig_scores(attributions))


def production_l2_ranking(attributions):
    return rank_descending(attributions["first_layer_combined_l2"])


def supervised_oracle_ranking(class_correlations):
    """Supervised oracle ceiling matching the existing reference convention.

    The reference marks a bin positive for class c when its *signed* PCC with
    the one-vs-rest mask of c passes the threshold, then unions classes. The
    oracle therefore ranks bins by the maximum signed PCC over classes. It is
    deliberately not max |PCC|: for three-class CAC a strongly negative
    correlation with one class does not make a bin reference-positive. For
    complementary two-class masks the two coincide. Not deployable.
    """
    stacked = np.stack([np.asarray(class_correlations[c], dtype=np.float64)
                        for c in sorted(class_correlations)])
    return rank_descending(np.max(stacked, axis=0))


def random_rankings(n_bins, draws=100, seed=RANDOM_SEED):
    rng = np.random.default_rng(seed)
    return [rng.permutation(n_bins) for _ in range(draws)]


def budgets(k_bin, n_bins, multipliers=BUDGET_MULTIPLIERS):
    values = {}
    for multiplier in multipliers:
        budget = int(round(k_bin * multiplier))
        if 1 <= budget <= n_bins:
            values[str(multiplier)] = budget
    return values

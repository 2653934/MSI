"""Structure-adaptive smoothing of latent means for Test S (protocol 18 Section 6.2).

Weights follow Cardinal 3.12.1 ``spatialWeights(..., weights = "adaptive")``
(R/spatialWeights.R, R/findNeighbors.R; checked 17 October 2026, supervisor chat
08:14):

- neighbourhood: ``findNeighbors(r = 1, metric = "maximum")``, the 3x3 Moore
  window over measured pixels, centre included; missing neighbours are dropped;
- spatial weight: ``alpha_ij = exp(-d_ij^2 / (2 sigma^2))``, with d_ij the
  Euclidean coordinate distance and ``sigma = (2r + 1) / 4``;
- adaptive weight: ``beta_ij = exp(-||z_i - z_j||^2 / (2 s_i^2))``, with the
  per-pixel scale ``s_i = max_{j in N(i)} ||z_i - z_j|| / 2 + sqrt(eps)``
  (Cardinal's definition replaces the 08:04 global-median lambda, by the 08:04
  rule "if Cardinal's definitions differ, use Cardinal's and record both");
- ``w_ij = alpha_ij * beta_ij``.

The 08:04 design then smooths the features, ``z~_i = sum_j w_ij z_j / sum_j w_ij``
(Cardinal itself uses the same weights in a spatially weighted distance instead).
"""

import numpy as np

from .preprocessing import build_moore_neighbour_slots, square_neighbour_offsets

RADIUS = 1
SIGMA = (2 * RADIUS + 1) / 4
# R's sqrt(.Machine$double.eps), added to the adaptive scale in Cardinal.
ADAPTIVE_EPSILON = float(np.sqrt(np.finfo(np.float64).eps))
# Slot 0 is the centre; slots 1-8 follow square_neighbour_offsets(3).
OFFSETS = ((0, 0),) + square_neighbour_offsets(3)


def measured_neighbourhoods(x, y):
    """Pixels x 9 indices of N(i) (centre first); -1 where no pixel was measured."""
    slots = build_moore_neighbour_slots(x, y)
    return np.column_stack((np.arange(len(slots), dtype=np.int64), slots))


def neighbourhood_edges(neighbourhoods):
    """Directed (source, target) pairs of the measured neighbours, centre excluded."""
    neighbours = np.asarray(neighbourhoods)[:, 1:]
    valid = neighbours >= 0
    sources = np.broadcast_to(np.arange(len(neighbours))[:, None], neighbours.shape)[valid]
    return sources.astype(np.int64), neighbours[valid].astype(np.int64)


def spatial_weights(neighbourhoods, sigma=SIGMA):
    """alpha_ij per slot (0 for missing neighbours)."""
    squared = np.asarray([dx * dx + dy * dy for dx, dy in OFFSETS], dtype=np.float64)
    alpha = np.broadcast_to(np.exp(-squared / (2.0 * sigma ** 2)),
                            np.shape(neighbourhoods)).copy()
    alpha[np.asarray(neighbourhoods) < 0] = 0.0
    return alpha


def feature_distances(features, neighbourhoods):
    """||z_i - z_j|| per slot (0 for missing neighbours)."""
    features = np.asarray(features, dtype=np.float64)
    neighbourhoods = np.asarray(neighbourhoods)
    valid = neighbourhoods >= 0
    gathered = features[np.where(valid, neighbourhoods, 0)]
    distances = np.sqrt(np.sum((gathered - features[:, None, :]) ** 2, axis=2))
    distances[~valid] = 0.0
    return distances


def adaptive_weights(features, neighbourhoods):
    """Cardinal's beta_ij with the per-pixel scale s_i (0 for missing neighbours)."""
    distances = feature_distances(features, neighbourhoods)
    scale = distances.max(axis=1) / 2.0 + ADAPTIVE_EPSILON
    beta = np.exp(-distances ** 2 / (2.0 * scale[:, None] ** 2))
    beta[np.asarray(neighbourhoods) < 0] = 0.0
    return beta, scale


def smooth(features, neighbourhoods, weights):
    """z~_i = sum_j w_ij z_j / sum_j w_ij over the measured slots."""
    features = np.asarray(features, dtype=np.float64)
    neighbourhoods = np.asarray(neighbourhoods)
    weights = np.asarray(weights, dtype=np.float64)
    if weights.shape != neighbourhoods.shape:
        raise ValueError("weights must have one value per neighbourhood slot")
    if np.any(weights[:, 0] <= 0):
        raise ValueError("every centre needs a positive self-weight")
    gathered = features[np.where(neighbourhoods >= 0, neighbourhoods, 0)]
    numerator = np.einsum("ns,nsd->nd", weights, gathered)
    return numerator / weights.sum(axis=1, keepdims=True)


def structure_adaptive_smoothing(features, x, y, sigma=SIGMA, adaptive=True):
    """Smooth standardised latents; returns (z~, record of the weights used).

    ``adaptive=False`` sets beta = 1 (the lambda -> infinity limit); a sigma near
    0 leaves only the centre weight, so z~ = z (the identity check).
    """
    neighbourhoods = measured_neighbourhoods(x, y)
    alpha = spatial_weights(neighbourhoods, sigma)
    if adaptive:
        beta, scale = adaptive_weights(features, neighbourhoods)
    else:
        beta, scale = np.where(neighbourhoods >= 0, 1.0, 0.0), None
    weights = alpha * beta
    smoothed = smooth(features, neighbourhoods, weights)
    valid = neighbourhoods >= 0
    distances = feature_distances(features, neighbourhoods)[:, 1:][valid[:, 1:]]
    record = {
        "radius": RADIUS, "sigma": float(sigma), "adaptive": bool(adaptive),
        "neighbourhood": "3x3 Moore over measured pixels, centre included",
        "measured_neighbours_per_pixel": {
            "min": int(valid[:, 1:].sum(axis=1).min()),
            "median": float(np.median(valid[:, 1:].sum(axis=1))),
            "max": int(valid[:, 1:].sum(axis=1).max())},
        "self_weight_share_median": float(np.median(weights[:, 0] / weights.sum(axis=1))),
        # The 08:04 global-median lambda, recorded but not used (Cardinal's s_i is).
        "median_neighbour_distance_lambda_0804": (float(np.median(distances))
                                                  if len(distances) else None),
    }
    if scale is not None:
        record["adaptive_scale_s_i"] = {"min": float(scale.min()),
                                        "median": float(np.median(scale)),
                                        "max": float(scale.max())}
    return smoothed, record


def ranks_of(ranking):
    """Position of every bin in a full ranking (0 = first)."""
    ranking = np.asarray(ranking, dtype=np.int64)
    if not np.array_equal(np.sort(ranking), np.arange(len(ranking))):
        raise ValueError("ranking must be a permutation of every bin")
    positions = np.empty(len(ranking), dtype=np.int64)
    positions[ranking] = np.arange(len(ranking))
    return positions


def rank_fusion(primary, secondary):
    """S2b: order by the mean of the two ranks, ties broken by the primary rank."""
    first, second = ranks_of(primary), ranks_of(secondary)
    if len(first) != len(second):
        raise ValueError("rankings cover different numbers of bins")
    return np.lexsort((first, (first + second) / 2.0)).astype(np.int64)

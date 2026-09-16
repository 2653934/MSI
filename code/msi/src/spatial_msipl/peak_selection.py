"""Peak-selection helpers for nonlinear Spatial-msiPL attribution."""

import numpy as np


def balanced_round_robin_rankings(rankings, count):
    """Select unique bins while giving each component equal opportunities.

    ``rankings`` maps component identifiers to descending one-dimensional index
    arrays.  Duplicate bins shared by components are selected only once.
    """
    if count < 1:
        raise ValueError("count must be positive")
    components = sorted(rankings)
    if not components:
        raise ValueError("at least one ranking is required")
    arrays = {
        component: np.asarray(rankings[component], dtype=np.int64).reshape(-1)
        for component in components
    }
    pointers = {component: 0 for component in components}
    selected = []
    selected_set = set()
    source_components = []
    while len(selected) < count:
        made_progress = False
        for component in components:
            ranking = arrays[component]
            while (
                pointers[component] < len(ranking)
                and int(ranking[pointers[component]]) in selected_set
            ):
                pointers[component] += 1
            if pointers[component] >= len(ranking):
                continue
            index = int(ranking[pointers[component]])
            pointers[component] += 1
            selected.append(index)
            selected_set.add(index)
            source_components.append(int(component))
            made_progress = True
            if len(selected) == count:
                break
        if not made_progress:
            raise ValueError("rankings do not contain enough unique indices")
    return np.asarray(selected, dtype=np.int64), np.asarray(
        source_components, dtype=np.int64
    )


def ppm_nonmaximum_suppression(ranked_indices, mz_values, tolerance_ppm, count=None):
    """Keep the first ranked bin within each explicit parts-per-million window."""
    if tolerance_ppm <= 0:
        raise ValueError("tolerance_ppm must be positive")
    mz = np.asarray(mz_values, dtype=np.float64).reshape(-1)
    ranking = np.asarray(ranked_indices, dtype=np.int64).reshape(-1)
    if np.any(ranking < 0) or np.any(ranking >= len(mz)):
        raise ValueError("ranking contains an out-of-range bin")
    if count is not None and count < 1:
        raise ValueError("count must be positive when provided")

    representatives = []
    for index in ranking:
        candidate_mz = mz[index]
        overlaps = False
        for representative in representatives:
            reference_mz = mz[representative]
            tolerance = tolerance_ppm * reference_mz * 1e-6
            if abs(candidate_mz - reference_mz) <= tolerance:
                overlaps = True
                break
        if not overlaps:
            representatives.append(int(index))
            if count is not None and len(representatives) == count:
                break
    return np.asarray(representatives, dtype=np.int64)

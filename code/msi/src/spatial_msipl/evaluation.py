"""Small, testable spatial-evaluation helpers for Spatial-msiPL."""

import numpy as np


def spatial_tile_folds(x, y, rows=4, columns=4, halo=1):
    """Partition pixels into rectangular test tiles with a training halo.

    Every measured pixel is tested exactly once. For a given test tile, pixels
    inside a ``halo``-pixel border around that tile are excluded from training.
    This prevents immediate spatial neighbours from leaking into the probe.
    """
    x = np.asarray(x, dtype=np.int64).reshape(-1)
    y = np.asarray(y, dtype=np.int64).reshape(-1)
    if len(x) == 0 or len(x) != len(y):
        raise ValueError("x and y must be non-empty arrays of equal length")
    if rows < 2 or columns < 2:
        raise ValueError("rows and columns must both be at least 2")
    if halo < 0:
        raise ValueError("halo cannot be negative")

    width = int(x.max() - x.min() + 1)
    height = int(y.max() - y.min() + 1)
    tile_x = np.minimum((x - x.min()) * columns // width, columns - 1)
    tile_y = np.minimum((y - y.min()) * rows // height, rows - 1)
    tile_ids = tile_y * columns + tile_x

    folds = []
    for tile_id in np.unique(tile_ids):
        test = np.flatnonzero(tile_ids == tile_id)
        test_x = x[test]
        test_y = y[test]
        in_buffer = (
            (x >= test_x.min() - halo)
            & (x <= test_x.max() + halo)
            & (y >= test_y.min() - halo)
            & (y <= test_y.max() + halo)
        )
        train = np.flatnonzero(~in_buffer)
        excluded_halo = np.flatnonzero(in_buffer & (tile_ids != tile_id))
        if len(train) == 0:
            raise ValueError("spatial fold has no training pixels")
        folds.append(
            {
                "tile": int(tile_id),
                "train": train,
                "test": test,
                "excluded_halo": excluded_halo,
            }
        )

    tested = np.concatenate([fold["test"] for fold in folds])
    if not np.array_equal(np.sort(tested), np.arange(len(x))):
        raise RuntimeError("spatial folds do not test every pixel exactly once")
    return folds


def morans_i(values, neighbour_slots):
    """Calculate global Moran's I over measured Moore-neighbour edges."""
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    slots = np.asarray(neighbour_slots, dtype=np.int64)
    if slots.ndim != 2 or slots.shape[0] != len(values):
        raise ValueError("neighbour_slots must have one row per value")
    if not np.all(np.isfinite(values)):
        raise ValueError("values must be finite")

    centred = values - values.mean()
    denominator = np.sum(centred**2)
    valid = slots >= 0
    edge_count = int(valid.sum())
    if denominator == 0 or edge_count == 0:
        return float("nan")

    sources = np.broadcast_to(np.arange(len(values))[:, None], slots.shape)[valid]
    targets = slots[valid]
    numerator = np.sum(centred[sources] * centred[targets])
    return float(len(values) * numerator / (edge_count * denominator))

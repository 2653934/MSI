from pathlib import Path

import numpy as np

from utils.data_source import load_spectrum_table


def _pearson_by_feature(binary_mask, spectra, chunk_size=2048):
    """Calculate mask-to-ion Pearson correlations without per-feature loops."""
    mask = np.asarray(binary_mask, dtype=np.float64)
    mask -= mask.mean()
    mask_norm = np.sqrt(np.dot(mask, mask))
    correlations = np.zeros(spectra.shape[1], dtype=np.float64)
    if mask_norm == 0:
        return correlations

    for start in range(0, spectra.shape[1], chunk_size):
        stop = min(start + chunk_size, spectra.shape[1])
        values = np.asarray(spectra[:, start:stop], dtype=np.float64)
        values -= values.mean(axis=0, keepdims=True)
        denominator = mask_norm * np.sqrt(np.sum(values * values, axis=0))
        numerator = mask @ values
        np.divide(
            numerator,
            denominator,
            out=correlations[start:stop],
            where=denominator != 0,
        )
    return correlations


def create_pearson_labels(
    dataname,
    folderpath,
    num_classes,
    data_path=None,
):
    """Create PCC rankings for either imzML or MassNet HDF5 spectra."""
    folder = Path(folderpath)
    labels_dir = folder / "labels"
    labels_dir.mkdir(exist_ok=True)

    mask_path = folder / "masks" / f"{dataname}_mask.npy"
    mask_orig = np.load(mask_path)
    source_path = Path(data_path) if data_path else folder / f"{dataname}.imzML"
    table = load_spectrum_table(source_path)

    rows = table.y - 1
    columns = table.x - 1
    if np.any(rows >= mask_orig.shape[0]) or np.any(columns >= mask_orig.shape[1]):
        raise ValueError(
            f"{dataname}: spectrum coordinates exceed mask shape {mask_orig.shape}"
        )

    for class_number in range(num_classes):
        mask_at_spectra = (mask_orig[rows, columns] == class_number).astype(np.uint8)
        pearson_correlations = _pearson_by_feature(
            mask_at_spectra,
            table.spectra,
        )

        ranking = np.argsort(pearson_correlations)[::-1]
        np.save(labels_dir / f"{dataname}_class{class_number}_ranking.npy", ranking)
        np.save(
            labels_dir / f"{dataname}_class{class_number}_mz_ranking.npy",
            table.mz_values[ranking],
        )
        np.save(
            labels_dir / f"{dataname}_class{class_number}_pearson_ranking.npy",
            pearson_correlations[ranking],
        )

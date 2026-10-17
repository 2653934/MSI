"""Test V: a PCA segmentation of the VAE's own centre input (protocol 18 Section 6.4).

The VAE's encoder receives, for every measured pixel, the raw spectrum read as
float32 and divided by its total ion current: ``H5SpatialContextDataset.__getitem__``
(and its cached subclass) returns ``target = tic_normalize(spectra)[0]``, and
``CentralOnlyVAE.encode`` receives that ``target``. No further scaling is applied
before the first dense layer (checked 17 October 2026 against preprocessing.py,
training.py, model.py and run_spatial_msipl_gmm_integrated_gradients.encode_all).
``vae_centre_inputs`` reproduces that input for all pixels at once.

PCA (sklearn, randomized solver, random_state 1) then gives the scores that the
production segmentation step clusters: StandardScaler, then a full-covariance
GaussianMixture with the production K, reg_covar 1e-6, n_init 20, seed 1.
"""

import numpy as np

from .preprocessing import tic_normalize

PRIMARY_COMPONENTS = 5        # = the VAE latent dimension
SENSITIVITY_COMPONENTS = 20   # descriptive (a)
PCA_SEED = 1
GMM_N_INIT = 20
GMM_SEED = 1
REG_COVAR = 1e-6
PREPROCESSING_RECORD = {
    "function": "spatial_msipl.preprocessing.tic_normalize on the raw Data rows read as float32",
    "matches": ("H5SpatialContextDataset.__getitem__ / CachedH5SpatialContextDataset "
                "'target' (the central spectrum CentralOnlyVAE.encode receives)"),
    "pixels": "measured pixels only (every row of Data)",
}


def vae_centre_inputs(path):
    """Pixels x bins float32: the VAE's centre input for every measured pixel."""
    import h5py

    with h5py.File(path, "r") as handle:
        n_pixels = len(np.asarray(handle["xLocation"]).reshape(-1))
        n_mz = len(np.asarray(handle["mzArray"]).reshape(-1))
        raw = handle["Data"][...]
    if raw.shape == (n_mz, n_pixels):      # the dataset's orientation order
        raw = raw.T
    elif raw.shape != (n_pixels, n_mz):
        raise ValueError(f"cannot orient Data shape {raw.shape}")
    # As CachedH5SpatialContextDataset: one float32 read, then row-wise TIC.
    return tic_normalize(np.ascontiguousarray(raw, dtype=np.float32))


def fit_gmm(features, k, n_init=GMM_N_INIT, seed=GMM_SEED):
    """The production segmentation step: StandardScaler + full-covariance GMM."""
    from sklearn.mixture import GaussianMixture
    from sklearn.preprocessing import StandardScaler

    standardized = StandardScaler().fit_transform(np.asarray(features, dtype=np.float64))
    model = GaussianMixture(n_components=k, covariance_type="full", reg_covar=REG_COVAR,
                            n_init=n_init, random_state=seed).fit(standardized)
    return model, standardized


def pca_segmentation(features, n_components, k):
    """PCA scores clustered by the production GMM; returns (posterior, component, record)."""
    from sklearn.decomposition import PCA

    pca = PCA(n_components=n_components, svd_solver="randomized", random_state=PCA_SEED)
    scores = pca.fit_transform(features)
    model, standardized = fit_gmm(scores, k)
    posterior = model.predict_proba(standardized)
    component = np.argmax(posterior, axis=1)
    counts = np.bincount(component, minlength=k)
    ratio = [float(v) for v in pca.explained_variance_ratio_]
    record = {
        "n_components": int(n_components),
        "pca": {"svd_solver": "randomized", "random_state": PCA_SEED},
        "explained_variance_ratio": ratio,
        "explained_variance_ratio_sum": float(np.sum(ratio)),
        "gmm": {"components": int(k), "covariance_type": "full", "reg_covar": REG_COVAR,
                "n_init": GMM_N_INIT, "seed": GMM_SEED, "scaler": "StandardScaler"},
        "converged": bool(model.converged_), "n_iter": int(model.n_iter_),
        "component_counts": counts.tolist(),
        "empty_components": int(np.count_nonzero(counts == 0)),
    }
    return posterior, component, record

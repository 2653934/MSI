"""Differentiable GMM targets and Integrated Gradients for Spatial-msiPL."""

import math

import torch


def gmm_posterior(
    latent,
    scaler_mean,
    scaler_scale,
    mixture_weights,
    component_means,
    precision_cholesky,
):
    """Return full-covariance GMM posterior probabilities.

    The parameters correspond to a scikit-learn ``StandardScaler`` followed by
    a full-covariance ``GaussianMixture``.  Keeping the calculation in PyTorch
    lets gradients flow from a cluster posterior through the complete encoder.
    """
    if latent.ndim != 2:
        raise ValueError("latent must have shape (batch, dimensions)")
    standardized = (latent - scaler_mean) / scaler_scale
    differences = standardized[:, None, :] - component_means[None, :, :]
    transformed = torch.einsum(
        "bkd,kde->bke", differences, precision_cholesky
    )
    mahalanobis = transformed.square().sum(dim=2)
    log_precision_determinant = torch.log(
        torch.diagonal(precision_cholesky, dim1=1, dim2=2)
    ).sum(dim=1)
    dimensions = latent.shape[1]
    component_log_probability = (
        torch.log(mixture_weights)
        + log_precision_determinant[None, :]
        - 0.5 * (dimensions * math.log(2.0 * math.pi) + mahalanobis)
    )
    return torch.softmax(component_log_probability, dim=1)


def integrated_gradients_cluster_posterior(
    model,
    central,
    neighbours,
    neighbour_mask,
    central_baseline,
    neighbour_baseline,
    target_component,
    gmm_parameters,
    steps=64,
    internal_batch_size=8,
):
    """Attribute one GMM posterior to central and neighbour spectra separately.

    ``steps`` is the number of trapezoidal integration intervals, so the method
    evaluates ``steps + 1`` points including both path endpoints.
    """
    if steps < 1 or internal_batch_size < 1:
        raise ValueError("steps and internal_batch_size must be positive")
    if central.shape[0] != 1 or neighbours.shape[0] != 1:
        raise ValueError("Integrated Gradients expects one pixel at a time")
    if central.shape != central_baseline.shape:
        raise ValueError("central and central_baseline shapes differ")
    if neighbours.shape != neighbour_baseline.shape:
        raise ValueError("neighbours and neighbour_baseline shapes differ")

    central_delta = central - central_baseline
    neighbour_delta = neighbours - neighbour_baseline
    central_gradient_sum = torch.zeros_like(central)
    neighbour_gradient_sum = torch.zeros_like(neighbours)
    alphas = torch.linspace(
        0.0, 1.0, steps + 1, device=central.device, dtype=central.dtype
    )

    for start in range(0, len(alphas), internal_batch_size):
        alpha = alphas[start : start + internal_batch_size]
        alpha_central = alpha.view(-1, 1)
        alpha_neighbour = alpha.view(-1, 1, 1)
        interpolated_central = (
            central_baseline
            + alpha_central * central_delta
        ).detach().requires_grad_(True)
        interpolated_neighbours = (
            neighbour_baseline
            + alpha_neighbour * neighbour_delta
        ).detach().requires_grad_(True)
        expanded_mask = neighbour_mask.expand(len(alpha), -1)
        latent = model.encode(
            interpolated_central, interpolated_neighbours, expanded_mask
        )[0]
        posterior = gmm_posterior(latent, **gmm_parameters)
        target = posterior[:, int(target_component)]
        central_gradient, neighbour_gradient = torch.autograd.grad(
            target.sum(), (interpolated_central, interpolated_neighbours)
        )

        trapezoid_weights = torch.ones_like(alpha)
        trapezoid_weights[alpha == 0.0] = 0.5
        trapezoid_weights[alpha == 1.0] = 0.5
        central_gradient_sum += (
            central_gradient * trapezoid_weights.view(-1, 1)
        ).sum(dim=0, keepdim=True)
        neighbour_gradient_sum += (
            neighbour_gradient * trapezoid_weights.view(-1, 1, 1)
        ).sum(dim=0, keepdim=True)

    central_attribution = central_delta * central_gradient_sum / float(steps)
    neighbour_attribution = neighbour_delta * neighbour_gradient_sum / float(steps)

    with torch.no_grad():
        input_latent = model.encode(central, neighbours, neighbour_mask)[0]
        baseline_latent = model.encode(
            central_baseline, neighbour_baseline, neighbour_mask
        )[0]
        input_score = gmm_posterior(input_latent, **gmm_parameters)[
            0, int(target_component)
        ]
        baseline_score = gmm_posterior(baseline_latent, **gmm_parameters)[
            0, int(target_component)
        ]
        score_delta = input_score - baseline_score
        attribution_sum = central_attribution.sum() + neighbour_attribution.sum()
        residual = score_delta - attribution_sum

    diagnostics = {
        "input_score": float(input_score.cpu()),
        "baseline_score": float(baseline_score.cpu()),
        "score_delta": float(score_delta.cpu()),
        "attribution_sum": float(attribution_sum.cpu()),
        "completeness_residual": float(residual.cpu()),
    }
    return central_attribution, neighbour_attribution, diagnostics


def first_layer_l2_importance(model):
    """Return the central/context L2 norms of the first encoder layer."""
    weight = model.vae.encoder_dense.weight.detach()
    spectral_dim = model.vae.spectral_dim
    if weight.shape[1] != 2 * spectral_dim:
        raise ValueError("first-layer comparator requires a contextual VAE")
    return (
        torch.linalg.vector_norm(weight[:, :spectral_dim], dim=0),
        torch.linalg.vector_norm(weight[:, spectral_dim:], dim=0),
    )

"""Comparable neighbourhood aggregation strategies for Spatial-msiPL."""

import math

import torch
from torch import nn


def _validate_neighbourhood(central, neighbours, neighbour_mask):
    if central.ndim != 2:
        raise ValueError("central must have shape (batch, m/z)")
    if neighbours.ndim != 3 or neighbours.shape[1] != 8:
        raise ValueError("neighbours must have shape (batch, 8, m/z)")
    if neighbour_mask.ndim != 2 or neighbour_mask.shape[1] != 8:
        raise ValueError("neighbour_mask must have shape (batch, 8)")
    if neighbours.shape[0] != central.shape[0] or neighbours.shape[2] != central.shape[1]:
        raise ValueError("central and neighbours have incompatible dimensions")
    if neighbour_mask.shape[0] != central.shape[0]:
        raise ValueError("central and neighbour_mask have incompatible batch sizes")


def _masked_softmax(logits, mask, dimension):
    """Softmax over valid entries; return zero weights when every entry is absent."""
    boolean_mask = mask.to(dtype=torch.bool)
    minimum = torch.finfo(logits.dtype).min
    masked_logits = torch.where(boolean_mask, logits, minimum)
    maximum = masked_logits.max(dim=dimension, keepdim=True).values
    unnormalized = torch.exp(masked_logits - maximum) * boolean_mask.to(logits.dtype)
    denominator = unnormalized.sum(dim=dimension, keepdim=True)
    return unnormalized / denominator.clamp_min(torch.finfo(logits.dtype).eps)


def _tic_normalize_context(context):
    total = context.sum(dim=1, keepdim=True)
    return context / total.clamp_min(torch.finfo(context.dtype).eps)


class UniformMeanNeighbourhood(nn.Module):
    """Give every valid measured neighbour the same weight."""

    name = "uniform_mean"

    def forward(self, central, neighbours, neighbour_mask):
        _validate_neighbourhood(central, neighbours, neighbour_mask)
        logits = torch.zeros_like(neighbour_mask, dtype=central.dtype)
        weights = _masked_softmax(logits, neighbour_mask, dimension=1)
        context = torch.sum(neighbours * weights.unsqueeze(-1), dim=1)
        return _tic_normalize_context(context), weights

    def configuration(self):
        return {"name": self.name, "learnable_parameters": 0, "orientation_free": True}


class DepthwiseNeighbourhood(nn.Module):
    """Learn eight position weights independently for every m/z channel."""

    name = "depthwise"

    def __init__(self, spectral_dim):
        super().__init__()
        if spectral_dim < 1:
            raise ValueError("spectral_dim must be positive")
        self.spectral_dim = int(spectral_dim)
        # Zero logits make the initial behaviour exactly equal to the uniform mean.
        self.position_logits = nn.Parameter(torch.zeros(8, self.spectral_dim))

    def forward(self, central, neighbours, neighbour_mask):
        _validate_neighbourhood(central, neighbours, neighbour_mask)
        if central.shape[1] != self.spectral_dim:
            raise ValueError(f"expected {self.spectral_dim} m/z bins")
        logits = self.position_logits.unsqueeze(0).expand(central.shape[0], -1, -1)
        mask = neighbour_mask.to(torch.bool).unsqueeze(-1).expand_as(logits)
        weights = _masked_softmax(logits, mask, dimension=1)
        context = torch.sum(neighbours * weights, dim=1)
        return _tic_normalize_context(context), weights

    def configuration(self):
        return {
            "name": self.name,
            "learnable_parameters": self.position_logits.numel(),
            "orientation_free": False,
            "initialization": "uniform over valid neighbours",
        }


class AttentionNeighbourhood(nn.Module):
    """Weight neighbours by learned spectral similarity to the central pixel."""

    name = "attention"

    def __init__(self, spectral_dim, attention_dim=8, input_scale="spectral_bins"):
        super().__init__()
        if spectral_dim < 1 or attention_dim < 1:
            raise ValueError("spectral_dim and attention_dim must be positive")
        self.spectral_dim = int(spectral_dim)
        self.attention_dim = int(attention_dim)
        scale_names = {
            "unit": 1.0,
            "sqrt_bins": math.sqrt(self.spectral_dim),
            "spectral_bins": float(self.spectral_dim),
        }
        if input_scale not in scale_names:
            raise ValueError(
                "input_scale must be unit, sqrt_bins, or spectral_bins"
            )
        self.input_scale_name = input_scale
        self.input_scale = scale_names[input_scale]
        # The same projection is used for every neighbour, so slot orientation is
        # not encoded. Scaling compensates for TIC-normalized values being tiny.
        self.projection = nn.Linear(self.spectral_dim, self.attention_dim)

    def forward(self, central, neighbours, neighbour_mask):
        _validate_neighbourhood(central, neighbours, neighbour_mask)
        if central.shape[1] != self.spectral_dim:
            raise ValueError(f"expected {self.spectral_dim} m/z bins")

        scale = self.input_scale
        central_embedding = torch.tanh(self.projection(central * scale))
        neighbour_embedding = torch.tanh(self.projection(neighbours * scale))
        similarity = torch.sum(
            neighbour_embedding * central_embedding.unsqueeze(1), dim=-1
        ) / math.sqrt(self.attention_dim)
        weights = _masked_softmax(similarity, neighbour_mask, dimension=1)
        context = torch.sum(neighbours * weights.unsqueeze(-1), dim=1)
        return _tic_normalize_context(context), weights

    def configuration(self):
        configuration = {
            "name": self.name,
            "attention_dim": self.attention_dim,
            "learnable_parameters": sum(p.numel() for p in self.parameters()),
            "orientation_free": True,
            "similarity": "shared nonlinear spectral projection and scaled dot product",
        }
        # Omit the historical default so old checkpoint resume signatures remain
        # byte-for-byte compatible after this option was introduced.
        if self.input_scale_name != "spectral_bins":
            configuration["input_scale_name"] = self.input_scale_name
            configuration["input_scale"] = self.input_scale
        return configuration


def create_neighbourhood_aggregator(
    name, spectral_dim, attention_dim=8, attention_input_scale="spectral_bins"
):
    """Construct a neighbourhood strategy from its experiment name."""
    normalized_name = name.lower().replace("-", "_")
    if normalized_name in {"uniform", "uniform_mean"}:
        return UniformMeanNeighbourhood()
    if normalized_name == "depthwise":
        return DepthwiseNeighbourhood(spectral_dim)
    if normalized_name == "attention":
        return AttentionNeighbourhood(
            spectral_dim,
            attention_dim=attention_dim,
            input_scale=attention_input_scale,
        )
    raise ValueError(f"unknown neighbourhood strategy: {name}")

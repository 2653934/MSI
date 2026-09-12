"""The contextual variational autoencoder used by Spatial-msiPL."""

import torch
from torch import nn

from .neighbourhood import create_neighbourhood_aggregator


class SpatialVAE(nn.Module):
    """Encode central + context spectra and reconstruct only the central spectrum.

    ``spectral_dim`` is the number of m/z bins in one spectrum. The encoder input
    therefore has ``2 * spectral_dim`` values, while the decoder output has only
    ``spectral_dim`` values.
    """

    def __init__(self, spectral_dim, hidden_dim=512, latent_dim=5):
        super().__init__()
        if spectral_dim < 1 or hidden_dim < 1 or latent_dim < 1:
            raise ValueError("all model dimensions must be positive")

        self.spectral_dim = int(spectral_dim)
        self.hidden_dim = int(hidden_dim)
        self.latent_dim = int(latent_dim)

        self.encoder_dense = nn.Linear(2 * self.spectral_dim, self.hidden_dim)
        self.encoder_batchnorm = nn.BatchNorm1d(self.hidden_dim)
        self.z_mean = nn.Linear(self.hidden_dim, self.latent_dim)
        self.z_log_var = nn.Linear(self.hidden_dim, self.latent_dim)

        self.decoder_dense = nn.Linear(self.latent_dim, self.hidden_dim)
        self.decoder_batchnorm = nn.BatchNorm1d(self.hidden_dim)
        self.decoder_output = nn.Linear(self.hidden_dim, self.spectral_dim)
        self.relu = nn.ReLU()

    def encode(self, contextual_spectrum):
        """Return the mean and log-variance of the learned latent distribution."""
        expected = 2 * self.spectral_dim
        if contextual_spectrum.ndim != 2 or contextual_spectrum.shape[1] != expected:
            raise ValueError(
                f"encoder input must have shape (batch, {expected}); "
                f"received {tuple(contextual_spectrum.shape)}"
            )
        hidden = self.relu(self.encoder_batchnorm(self.encoder_dense(contextual_spectrum)))
        return self.z_mean(hidden), self.z_log_var(hidden)

    @staticmethod
    def reparameterize(mean, log_variance):
        """Draw z = mean + standard_deviation * epsilon, epsilon ~ N(0, I)."""
        standard_deviation = torch.exp(0.5 * log_variance)
        epsilon = torch.randn_like(standard_deviation)
        return mean + standard_deviation * epsilon

    def decode(self, latent):
        """Decode a latent sample into a reconstructed central spectrum."""
        hidden = self.relu(self.decoder_batchnorm(self.decoder_dense(latent)))
        return torch.sigmoid(self.decoder_output(hidden))

    def forward(self, contextual_spectrum):
        mean, log_variance = self.encode(contextual_spectrum)
        latent = self.reparameterize(mean, log_variance)
        reconstruction = self.decode(latent)
        return reconstruction, mean, log_variance

    def configuration(self):
        """Return the dimensions needed to reconstruct this model later."""
        return {
            "spectral_dim": self.spectral_dim,
            "contextual_input_dim": 2 * self.spectral_dim,
            "hidden_dim": self.hidden_dim,
            "latent_dim": self.latent_dim,
        }


class NeighbourhoodSpatialVAE(nn.Module):
    """Combine one neighbourhood strategy with the otherwise identical VAE."""

    def __init__(
        self,
        spectral_dim,
        neighbourhood="uniform_mean",
        hidden_dim=512,
        latent_dim=5,
        attention_dim=8,
    ):
        super().__init__()
        self.aggregator = create_neighbourhood_aggregator(
            neighbourhood, spectral_dim, attention_dim=attention_dim
        )
        self.vae = SpatialVAE(spectral_dim, hidden_dim=hidden_dim, latent_dim=latent_dim)

    def build_contextual_input(self, central, neighbours, neighbour_mask):
        context, weights = self.aggregator(central, neighbours, neighbour_mask)
        return torch.cat((central, context), dim=1), context, weights

    def encode(self, central, neighbours, neighbour_mask):
        contextual, context, weights = self.build_contextual_input(
            central, neighbours, neighbour_mask
        )
        mean, log_variance = self.vae.encode(contextual)
        return mean, log_variance, context, weights

    def forward(self, central, neighbours, neighbour_mask):
        mean, log_variance, context, weights = self.encode(
            central, neighbours, neighbour_mask
        )
        latent = self.vae.reparameterize(mean, log_variance)
        reconstruction = self.vae.decode(latent)
        return reconstruction, mean, log_variance, context, weights

    def configuration(self):
        configuration = self.vae.configuration()
        configuration["neighbourhood"] = self.aggregator.configuration()
        return configuration

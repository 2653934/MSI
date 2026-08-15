# -*- coding: utf-8 -*-
"""
msiPL (Abdelmoula et al.) Neural Network Architecture

VAE_BN:
    Fully-connected Variational Autoencoder equipped with
    Batch Normalization.

This version preserves the original msiPL architecture while
using a TensorFlow/Keras-compatible VAE loss implementation.
"""

import numpy as np

from keras.layers import (
    Lambda,
    Input,
    Dense,
    ReLU,
    BatchNormalization,
)
from keras.models import Model
from keras import backend as K


class VAE_BN(object):

    def __init__(self, nSpecFeatures, intermediate_dim, latent_dim):
        self.nSpecFeatures = nSpecFeatures
        self.intermediate_dim = intermediate_dim
        self.latent_dim = latent_dim

    def sampling(self, args):
        """
        Reparameterization trick.

        z = z_mean + exp(0.5 * z_log_var) * epsilon

        where epsilon ~ N(0, I).
        """
        z_mean, z_log_var = args

        batch = K.shape(z_mean)[0]
        dim = K.int_shape(z_mean)[1]

        epsilon = K.random_normal(
            shape=(batch, dim),
            mean=0.0,
            stddev=1.0,
        )

        return z_mean + K.exp(0.5 * z_log_var) * epsilon

    def get_architecture(self):

        # ============================================================
        # 1. Encoder
        # ============================================================

        input_shape = (self.nSpecFeatures,)

        inputs = Input(
            shape=input_shape,
            name="encoder_input",
        )

        h = Dense(
            self.intermediate_dim,
            name="encoder_dense",
        )(inputs)

        h = BatchNormalization(
            name="encoder_batchnorm",
        )(h)

        h = ReLU(
            name="encoder_relu",
        )(h)

        z_mean = Dense(
            self.latent_dim,
            name="z_mean",
        )(h)

        z_mean = BatchNormalization(
            name="z_mean_batchnorm",
        )(z_mean)

        z_log_var = Dense(
            self.latent_dim,
            name="z_log_var",
        )(h)

        z_log_var = BatchNormalization(
            name="z_log_var_batchnorm",
        )(z_log_var)

        z = Lambda(
            self.sampling,
            output_shape=(self.latent_dim,),
            name="z",
        )([z_mean, z_log_var])

        encoder = Model(
            inputs,
            [z_mean, z_log_var, z],
            name="encoder",
        )

        print("==== Encoder Architecture...")
        encoder.summary()

        # ============================================================
        # 2. Decoder
        # ============================================================

        latent_inputs = Input(
            shape=(self.latent_dim,),
            name="Latent_Space",
        )

        hdec = Dense(
            self.intermediate_dim,
            name="decoder_dense",
        )(latent_inputs)

        hdec = BatchNormalization(
            name="decoder_batchnorm",
        )(hdec)

        hdec = ReLU(
            name="decoder_relu",
        )(hdec)

        outputs = Dense(
            self.nSpecFeatures,
            activation="sigmoid",
            name="decoder_output",
        )(hdec)

        decoder = Model(
            latent_inputs,
            outputs,
            name="decoder",
        )

        print("==== Decoder Architecture...")
        decoder.summary()

        # ============================================================
        # 3. VAE
        # ============================================================

        # Build the encoder graph once and explicitly retain its
        # symbolic outputs. This avoids the graph-scope issue caused
        # by repeatedly calling encoder(inputs).
        z_mean_out, z_log_var_out, z_out = encoder(inputs)

        outputs = decoder(z_out)

        VAE_BN_model = Model(
            inputs,
            outputs,
            name="VAE_BN",
        )

        # ============================================================
        # 4. VAE Loss
        # ============================================================

        # KL divergence:
        #
        # -0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
        #
        kl_loss = (
            1.0
            + z_log_var_out
            - K.square(z_mean_out)
            - K.exp(z_log_var_out)
        )

        kl_loss = K.sum(
            kl_loss,
            axis=-1,
        )

        kl_loss *= -0.5

        # Reconstruction loss.
        #
        # msiPL uses categorical_crossentropy despite the sigmoid
        # output layer. We preserve that behaviour from the original
        # implementation.
        reconstruction_loss = K.categorical_crossentropy(
            inputs,
            outputs,
        )

        reconstruction_loss *= self.nSpecFeatures

        # Total VAE loss.
        model_loss = K.mean(
            reconstruction_loss + kl_loss
        )

        VAE_BN_model.add_loss(model_loss)

        VAE_BN_model.compile(
            optimizer="adam"
        )

        return VAE_BN_model, encoder
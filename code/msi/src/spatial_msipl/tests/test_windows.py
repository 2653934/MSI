"""Independent small-grid checks before submitting window experiments."""

import tempfile
import unittest
import importlib.util
from pathlib import Path

import h5py
import numpy as np
import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import UniformMeanNeighbourhood
from spatial_msipl.training import train_vae
from spatial_msipl.preprocessing import (
    MOORE_OFFSETS, build_moore_neighbour_slots, build_square_neighbour_slots,
    square_neighbour_offsets, H5SpatialContextDataset, CachedH5SpatialContextDataset,
    tic_normalize, checkpoint_input_spec,
)


class WindowTests(unittest.TestCase):
    def test_shuffled_context_is_seeded_nonlocal_and_cache_equivalent(self):
        coordinates = [(x, y) for y in range(1, 8) for x in range(1, 8)
                       if (x, y) != (3, 4)]
        spectra = np.asarray([[i + 1, 2, 3] for i in range(len(coordinates))], dtype=np.float64)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "shuffled.h5"
            with h5py.File(path, "w") as handle:
                handle["Data"] = spectra.T
                handle["mzArray"] = [100, 101, 102]
                handle["xLocation"] = [x for x, _ in coordinates]
                handle["yLocation"] = [y for _, y in coordinates]
            first = H5SpatialContextDataset(path, True, 5, "shuffled", 17)
            same = CachedH5SpatialContextDataset(path, True, 5, "shuffled", 17)
            other = H5SpatialContextDataset(path, True, 5, "shuffled", 18)
            measured = H5SpatialContextDataset(path, True, 5)
            try:
                self.assertEqual(first.context_permutation_sha256, same.context_permutation_sha256)
                self.assertNotEqual(first.context_permutation_sha256, other.context_permutation_sha256)
                for i in range(len(first)):
                    forbidden = set(first.neighbour_indices[i].tolist()) | {i}
                    sources = first.context_source_slots[i][first.neighbour_slots[i] >= 0]
                    self.assertTrue(all(int(source) not in forbidden for source in sources))
                    sample = first[i]
                    for key, value in sample.items():
                        np.testing.assert_array_equal(value, same[i][key])
                    np.testing.assert_array_equal(sample["target"], measured[i]["target"])
                    expected = tic_normalize(spectra[sources]).mean(0) if len(sources) else np.zeros(3)
                    np.testing.assert_allclose(sample["context"], expected, rtol=1e-6)
                    np.testing.assert_array_equal(sample["neighbour_mask"], measured[i]["neighbour_mask"])
            finally:
                for dataset in (first, same, other, measured):
                    dataset.close()

    def test_checkpoint_inputs_keep_historical_defaults_and_reject_mismatch(self):
        historical = {"model_configuration": {"spectral_dim": 3,
                                             "neighbourhood": {"name": "uniform_mean"}}}
        self.assertEqual(checkpoint_input_spec(historical)["window_size"], 3)
        self.assertEqual(checkpoint_input_spec(historical)["context_mode"], "measured")
        new = {"model_configuration": {"spectral_dim": 3, "window_size": 5,
                                        "neighbourhood": {"name": "uniform_mean"}},
               "resume_signature": {"dataset_window_size": 5, "context_mode": "shuffled",
                                    "context_seed": 17, "context_permutation_sha256": "example"}}
        self.assertEqual(checkpoint_input_spec(new)["context_seed"], 17)
        new["resume_signature"]["dataset_window_size"] = 3
        with self.assertRaises(ValueError):
            checkpoint_input_spec(new)

    def test_training_checkpoint_binds_shuffle_seed_and_window(self):
        coordinates = [(x, y) for y in range(1, 8) for x in range(1, 8)]
        spectra = np.asarray([[i + 1, 2, 3] for i in range(len(coordinates))], dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "training.h5"
            with h5py.File(path, "w") as handle:
                handle["Data"] = spectra.T
                handle["mzArray"] = [100, 101, 102]
                handle["xLocation"] = [x for x, _ in coordinates]
                handle["yLocation"] = [y for _, y in coordinates]
            dataset = CachedH5SpatialContextDataset(path, True, 5, "shuffled", 17)
            output = Path(directory) / "first"
            model = NeighbourhoodSpatialVAE(3, "uniform_mean", hidden_dim=4,
                                            latent_dim=2, window_size=5)
            try:
                train_vae(model, dataset, output, epochs=1, batch_size=7,
                          seed=1, checkpoint_interval=1)
                checkpoint = torch.load(output / "checkpoint.pt", map_location="cpu")
                spec = checkpoint_input_spec(checkpoint)
                self.assertEqual(spec["window_size"], 5)
                self.assertEqual(spec["context_seed"], 17)
                self.assertEqual(spec["context_permutation_sha256"],
                                 dataset.context_permutation_sha256)
                changed = CachedH5SpatialContextDataset(path, True, 5, "shuffled", 18)
                try:
                    with self.assertRaisesRegex(ValueError, "configuration does not match"):
                        train_vae(NeighbourhoodSpatialVAE(3, "uniform_mean", hidden_dim=4,
                                                          latent_dim=2, window_size=5),
                                  changed, Path(directory) / "second", epochs=1,
                                  batch_size=7, seed=1,
                                  resume_checkpoint=output / "checkpoint.pt")
                finally:
                    changed.close()
            finally:
                dataset.close()

    def test_attribution_reconstructs_new_variant_without_using_old_defaults(self):
        script_path = Path(__file__).resolve().parents[3] / "scripts" / "run_spatial_msipl_gmm_integrated_gradients.py"
        module_spec = importlib.util.spec_from_file_location("window_attribution_entry", script_path)
        entry = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(entry)
        model = NeighbourhoodSpatialVAE(3, "uniform_mean", hidden_dim=4,
                                        latent_dim=2, window_size=5)
        checkpoint = {"completed_epochs": 100,
                      "model_configuration": model.configuration(),
                      "model_state_dict": model.state_dict(),
                      "resume_signature": {"dataset_window_size": 5,
                                           "context_mode": "shuffled",
                                           "context_seed": 17,
                                           "context_permutation_sha256": "example"}}
        reconstructed, _ = entry.load_model("unused", 3, "shuffled_uniform", "cpu",
                                             checkpoint=checkpoint)
        self.assertEqual(reconstructed.neighbour_slots, 24)
        with self.assertRaisesRegex(ValueError, "measured-context"):
            entry.load_model("unused", 3, "uniform_mean", "cpu", checkpoint=checkpoint)
        with self.assertRaises(ValueError):
            entry.load_model("unused", 4, "shuffled_uniform", "cpu", checkpoint=checkpoint)

    def test_legacy_order_and_invalid_sizes(self):
        self.assertEqual(MOORE_OFFSETS, ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)))
        for size in (0, -1, 2, 4, 3.5, True):
            with self.assertRaises(ValueError):
                square_neighbour_offsets(size)

    def test_slots_against_independent_distance_rule(self):
        coordinates = [(x,y) for y in range(1,6) for x in range(1,6) if (x,y) != (2,3)]
        x, y = zip(*coordinates)
        for size in (1,3,5):
            slots = build_square_neighbour_slots(x,y,size)
            self.assertEqual(slots.shape, (24,size*size-1))
            for index, (cx,cy) in enumerate(coordinates):
                expected = {j for j,(nx,ny) in enumerate(coordinates)
                            if j != index and max(abs(cx-nx),abs(cy-ny)) <= size//2}
                self.assertEqual(set(slots[index][slots[index]>=0]), expected)
        np.testing.assert_array_equal(build_moore_neighbour_slots(x,y), build_square_neighbour_slots(x,y,3))

    def test_cached_streamed_samples_and_mean_for_every_window(self):
        coordinates = [(x,y) for y in range(1,6) for x in range(1,6) if (x,y)!=(2,3)]
        spectra = np.asarray([[i+1,2,3] for i in range(24)], dtype=np.float64)
        for transpose in (False,True):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"tiny.h5"
                with h5py.File(path,"w") as h:
                    h["Data"] = spectra.T if transpose else spectra
                    h["mzArray"] = [100,101,102]
                    h["xLocation"] = [x for x,y in coordinates]
                    h["yLocation"] = [y for x,y in coordinates]
                for size in (1,3,5):
                    streamed = H5SpatialContextDataset(path,True,size)
                    cached = CachedH5SpatialContextDataset(path,True,size)
                    try:
                        for i,(cx,cy) in enumerate(coordinates):
                            sample = streamed[i]
                            for key in sample:
                                np.testing.assert_array_equal(sample[key],cached[i][key])
                            selected = [j for j,(x,y) in enumerate(coordinates)
                                        if j!=i and max(abs(cx-x),abs(cy-y))<=size//2]
                            expected = tic_normalize(spectra[selected]).mean(0) if selected else np.zeros(3)
                            np.testing.assert_allclose(sample["context"],expected,rtol=1e-6)
                    finally:
                        streamed.close()
                        cached.close()

    def test_masked_slots_have_no_gradient_and_empty_window_is_finite(self):
        for size in (1,3,5):
            slots = size*size-1
            neighbours = torch.rand(2,slots,3,requires_grad=True)
            mask = torch.zeros(2,slots,dtype=torch.bool)
            mask[:,::2] = True
            context,weights = UniformMeanNeighbourhood()(torch.ones(2,3),neighbours,mask)
            self.assertTrue(torch.isfinite(context).all())
            context[:,0].sum().backward()
            self.assertEqual(float(neighbours.grad[~mask].abs().sum()),0)
            self.assertEqual(float(weights[~mask].abs().sum()),0)

    def test_same_vae_initialization_parameter_count_and_zero_control(self):
        models = []
        for size,name in ((3,"uniform_mean"),(5,"uniform_mean"),(3,"zero_context")):
            torch.manual_seed(19)
            models.append(NeighbourhoodSpatialVAE(3,name,hidden_dim=4,latent_dim=2,window_size=size))
        counts = [sum(p.numel() for p in m.parameters()) for m in models]
        self.assertEqual(counts,[counts[0]]*3)
        for model in models[1:]:
            for name,tensor in models[0].vae.state_dict().items():
                torch.testing.assert_close(tensor,model.vae.state_dict()[name],rtol=0,atol=0)
        central = torch.rand(2,3)
        zero = models[2]
        first = zero.build_contextual_input(central,torch.rand(2,8,3),torch.ones(2,8,dtype=torch.bool))[0]
        second = zero.build_contextual_input(central,torch.rand(2,8,3)*100,torch.zeros(2,8,dtype=torch.bool))[0]
        torch.testing.assert_close(first,second,rtol=0,atol=0)
        torch.testing.assert_close(first,torch.cat((central,torch.zeros_like(central)),1))
        for model in models:
            model.eval()
            n = model.neighbour_slots
            output = model(central,torch.rand(2,n,3),torch.ones(2,n,dtype=torch.bool))
            self.assertEqual(output[0].shape,(2,3))
        self.assertNotIn("window_size",models[0].configuration())
        self.assertEqual(models[1].configuration()["window_size"],5)
        with self.assertRaises(ValueError):
            models[1].build_contextual_input(central,torch.rand(2,8,3),torch.ones(2,8,dtype=torch.bool))


if __name__ == "__main__":
    unittest.main()

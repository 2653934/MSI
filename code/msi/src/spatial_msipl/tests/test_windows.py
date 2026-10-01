"""Independent small-grid checks before submitting window experiments."""

import tempfile
import unittest
from pathlib import Path

import h5py
import numpy as np
import torch

from spatial_msipl.model import NeighbourhoodSpatialVAE
from spatial_msipl.neighbourhood import UniformMeanNeighbourhood
from spatial_msipl.preprocessing import (
    MOORE_OFFSETS, build_moore_neighbour_slots, build_square_neighbour_slots,
    square_neighbour_offsets, H5SpatialContextDataset, CachedH5SpatialContextDataset,
    tic_normalize,
)


class WindowTests(unittest.TestCase):
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

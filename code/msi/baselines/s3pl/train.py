import os
import random
import json
import time
import numpy as np

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, SubsetRandomSampler
from torchvision import transforms
import tqdm

from model.Attention3DConvAutoencoder import Attention3DConvAutoencoder
from test import test
from utils.data_source import build_patch_dataset
from utils.helpers import artifact_directories, normalize_spectra, resolve_data_paths

def train(config):   
    random_seed = config["random_seed"]
    random.seed(random_seed)
    np.random.seed(random_seed)
    torch.manual_seed(random_seed)
    torch.cuda.manual_seed(random_seed)
    use_cuda = torch.cuda.is_available()
    if use_cuda:
        torch.cuda.reset_peak_memory_stats()

    total_started_at = time.perf_counter()

    data_dir = config["data_dir"]
    directory_name = os.path.dirname(__file__)
    filepath, folderpath, dataname = resolve_data_paths(data_dir, directory_name)
    artifact_dirs = artifact_directories(config, directory_name)

    normalization = config.get("normalization", "reference_spatial_max")
    transform = transforms.Lambda(
        lambda x: torch.tensor(
            normalize_spectra(x, normalization), dtype=torch.float32
        )
    )
    training_dataset, mz_list = build_patch_dataset(
        filepath,
        config["spectral_patch_size"],
        transform,
    )
    num_input_channels = len(mz_list)
    
    dataset_size = len(training_dataset)
    indices = list(range(dataset_size))
    np.random.seed(random_seed)
    np.random.shuffle(indices)

    train_indices = indices
    test_indices = indices

    train_sampler = SubsetRandomSampler(train_indices)
    training_loader = DataLoader(training_dataset, batch_size=config["batch_size"], shuffle=False, drop_last=True, sampler=train_sampler)

    model = Attention3DConvAutoencoder(config["batch_size"], kernel_depth_d1=config["kernel_depth_d1"], kernel_depth_d2=config["kernel_depth_d2"], dropout=config["dropout"], spectral_patch_size=config["spectral_patch_size"])
    criterion = nn.MSELoss()

    if use_cuda:
        model = model.cuda()

    for path in artifact_dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    training_name = dataname + '_' + model._get_name() + '_' + str(config["n_epochs"]) + 'epochs_' + str(config["peaks_per_spectral_patch"]) + '_' + 'spectral_patch_size_' + str(config["spectral_patch_size"])
    if normalization != "reference_spatial_max":
        training_name += "_" + normalization
    path_to_weights = artifact_dirs["weights"] / (training_name + '.pt')

    pytorch_total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(path_to_weights)
    print('Samples in training folder: ' + str(len(training_dataset)))
    print('input channels = ' + str(num_input_channels))
    print('trainable parameters: ' + str(pytorch_total_params))
    print('GPU available: ' + str(use_cuda))
    print('normalization: ' + normalization)
    
    optimizer = optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=config["learning_rate"])

    train_started_at = time.perf_counter()
    train_history = []
    for epoch in range(config["n_epochs"]):
        model.train()

        with tqdm.tqdm(training_loader, unit="batch") as bar:
            for batch in bar:
                bar.set_description(f"Epoch {epoch}")
                optimizer.zero_grad()

                X_batch, _ = batch            
                y_batch = X_batch

                if use_cuda:
                    X_batch = X_batch.cuda()
                    y_batch = y_batch.cuda()

                y_pred, binary_mask, attention_mask = model(X_batch)

                loss = criterion(y_pred, y_batch)
                loss.backward()
                optimizer.step()

                bar.set_postfix_str(str(criterion._get_name()) + '=' + str(loss.item()))

        loss = loss.item()
        train_history.append(loss)
        
    training_seconds = time.perf_counter() - train_started_at
    torch.save(model.state_dict(), str(path_to_weights))

    config["training_name"] = training_name
    config["train_history"] = train_history
    
    with open(artifact_dirs["logs"] / (training_name + '.json'), 'w') as f:
        json.dump(config, f, indent=4)

    evaluation_started_at = time.perf_counter()
    mSCF1 = test(config, test_indices)
    evaluation_seconds = time.perf_counter() - evaluation_started_at
    total_seconds = time.perf_counter() - total_started_at

    runtime_metrics = {
        "dataset": dataname,
        "normalization": normalization,
        "device": torch.cuda.get_device_name(0) if use_cuda else "cpu",
        "training_seconds": training_seconds,
        "evaluation_seconds": evaluation_seconds,
        "total_seconds": total_seconds,
        "peak_gpu_memory_bytes": (
            int(torch.cuda.max_memory_allocated()) if use_cuda else None
        ),
    }
    resultfolder = artifact_dirs["results"] / training_name
    resultfolder.mkdir(parents=True, exist_ok=True)
    with open(resultfolder / "runtime_metrics.json", "w") as f:
        json.dump(runtime_metrics, f, indent=4)

    print("Runtime metrics:", runtime_metrics)
    return mSCF1

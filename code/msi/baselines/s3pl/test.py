import os
import numpy as np
import pandas as pd
import json

import torch
from torch.utils.data import DataLoader, SubsetRandomSampler
from torchvision import transforms
import tqdm
import m2aia as m2

from utils.PeakEvaluation import PeakEvaluation, PeakEvaluationMultipleClasses
from utils.helpers import (
    artifact_directories,
    check_for_labels,
    resolve_data_paths,
    tic_norm_spectra,
)
from model.Attention3DConvAutoencoder import Attention3DConvAutoencoder
import data_configs

def test(config, test_indices):
    training_name = config["training_name"]
    directory_name = os.path.dirname(__file__)
    artifact_dirs = artifact_directories(config, directory_name)
    model_path = artifact_dirs["weights"] / (training_name + '.pt')
    config_path = artifact_dirs["logs"] / (training_name + '.json')

    with open(config_path) as f:
        config = json.load(f)

    data_dir = config["data_dir"]
    filepath, folderpath, dataname = resolve_data_paths(data_dir, directory_name)

    spectral_patch_size = config["spectral_patch_size"]

    if type(config["number_peaks"]) is int:
        number_peaks = config["number_peaks"]
    else:
        number_peaks = data_configs.num_GT_peaks[dataname]

    if type(config["number_classes"]) is int:
        number_classes = config["number_classes"]
    else:
        number_classes = data_configs.number_classes[dataname]

    I = m2.ImzMLReader(filepath)
    mz_list = torch.tensor(I.GetXAxis())
    image_handles=[I]

    transform = transforms.Lambda(lambda x: torch.tensor(tic_norm_spectra(x), dtype=torch.float32))
    
    test_dataset = m2.SpectrumDataset(image_handles, shape=(config["spectral_patch_size"], config["spectral_patch_size"]), buffer_type="memory", transform_data=transform)
    test_sampler = SubsetRandomSampler(test_indices)
    test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False, drop_last=False, sampler=test_sampler)

    model = Attention3DConvAutoencoder(batchsize=1, kernel_depth_d1=config["kernel_depth_d1"], kernel_depth_d2=config["kernel_depth_d2"], dropout=config["dropout"], spectral_patch_size=config["spectral_patch_size"])
    model.load_state_dict(torch.load(str(model_path), map_location=torch.device('cpu')), strict=False)
    model.eval()

    use_cuda = torch.cuda.is_available()
    if use_cuda:
        model = model.cuda()
        mz_list = mz_list.cuda()

    peak_selection = {}
    with tqdm.tqdm(test_loader, unit="batch") as bar:
        for batch in bar:
            bar.set_description(f"Test")

            X_batch, _ = batch             
            y_batch = X_batch
            
            if use_cuda:
                X_batch = X_batch.cuda()
                y_batch = y_batch.cuda()

            y_pred, binary_mask, attention_mask = model(X_batch)

            attention_mask = attention_mask.squeeze()
            peaks_per_spectral_patch = config["peaks_per_spectral_patch"]
            _, indices = torch.topk(attention_mask, peaks_per_spectral_patch)
            indices = torch.unique(indices)
            picked_peaks = torch.index_select(mz_list, 0, indices)

            X_batch = X_batch.cpu().detach().numpy()
            y_batch = y_batch.cpu().detach().numpy()
            picked_peaks = picked_peaks.cpu().detach().numpy()
            attention_mask = attention_mask.cpu().detach().numpy()

            for mz_value in picked_peaks:
                if mz_value in peak_selection:
                    peak_selection[mz_value] += 1
                else:
                    peak_selection[mz_value] = 1

    sorted_peak_list = [mz_value for counts, mz_value in sorted(zip(list(peak_selection.values()), list(peak_selection.keys())))[::-1]]
    print('length of peak selection before cut-off = ' + str(len(sorted_peak_list)))
    peak_list = sorted_peak_list[:number_peaks]

    resultfolder = artifact_dirs["results"] / training_name
    filename_peak_evaluation = resultfolder / ('peak_evaluation_' + dataname + '_' + str(config["n_epochs"]) + 'epochs.txt')

    resultfolder.mkdir(parents=True, exist_ok=True)

    df = pd.DataFrame(peak_list)
    df.to_csv(resultfolder / ('picked_peaks_' + dataname + '_' + str(peaks_per_spectral_patch) + 'peaks_z_patchsize_' + str(spectral_patch_size) + '.csv'), index=False)

    mSCF1 = None
    if config["evaluate_peak_picking"]:
        check_for_labels(folderpath, dataname)
        evaluation_metrics = {
            "dataset": dataname,
            "number_picked_peaks": len(peak_list),
            "class_metrics": {},
            "mixed_f1": {},
        }

        with open(filename_peak_evaluation, 'a') as file:
            file.write(training_name + ':\n')
            file.write('number picked peaks = ' + str(len(peak_list)) + ', Recall/Precision/F1-Score/Correlation-Score\n')

        print(training_name + ':\n')
        print('number picked peaks = ' + str(len(peak_list)))

        for pcc_threshold in [0.3, 0.4, 0.5, 0.6]:
            evaluate_peaks = PeakEvaluationMultipleClasses(dataname, list(range(number_classes)), pcc_threshold, folderpath, peak_list, show_ion_images=False)
            class_metrics = evaluate_peaks.calculate_metrics()
            evaluation_metrics["class_metrics"][str(pcc_threshold)] = class_metrics

            with open(filename_peak_evaluation, 'a') as file:
                file.write('T_PCC = ' + str(pcc_threshold) + '\n')
            for class_name, metrics in class_metrics.items():
                recall = metrics["recall"]
                precision = metrics["precision"]
                F1 = metrics["F1"]

                with open(filename_peak_evaluation, 'a') as file:
                    file.write(str(class_name) + '\n')
                    file.write(str(round(F1,3)) + '\n')

        with open(filename_peak_evaluation, 'a') as file:
            file.write('\nF1-Score MixedClasses:\n')

        F1_scores_mixed = []
        for pcc_threshold in [0.3, 0.4, 0.5, 0.6]:      
            evaluate_peaks = PeakEvaluation(dataname, list(range(number_classes)), pcc_threshold, folderpath, peak_list, show_ion_images=False)
            recall, precision, F1 = evaluate_peaks.calculate_metrics()

            F1_scores_mixed.append(F1)
            evaluation_metrics["mixed_f1"][str(pcc_threshold)] = F1
            with open(filename_peak_evaluation, 'a') as file:
                file.write('F1 ' + str(pcc_threshold) + ' = ')
                file.write(str(round(F1,3)) + '\n')
            print('F1 ' + str(pcc_threshold) + ' = ' + str(round(F1,3)) + '\n')

        mSCF1 = float(round(np.mean(F1_scores_mixed),3))
        evaluation_metrics["mSCF1"] = mSCF1
        with open(filename_peak_evaluation, 'a') as file:
            file.write('mSCF1 = ' + str(mSCF1) + '\n')
        print('mSCF1 = ' + str(mSCF1) + '\n')

        with open(resultfolder / 'metrics.json', 'w') as file:
            json.dump(evaluation_metrics, file, indent=4)
    
    return mSCF1

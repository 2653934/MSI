# S3PL MassNet GBM reproduction status

## Status

This is an **interim partial reproduction**, not an exact reproduction of the paper's GBM result.

The released implementation is deterministic on our cluster and the MassNet HDF5 adapter, coordinates, neighbourhoods, masks, and evaluation procedure have passed their audits. However, the paper describes TIC normalization while the released S3PL helper performs spatial-maximum normalization. Neither interpretation reproduces the paper's collection result.

## Locked comparison

All p=3 experiments use the same eight sections, 10 epochs, batch size 16, learning rate 0.01, 256 spectral peaks, random seed 1, and PCC thresholds 0.3, 0.4, 0.5, and 0.6.

| Experiment | Role | Mean mSCF1 | Interpretation |
|---|---|---:|---|
| Released-code normalization, p=3 | Primary executable baseline | 0.316 | Paper-reported patch size with the normalization shipped in the released code |
| Paper-described TIC, p=3 | Sensitivity analysis | 0.289 | Correct per-spectrum TIC implementation; not treated as a replacement baseline |
| Released-code normalization, p=9 | Earlier transfer run | 0.346 | Useful context, but not the paper-reported GBM patch size |
| Paper | Published reference | 0.496 | Target reported for the eight-section GBM collection |

## Section-level comparison

| Section | Released code p=3 | Paper TIC p=3 | TIC change |
|---|---:|---:|---:|
| `GBM108_negative` | 0.664 | 0.291 | -0.373 |
| `GBM108_positive` | 0.033 | 0.267 | +0.234 |
| `GBM12_1` | 0.145 | 0.236 | +0.091 |
| `GBM12_2` | 0.512 | 0.292 | -0.220 |
| `GBM22_1` | 0.295 | 0.304 | +0.009 |
| `GBM22_2` | 0.339 | 0.347 | +0.008 |
| `GBM39_1` | 0.255 | 0.282 | +0.027 |
| `GBM39_2` | 0.281 | 0.291 | +0.010 |
| **Unweighted mean** | **0.316** | **0.289** | **-0.027** |

## Conclusions we can support

1. The `GBM108_positive` p=3 result is not random: an isolated repeat reproduced every scientific artifact exactly.
2. The HDF5 spatial adapter is not the cause: all 18,639 p=3 neighbour entries, centre spectra, and mask labels checked for `GBM108_positive` matched their source data.
3. Correct TIC normalization rescues part of the positive-section failure but substantially reduces `GBM108_negative` and `GBM12_2`; it is therefore not the missing global fix.
4. Results from the two normalizations must remain separate. Selecting the better result per section would invalidate the comparison.
5. The gap most likely lies in the data representation or preprocessing path between the public MassNet data and the imzML inputs used by the S3PL workflow, or in an unreleased experimental code revision.

## Original imzML lead

The official [IonMorphNet repository](https://github.com/CeMOS-IS/IonMorphNet), from the same research group and with overlapping S3PL authorship, links a Mannheim-hosted [GBM mSCF1 evaluation package](https://clousi.hs-mannheim.de/index.php/s/gnxRf6fXFQ7faFf). Its documented layout contains `.imzML`, `.ibd`, and mask files.

This package is a strong candidate for the representation used by the S3PL evaluation, but it must be inspected before being called the exact S3PL input. We need to compare its filenames, m/z axes, coordinates, spectra, masks, and checksums with the MassNet HDF5 data.

## Decision and next gate

- Use the released-code p=3 result (mean mSCF1 0.316) as the **primary executable baseline**.
- Report paper-TIC p=3 (mean mSCF1 0.289) as a **preprocessing sensitivity analysis**.
- Keep the paper value 0.496 as the **unreproduced published reference**.
- Do not launch another eight-section sweep yet.
- Next, download and inspect the official GBM imzML package. If it contains the expected eight sections, run only `GBM108_positive` and `GBM108_negative` through the original imzML path. Expand to all eight only if that two-section gate materially improves alignment without choosing settings per section.


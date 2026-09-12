# S3PL MassNet GBM reproduction status

## Status

This is an **interim partial reproduction**, not an exact reproduction of the paper's GBM result.

The released implementation is deterministic on our cluster and the MassNet HDF5 adapter, coordinates, neighbourhoods, masks, and evaluation procedure have passed their audits. The official imzML package also matches the HDF5 spectra, coordinates, and tissue regions. A two-section run through S3PL's original `m2aia` imzML loader reproduced the same high/low pattern as the HDF5 adapter. However, the paper describes TIC normalization while the released helper performs spatial-maximum normalization, and neither interpretation reproduces the paper's collection result.

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
2. The HDF5 spatial adapter is not the cause: all 18,639 p=3 neighbour entries, centre spectra, and mask labels checked for `GBM108_positive` matched their source data, and the original imzML loader produced nearly the same pilot scores.
3. Correct TIC normalization rescues part of the positive-section failure but substantially reduces `GBM108_negative` and `GBM12_2`; it is therefore not the missing global fix.
4. Results from the two normalizations must remain separate. Selecting the better result per section would invalidate the comparison.
5. The remaining gap is unlikely to be caused by HDF5 conversion, mask geometry, coordinate order, or the choice of HDF5 versus imzML loader. It more likely reflects an undocumented experimental detail, a difference between the released and experimental code, or an ambiguity in how the published aggregate was produced.

## Original imzML gate

The Mannheim-hosted GBM package linked by the official IonMorphNet repository contains the same eight sections in `.imzML`/`.ibd` form. All coordinate sets matched the HDF5 release, the tested spectra agreed to floating-point tolerance, and the official masks matched the reconstructed tissue classes at every measured pixel after recoding `1/2` to `0/1`.

| Section | HDF5 adapter | Original imzML loader | Change | Peak overlap at 4 decimals |
|---|---:|---:|---:|---:|
| `GBM108_positive` | 0.033 | 0.027 | -0.006 | 514/581 (88.5%) |
| `GBM108_negative` | 0.664 | 0.655 | -0.009 | 855/937 (91.2%) |

The threshold-level F1 changes were at most 0.011. Both imzML results decreased slightly, so the gate provides no justification for an eight-section rerun.

## Decision and next gate

- Use the released-code p=3 result (mean mSCF1 0.316) as the **primary executable baseline**.
- Report paper-TIC p=3 (mean mSCF1 0.289) as a **preprocessing sensitivity analysis**.
- Keep the paper value 0.496 as the **unreproduced published reference**.
- Do not launch an eight-section imzML sweep; the two-section gate failed its expansion criterion.
- Treat the released-code result as a valid executable baseline and clearly document the unresolved difference from the published aggregate rather than tuning sections individually.

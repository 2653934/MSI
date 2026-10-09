# Draft claim map

Only claims in the **allowed wording** column may be promoted into the report
without further evidence.

| Topic | Allowed wording | Required evidence | Prohibited shortcut |
|---|---|---|---|
| Pipeline quality | The evaluated VAE/GMM/IG package improves matched-budget mSCF1 over reproduced legacy msiPL on both collections. | Primary claim ledger and audited section results. | “IG alone caused the full improvement.” |
| Uniform context | Fixed 3×3 context improves the frozen single-seed CAC comparison but provides no consistent GBM benefit. | CAC validation and tuned-count GBM summaries. | “Spatial context universally improves peak selection.” |
| Spatial specificity | The tested controls do not establish a consistent benefit specifically attributable to correct local neighbourhood topology across both collections. | Window, zero/shuffled, attention and topology controls. | “Spatial information has no value in MSI.” |
| S3PL CAC | Matched-count S3PL is stronger on CAC under its native evaluated protocol. | CAC matched-count comparison and gap diagnostics. | “S3PL is intrinsically the better architecture.” |
| S3PL GBM | The executable ten-epoch GBM protocol is initialization-sensitive at section level; the paper-level score was not reproduced. | Three-seed section screen and longer-training diagnosis. | Selecting or presenting the best seed as the baseline. |
| Runtime | On three native 160TopL measurements, the VAE workflow used less wall time and slightly less sampled memory than S3PL. | Runtime stage table and measurement definitions. | “The VAE is universally faster” or “100 epochs beat 10 epochs at equal work.” |
| Biology | Selected-bin ion images have measured agreement with expert masks. | PCC/F1/mSCF1 audits. | Calling bins identified biomarkers or calling all non-correlated bins noise. |
| Statistical unit | Results are section-level and GBM sections are grouped within four patients. | Patient-grouped table/figure still to be produced. | Treating eight GBM sections as eight independent patients. |
| Peak representation | Evaluation ranks raw spectral bins at matched budgets; consolidated molecular-peak views are for interpretation. | Evaluation and consolidation code paths. | Using “peak” without stating which representation is meant. |


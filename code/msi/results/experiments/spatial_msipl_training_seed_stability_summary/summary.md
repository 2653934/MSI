# GBM108-positive training-seed stability

Three independently trained seeds were evaluated with the same GMM and attribution sampling seeds.
All methods selected the same 530 peaks, so variation reflects model training rather than peak budget.

## Mean ± sample SD across three seeds

| Variant | mSCF1 | GMM balanced accuracy | IG deletion faithfulness | Training hours | Peak GPU GiB |
|---|---:|---:|---:|---:|---:|
| Centre-only | 0.5120 ± 0.0179 | 0.8745 ± 0.0039 | 0.1120 ± 0.0147 | 11.4521 ± 0.3026 | 2.0466 ± 0.0000 |
| Uniform mean | 0.5250 ± 0.0132 | 0.8735 ± 0.0274 | 0.1224 ± 0.0255 | 11.5785 ± 0.2609 | 2.8984 ± 0.0000 |
| Corrected attention | 0.5454 ± 0.0188 | 0.8822 ± 0.0072 | 0.1179 ± 0.0099 | 11.1865 ± 0.0542 | 3.1956 ± 0.0000 |

## Interpretation

- Corrected attention minus uniform-mean mSCF1: +0.0204 on average; attention wins 3/3 seeds.
- Uniform-mean minus centre-only mSCF1: +0.0130 on average; uniform wins 2/3 seeds.
- With only three seeds, report the spread and per-seed values; do not treat this as a high-powered significance test.
- The predeclared attention decision also requires deletion faithfulness, not mSCF1 alone.

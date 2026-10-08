# S3PL GBM stability and native-runtime synthesis

All 24 GBM seed-screen configurations and all three native runtime workflows passed validation.

## Reporting decision

S3PL's 10-epoch GBM output is initialization-sensitive at section level. Report all declared seeds, section mean and sample SD, collection aggregation, and selected-peak overlap. Do not select the best seed. The collection mean is more stable than several individual sections, so show both levels.

The native runtime repetitions show the VAE workflow taking less wall time in all three measurements, with slightly lower sampled host and GPU memory. This is a workflow-cost result only: the methods use different architectures, objectives and epoch counts, so it is not an intrinsic efficiency or equal-work claim.

## Key values

- Collection means by initialization seed: seed_1=0.300, seed_2=0.306, seed_3=0.339.
- Sections with seed range at least 0.10: 6/8 (GBM108_positive, GBM108_negative, GBM12_2, GBM22_1, GBM39_1, GBM39_2).
- Runtime totals (S3PL / VAE seconds): 65630: 151.18 / 135.30; 65854: 173.90 / 121.63; 65855: 173.87 / 121.87.

See `summary.json` and the CSV files in this directory for exact provenance-linked values.

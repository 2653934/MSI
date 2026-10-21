`train.py` here is the current `baselines/s3pl/train.py` with only the `3624b56b`
hunks reversed (`git diff 3624b56b^ 3624b56b -- code/msi/baselines/s3pl/train.py`
applied with `patch -R`), made on 20 October 2026 for Investigation 21 Part C.
It is the released training path without the opt-in `--initialization_seed` /
`--sample_order_seed` flags; `tests/test_seed_flags_default.py` checks that the
current code with neither flag set behaves identically.

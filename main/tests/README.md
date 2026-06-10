# FundTrail tests

Two dependency-free suites (no pytest needed — they run anywhere):

```bash
cd main
python tests/smoke_test.py            # routes, auth routing, pages render, CSRF
python tests/test_access_control.py   # per-officer isolation, validators, backfill
```

Both exit non-zero on any failure. Run them **before and after every change**.

With pytest installed you can also run everything through one command:

```bash
pytest main/tests/pytest_suites.py
```

Each suite uses a throwaway temp database (`FUNDTRAIL_DATA_DIR`) and synthetic
data only — they never touch real case data.

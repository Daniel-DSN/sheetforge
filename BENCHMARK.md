# Benchmark — cleaning 50,000 rows

Synthetic, reproducible benchmark for the `clean` pipeline. The goal is to show
the order of magnitude on modest hardware, not to claim a record. Run it yourself:

```bash
PYTHONPATH=src python3 benchmarks/bench_clean.py --rows 50000 --runs 3
PYTHONPATH=src python3 benchmarks/bench_clean.py --rows 50000 --runs 3 --xlsx
```

## Dataset

- **50,000 rows × 10 columns** (name, email, phone, city, company, order id,
  order value, status, notes, signup date)
- deterministic generator (`seed = 42`); no client data
- dirty on purpose: 30% invalid emails, 75% phones reformatted, prices in
  `R$ 1.299,90` / `1,299.90` / `$ 9.99`, extra whitespace
- unique emails, so this exercises normalization and coercion rather than dedupe

## Environment

| | |
|---|---|
| CPU | Intel Core i3-2328M @ 2.20 GHz (2 cores / 4 threads) |
| RAM | 7.7 GiB |
| OS | Linux 7.0.0 x86_64 |
| Python | 3.12.3 |
| openpyxl | 3.1.5 |

## Results

In-process (`bench_clean.py`), median of 3 runs:

| Phase | Median | Range | Throughput |
|---|---:|---:|---:|
| Clean (pure rules → `Table`) | **2.78 s** | 2.60–3.08 s | ~18,000 rows/s |
| Write CSV | **0.76 s** | 0.75–1.41 s | ~65,000 rows/s |
| Write XLSX | **27.38 s** | 25.75–27.93 s | ~1,800 rows/s |

End-to-end CLI (`clean` with `--report` and `--summary`), median of 3 runs:
**4.99 s** (4.46 / 5.13 / 4.99 s). This includes reading the 6.3 MB CSV,
cleaning, writing the output CSV, the 15,070-row flagged report and the
markdown summary.

XLSX is slower because openpyxl serializes every cell as XML. For large
exports, CSV is the fast path; use XLSX for deliverables that need formatting.

## What changed to get here

The benchmark drove three low-risk optimizations (all covered by the existing
56 tests):

1. `normalize_text` has a fast path for already-clean strings — no regex call
   for the common case.
2. Numeric-column detection parses each numeric value once and reuses the
   result for coercion; text columns fail on the first non-numeric cell.
3. XLSX export uses openpyxl's write-only mode, and invalid email/phone flags
   are cached instead of re-validated in the reporting pass.

XLSX memory use for this dataset dropped from ~299 MB to ~138 MB.

Absolute timings vary with CPU and disk. The generator and commands above are
the reproducible part.

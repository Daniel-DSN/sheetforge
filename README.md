# SheetForge

[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](#testing)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Spreadsheet cleanup for messy client data: emails, phones, prices, duplicates.**

CSV / Excel / JSON in → cleaned file + flagged rows + markdown stats — then group, aggregate and merge.

```
messy.csv → sheetforge clean → out.xlsx (25 rows) + bad.csv (7 flagged) + summary.md
```

---

## Why this exists

Clients send "just a spreadsheet": doubled spaces, `ANA@Gmail.COM`, the same phone as
`(11) 99999-0001` *and* `+55 11 99999-0001` *and* `11999990001`, prices as `R$ 1.299,90`
next to `$1,299.90`, plus the same contact pasted three times. SheetForge does the boring half:

- **Clean** — trim/collapse text, normalize emails, fix BR phones, coerce prices, drop duplicates
- **Flag, never drop** — invalid rows stay in the output *and* are written to `bad.csv` with a reason
- **Report** — markdown stats: rows in/out, dupes removed, emails valid/invalid, phones fixed, columns coerced
- **Summarize** — group by any column with `sum` / `avg` / `count`, as a terminal table or `report.md`
- **Merge** — join two exports by email, dedupe, report overlap vs. new contacts
- **Exit code 2 when issues were found** — drop it into cron/CI

## Quick start

```bash
pip install -r requirements.txt          # openpyxl (plus pytest for the tests)
PYTHONPATH=src python -m sheetforge.cli --help
```

Run the bundled sample (30 messy rows):

```bash
# 1) clean → Excel + flagged rows + stats (exit 2: issues found)
python -m sheetforge.cli clean samples/messy.csv \
    -o demo/out.xlsx --report demo/bad.csv --summary demo/summary.md

# 2) revenue by city
python -m sheetforge.cli summarize demo/out.xlsx --by city --agg order_value --func sum

# 3) merge a second export and report overlap
python -m sheetforge.cli merge samples/messy.csv samples/messy_b.csv -o demo/merged.csv
```

One `make demo` runs all three and captures the transcripts into `demo/`.

## Example output

Real run — `clean` (exit code **2** = data issues found):

```
SheetForge 1.0.0 — clean samples/messy.csv
[stats] 30 rows in → 25 rows out · 5 dupes removed (3 exact + 2 email)
[stats] emails 19 valid / 6 invalid · phones 12 fixed · columns coerced: order_value
[ok] wrote 25 rows → demo/out.xlsx
[warn] 7 flagged rows → demo/bad.csv
[ok] summary → demo/summary.md
```

Real run — `summarize`:

```
group by city · sum(order_value) · 18 groups
city            rows  sum(order_value)
--------------  ----  ----------------
Rio de Janeiro     3           1229.74
São Paulo          3           1994.90
Belo Horizonte     2           1312.40
Curitiba           2            195.00
Florianópolis      2            229.09
...
TOTAL             25          16420.22
```

Real run — `merge`:

```
SheetForge 1.0.0 — merge samples/messy.csv + samples/messy_b.csv (key=email)
[stats] A=30 · B=10 · overlap=4 · new=6 · dupes removed=9
[ok] wrote 31 rows → demo/merged.csv
```

Full transcripts: [demo_run1.txt](demo/demo_run1.txt) ·
[demo_run2.txt](demo/demo_run2.txt) · [demo_merge.txt](demo/demo_merge.txt),
plus the generated `out.xlsx`, `bad.csv`, `summary.md`, `city_report.md`, `merged.csv`.

## Full CLI

| Command | Purpose |
|---------|---------|
| `clean INPUT -o OUT` | normalize rows → `.csv` / `.json` / `.xlsx` (suffix decides) |
| `--report bad.csv` | flagged rows with `row` + `reason` columns |
| `--summary summary.md` | markdown stats |
| `--key email` | duplicate key column (default `email`) |
| `summarize INPUT --by COL` | grouped count table |
| `--agg COL --func sum\|count\|avg` | aggregate values (unparseable values skipped) |
| `--out report.md` | write the table as markdown |
| `merge A B -o OUT [--key email]` | concatenate + dedupe + overlap/new report |

Exit codes: `0` success · `1` error · `2` data issues found (or CLI usage error).

### What `clean` does

| Rule | Example in → out |
|------|------------------|
| trim + collapse spaces | `"  Ana   Silva "` → `Ana Silva` |
| email lowercase + validate | `ANA@Gmail.COM` → `ana@gmail.com`; `john@@x` → **flagged, kept** |
| BR phone rules | `11999990001` / `+55 11 99999-0001` / `021 99999-0005` → `(11) 99999-0001` |
| international phones | `+1 415 555 0010` → `+14155550010` (kept with `+`) |
| price coercion | `R$ 1.299,90` · `1,299.90` · `$ 9.99` → `1299.9`, `1299.9`, `9.99` |
| duplicates | exact rows and same-key rows → first occurrence kept |
| encoding | `utf-8-sig` → `utf-8` → `latin-1` |

A lone `.` is always decimal (`1.299` → `1.299`); use the two-separator form
(`1.299,90` / `1,299.90`) for thousands.

## Architecture

```
src/sheetforge/
├── cli.py         argparse + commands (clean / summarize / merge)
├── clean.py       pure rules: text, emails, phones, numbers, dedupe, merge
├── summarize.py   grouping, aggregates, terminal + markdown tables
└── io.py          CSV / JSON / XLSX readers & writers, encoding fallback
```

- **Rules are pure** (table in → table + stats out) → unit-tested without touching disk
- **I/O is isolated** — one dispatch point picks the writer from the output suffix
- **Flagging never drops data** — bad rows survive in the output and are listed in `bad.csv`

## Testing

```bash
pip install pytest
PYTHONPATH=src python3 -m pytest -q
```

```
56 passed in 1.17s
```

Coverage: text/email/phone rules, price parsing (BR + US + currency), duplicate removal,
merge overlap math, grouping + aggregates, BOM/latin-1 decoding, CSV/JSON/XLSX round-trips
and CLI exit codes (0/1/2).

## Use cases

| Who | Uses SheetForge for |
|-----|--------------------|
| Freelancers | one-off client spreadsheet cleanup → deliverable Excel |
| Agencies | contact list from a CRM export → dedupe by email before mailing |
| E-commerce | price lists in mixed formats → numeric column for BI |
| Ops | scheduled `clean` → exit 2 alert when bad rows appear |

## License

MIT — see [LICENSE](LICENSE).

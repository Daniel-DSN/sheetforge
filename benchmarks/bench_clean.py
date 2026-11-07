#!/usr/bin/env python3
"""Reproducible clean/write benchmark for SheetForge.

Usage (from the repository root):

    PYTHONPATH=src python3 benchmarks/bench_clean.py --rows 50000 --runs 3
    PYTHONPATH=src python3 benchmarks/bench_clean.py --rows 50000 --xlsx

The input is generated deterministically (seed 42), so the same command
produces the same rows on every machine. Timings are wall-clock seconds.
"""

from __future__ import annotations

import argparse
import random
import statistics
import tempfile
import time
from pathlib import Path

from sheetforge.clean import clean_table
from sheetforge.io import Table, to_csv, to_xlsx

CITIES = [
    "São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre",
    "Recife", "Salvador", "Fortaleza", "Brasília", "Campinas",
]
FIRST = [
    "Ana", "João", "Maria", "Pedro", "Lucas", "Julia", "Rafael", "Beatriz",
    "Carlos", "Fernanda", "Bruno", "Camila", "Diego", "Larissa", "Marcos",
    "Patrícia",
]
LAST = [
    "Silva", "Souza", "Oliveira", "Santos", "Pereira", "Lima", "Costa",
    "Carvalho", "Almeida", "Ferreira", "Rodrigues", "Gomes",
]
COLUMNS = [
    "name", "email", "phone", "city", "company", "order_id", "order_value",
    "status", "notes", "signup_date",
]


def make_table(rows: int) -> Table:
    rng = random.Random(42)
    data: list[dict[str, object]] = []
    for i in range(rows):
        first = rng.choice(FIRST)
        last = rng.choice(LAST)
        name = f"  {first}   {last} " if i % 7 == 0 else f"{first} {last}"
        if i % 5 == 0:
            email = f"{first.lower()}.{last.lower()}{i}@@bad"
        else:
            email = f"{first.lower()}.{last.lower()}{i}@Gmail.COM"
        ddd = rng.choice(["11", "21", "31", "41", "51", "81", "71", "85", "61", "19"])
        if i % 4 == 0:
            phone = f"{ddd}9{rng.randint(10000000, 99999999)}"
        elif i % 4 == 1:
            phone = f"+55 {ddd} 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        elif i % 4 == 2:
            phone = f"({ddd}) 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        else:
            phone = f"{ddd} 9{rng.randint(1000, 9999)}-{rng.randint(1000, 9999)}"
        value = rng.choice([
            f"R$ {rng.randint(10, 9999)},{rng.randint(10, 99):02d}",
            f"{rng.randint(10, 9999)}.{rng.randint(10, 99):02d}",
            f"$ {rng.randint(10, 999)}.{rng.randint(10, 99):02d}",
        ])
        data.append({
            "name": name,
            "email": email,
            "phone": phone,
            "city": rng.choice(CITIES),
            "company": f"Empresa {rng.randint(1, 900)} Ltda",
            "order_id": f"ORD-{100000 + i}",
            "order_value": value,
            "status": rng.choice(["novo", "pago", "enviado", "cancelado"]),
            "notes": "  cliente   antigo " if i % 9 == 0 else "ok",
            "signup_date": f"2026-{rng.randint(1, 10):02d}-{rng.randint(1, 28):02d}",
        })
    return Table(columns=COLUMNS, rows=data)


def timed(fn):
    start = time.perf_counter()
    result = fn()
    return result, time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50_000)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--xlsx", action="store_true", help="also measure XLSX writing")
    args = parser.parse_args()

    table = make_table(args.rows)
    clean_times: list[float] = []
    csv_times: list[float] = []
    xlsx_times: list[float] = []

    with tempfile.TemporaryDirectory() as tmp:
        out_csv = Path(tmp) / "out.csv"
        out_xlsx = Path(tmp) / "out.xlsx"
        for run in range(1, args.runs + 1):
            result, clean_s = timed(lambda: clean_table(table))
            clean_times.append(clean_s)
            _, csv_s = timed(lambda: to_csv(result.table, out_csv))
            csv_times.append(csv_s)
            line = (
                f"run {run}: clean {clean_s:5.2f}s | csv {csv_s:5.2f}s"
            )
            if args.xlsx:
                _, xlsx_s = timed(lambda: to_xlsx(result.table, out_xlsx))
                xlsx_times.append(xlsx_s)
                line += f" | xlsx {xlsx_s:5.2f}s"
            print(line)

    def summary(name: str, values: list[float]) -> None:
        if not values:
            return
        median = statistics.median(values)
        print(
            f"{name}: median {median:.2f}s | min {min(values):.2f}s | "
            f"max {max(values):.2f}s | {args.rows / median:,.0f} rows/s"
        )

    print(f"\nrows: {args.rows:,} | columns: {len(COLUMNS)} | runs: {args.runs}")
    summary("clean", clean_times)
    summary("csv  ", csv_times)
    summary("xlsx ", xlsx_times)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

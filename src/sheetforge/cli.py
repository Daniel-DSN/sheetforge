"""SheetForge command-line interface.

Commands
--------
    sheetforge clean      INPUT -o OUT [--report bad.csv] [--summary summary.md]
    sheetforge summarize  INPUT --by COL [--agg COL --func sum|count|avg] [--out report.md]
    sheetforge merge      A B -o OUT [--key email]

Exit codes: 0 = success, 1 = error, 2 = data issues found (or CLI usage error).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .clean import clean_table, merge_tables, render_report, render_summary
from .io import read_table, write_rows, write_table
from .summarize import FUNCTIONS, format_table, summarize, to_markdown


def cmd_clean(args: argparse.Namespace) -> int:
    source = Path(args.input)
    output = Path(args.output)
    print(f"SheetForge {__version__} — clean {source}")
    table = read_table(source)
    result = clean_table(table, key=args.key)
    stats = result.stats
    write_table(result.table, output)

    print(
        f"[stats] {stats.rows_in} rows in → {stats.rows_out} rows out · "
        f"{stats.dupes_removed} dupes removed ({stats.exact_dupes} exact + "
        f"{stats.key_dupes} {args.key})"
    )
    print(
        f"[stats] emails {stats.emails_valid} valid / {stats.emails_invalid} invalid · "
        f"phones {stats.phones_fixed} fixed · "
        f"columns coerced: {', '.join(stats.columns_coerced) or 'none'}"
    )
    print(f"[ok] wrote {len(result.table)} rows → {output}")

    if args.report:
        header, rows = render_report(stats.flagged, table.columns)
        write_rows(rows, header, Path(args.report))
        print(f"[warn] {len(stats.flagged)} flagged rows → {args.report}")
    if args.summary:
        Path(args.summary).write_text(
            render_summary(stats, str(source), key=args.key), encoding="utf-8"
        )
        print(f"[ok] summary → {args.summary}")
    return 2 if stats.has_issues else 0


def cmd_summarize(args: argparse.Namespace) -> int:
    source = Path(args.input)
    print(f"SheetForge {__version__} — summarize {source} by {args.by}")
    table = read_table(source)
    if args.agg_func and not args.agg and args.agg_func != "count":
        print(f"[error] --func {args.agg_func} requires --agg", file=sys.stderr)
        return 1
    func = args.agg_func or ("sum" if args.agg else "count")
    result = summarize(table, args.by, agg=args.agg, func=func)
    if not result.groups:
        print("[warn] no rows to summarize", file=sys.stderr)
        return 0
    print(format_table(result))
    if args.out:
        Path(args.out).write_text(to_markdown(result), encoding="utf-8")
        print(f"[ok] report → {args.out}")
    return 0


def cmd_merge(args: argparse.Namespace) -> int:
    left, right = Path(args.a), Path(args.b)
    output = Path(args.output)
    print(f"SheetForge {__version__} — merge {left} + {right} (key={args.key})")
    merged = merge_tables(read_table(left), read_table(right), key=args.key)
    write_table(merged.table, output)
    print(
        f"[stats] A={merged.a_rows} · B={merged.b_rows} · overlap={merged.overlap} · "
        f"new={merged.new} · dupes removed={merged.dupes_removed}"
    )
    print(f"[ok] wrote {len(merged.table)} rows → {output}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sheetforge",
        description="Clean, summarize and merge messy spreadsheets (CSV/Excel/JSON).",
    )
    parser.add_argument("--version", action="version", version=f"sheetforge {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    c = sub.add_parser("clean", help="normalize rows and export CSV / JSON / XLSX")
    c.add_argument("input", help="input file (.csv / .tsv / .json / .xlsx)")
    c.add_argument("-o", "--output", required=True, help="output file (.csv / .json / .xlsx)")
    c.add_argument("--key", default="email", help="dedupe key column (default: email)")
    c.add_argument("--report", help="write flagged rows to this CSV")
    c.add_argument("--summary", help="write markdown stats to this file")
    c.set_defaults(func=cmd_clean)

    s = sub.add_parser("summarize", help="group rows and print a table")
    s.add_argument("input", help="input file (.csv / .tsv / .json / .xlsx)")
    s.add_argument("--by", required=True, help="column to group by")
    s.add_argument("--agg", help="column to aggregate")
    s.add_argument("--func", dest="agg_func", choices=list(FUNCTIONS),
                   help="sum | count | avg (default: sum)")
    s.add_argument("--out", help="write the table as markdown")
    s.set_defaults(func=cmd_summarize)

    m = sub.add_parser("merge", help="merge two files, dedupe and report overlap")
    m.add_argument("a", help="first input file")
    m.add_argument("b", help="second input file")
    m.add_argument("-o", "--output", required=True, help="output file (.csv / .json / .xlsx)")
    m.add_argument("--key", default="email", help="merge key column (default: email)")
    m.set_defaults(func=cmd_merge)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\n[abort] interrupted", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

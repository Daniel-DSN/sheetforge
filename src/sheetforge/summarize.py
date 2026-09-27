"""Grouped summaries: counts, sum / avg / count aggregates, text and Markdown tables."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .clean import normalize_text, parse_number
from .io import Table

FUNCTIONS = ("sum", "count", "avg")


@dataclass(slots=True)
class Group:
    key: str
    count: int
    value: float | None = None


@dataclass(slots=True)
class SummaryResult:
    by: str
    agg: str | None
    func: str | None
    groups: list[Group] = field(default_factory=list)
    total_rows: int = 0
    grand_total: float | None = None

    @property
    def label(self) -> str:
        if not self.agg:
            return "rows"
        return f"{self.func}({self.agg})"


def summarize(
    table: Table, by: str, agg: str | None = None, func: str | None = None
) -> SummaryResult:
    if func is not None and func not in FUNCTIONS:
        raise ValueError(f"unknown function: {func!r} (use {', '.join(FUNCTIONS)})")
    by_col = table.column(by)
    agg_col = table.column(agg) if agg else None
    if agg_col is None:
        if func not in (None, "count"):
            raise ValueError("--agg is required for sum and avg")
        func = None
    else:
        func = func or "sum"

    buckets: dict[str, dict[str, Any]] = {}
    for row in table.rows:
        key = normalize_text(row.get(by_col, "")) or "(blank)"
        bucket = buckets.setdefault(
            key, {"count": 0, "nonempty": 0, "total": 0.0, "numeric": 0}
        )
        bucket["count"] += 1
        if agg_col is not None:
            value = row.get(agg_col, "")
            if normalize_text(value):
                bucket["nonempty"] += 1
                parsed = parse_number(value)
                if parsed is not None:
                    bucket["total"] += parsed
                    bucket["numeric"] += 1

    result = SummaryResult(
        by=by_col, agg=agg_col, func=func if agg_col else None, total_rows=len(table.rows)
    )
    for key, bucket in buckets.items():
        value: float | None = None
        if agg_col is not None:
            if func == "sum":
                value = bucket["total"]
            elif func == "avg":
                value = bucket["total"] / bucket["numeric"] if bucket["numeric"] else None
            else:
                value = float(bucket["nonempty"])
        result.groups.append(Group(key=key, count=bucket["count"], value=value))
    result.groups.sort(key=lambda group: (-group.count, group.key))

    if agg_col is not None:
        totals = [g.value for g in result.groups if g.value is not None]
        if func == "avg":
            numeric_total = sum(b["total"] for b in buckets.values())
            numeric_count = sum(b["numeric"] for b in buckets.values())
            result.grand_total = numeric_total / numeric_count if numeric_count else None
        elif totals:
            result.grand_total = sum(totals)
    return result


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.2f}"


def format_table(result: SummaryResult) -> str:
    header = [result.by, "rows"]
    if result.agg:
        header.append(result.label)
    body = [[group.key, str(group.count)] + ([_fmt(group.value)] if result.agg else [])
            for group in result.groups]
    if result.agg:
        body.append(["TOTAL", str(result.total_rows), _fmt(result.grand_total)])
    widths = [
        max(len(header[i]), *(len(row[i]) for row in body)) if body else len(header[i])
        for i in range(len(header))
    ]
    lines = [
        f"group by {result.by}"
        + (f" · {result.func}({result.agg})" if result.agg else "")
        + f" · {len(result.groups)} groups"
    ]
    lines.append("  ".join(header[i].ljust(widths[i]) for i in range(len(header))))
    lines.append("  ".join("-" * widths[i] for i in range(len(header))))
    for row in body:
        cells = []
        for i, cell in enumerate(row):
            cells.append(cell.rjust(widths[i]) if i else cell.ljust(widths[i]))
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def to_markdown(result: SummaryResult) -> str:
    header = [result.by, "rows"] + ([result.label] if result.agg else [])
    lines = [
        f"Grouped by **{result.by}**"
        + (f" · agg **{result.agg}** · func **{result.func}**" if result.agg else "")
        + f" · {result.total_rows} rows",
        "",
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] + [":---:"] * (len(header) - 1)) + " |",
    ]
    for group in result.groups:
        cells = [group.key, str(group.count)] + ([_fmt(group.value)] if result.agg else [])
        lines.append("| " + " | ".join(cells) + " |")
    if result.agg:
        cells = ["**TOTAL**", f"**{result.total_rows}**", f"**{_fmt(result.grand_total)}**"]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)

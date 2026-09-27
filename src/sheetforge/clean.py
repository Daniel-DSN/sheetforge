"""Pure cleaning rules: text, emails, BR phones, numbers, duplicates.

Every function here is pure (data in → data out). File I/O lives in ``io.py``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .io import Table

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
SPACE_RE = re.compile(r"\s+")
CURRENCY_RE = re.compile(r"(US\$|R\$|USD|GBP|EUR|\$|£|€)\s*", re.IGNORECASE)
THOUSANDS_COMMA_RE = re.compile(r"^-?\d{1,3}(,\d{3})+$")
DECIMAL_COMMA_RE = re.compile(r"^-?\d+,\d{1,2}$")
INT_THOUSANDS_COMMA_RE = re.compile(r"^-?\d+,\d{3}$")
PHONE_COLUMNS = {"phone", "telefone", "celular", "mobile"}
EMAIL_COLUMNS = {"email", "e-mail", "mail"}


@dataclass(slots=True)
class EmailResult:
    value: str
    valid: bool


@dataclass(slots=True)
class PhoneResult:
    value: str
    fixed: bool
    valid: bool


@dataclass(slots=True)
class Flag:
    row: int
    reason: str
    data: dict[str, Any]


@dataclass(slots=True)
class CleanStats:
    rows_in: int = 0
    rows_out: int = 0
    exact_dupes: int = 0
    key_dupes: int = 0
    emails_valid: int = 0
    emails_invalid: int = 0
    phones_fixed: int = 0
    phones_invalid: int = 0
    columns_coerced: list[str] = field(default_factory=list)
    flagged: list[Flag] = field(default_factory=list)

    @property
    def dupes_removed(self) -> int:
        return self.exact_dupes + self.key_dupes

    @property
    def has_issues(self) -> bool:
        return bool(self.flagged)


@dataclass(slots=True)
class CleanResult:
    table: Table
    stats: CleanStats


@dataclass(slots=True)
class MergeResult:
    table: Table
    a_rows: int
    b_rows: int
    overlap: int
    new: int
    dupes_removed: int


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return SPACE_RE.sub(" ", str(value)).strip()


def normalize_email(value: Any) -> EmailResult:
    text = normalize_text(value).lower()
    if not text:
        return EmailResult("", False)
    return EmailResult(text, bool(EMAIL_RE.match(text)))


def normalize_phone(value: Any) -> PhoneResult:
    original = normalize_text(value)
    if not original:
        return PhoneResult("", False, True)
    digits = re.sub(r"\D", "", original)
    if original.startswith("+"):
        if digits.startswith("55") and len(digits) in (12, 13):
            national = digits[2:]
        else:
            formatted = f"+{digits}"
            return PhoneResult(formatted, formatted != original, len(digits) >= 8)
    else:
        national = digits
        if national.startswith("0") and len(national) - 1 in (10, 11):
            national = national[1:]
    if len(national) == 11 and national[2] == "9":
        formatted = f"({national[:2]}) {national[2:7]}-{national[7:]}"
    elif len(national) == 10:
        formatted = f"({national[:2]}) {national[2:6]}-{national[6:]}"
    else:
        return PhoneResult(original, False, False)
    return PhoneResult(formatted, formatted != original, True)


def parse_number(value: Any) -> float | None:
    """Parse ``1.299,90`` / ``1,299.90`` / ``R$ 50`` / ``$ 9.99`` into a float."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = normalize_text(value)
    if not text:
        return None
    text = CURRENCY_RE.sub("", text)
    text = text.replace(" ", "")
    if not text:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    if text.startswith("-"):
        negative = True
        text = text[1:]
    has_dot = "." in text
    has_comma = "," in text
    if has_dot and has_comma:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif has_comma:
        if THOUSANDS_COMMA_RE.match(text) or INT_THOUSANDS_COMMA_RE.match(text):
            text = text.replace(",", "")
        elif DECIMAL_COMMA_RE.match(text):
            text = text.replace(",", ".")
        else:
            return None
    if not re.fullmatch(r"\d*\.?\d*", text) or text in {"", "."}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def is_numeric_column(rows: list[dict[str, Any]], column: str) -> bool:
    values = [row.get(column, "") for row in rows]
    filled = [value for value in values if normalize_text(value)]
    if not filled:
        return False
    return all(parse_number(value) is not None for value in filled)


def _find_column(columns: list[str], candidates: set[str]) -> str | None:
    for column in columns:
        if column.strip().lower() in candidates:
            return column
    return None


def dedupe(
    rows: list[tuple[int, dict[str, Any]]], columns: list[str], key: str | None
) -> tuple[list[tuple[int, dict[str, Any]]], int, int]:
    kept: list[tuple[int, dict[str, Any]]] = []
    seen_exact: set[tuple[Any, ...]] = set()
    seen_keys: set[str] = set()
    exact_removed = 0
    key_removed = 0
    for index, row in rows:
        fingerprint = tuple(row.get(col, "") for col in columns)
        if fingerprint in seen_exact:
            exact_removed += 1
            continue
        seen_exact.add(fingerprint)
        if key:
            k = normalize_text(row.get(key, "")).lower()
            if k:
                if k in seen_keys:
                    key_removed += 1
                    continue
                seen_keys.add(k)
        kept.append((index, row))
    return kept, exact_removed, key_removed


def clean_table(table: Table, key: str = "email") -> CleanResult:
    columns = list(table.columns)
    originals = [dict(row) for row in table.rows]
    stats = CleanStats(rows_in=len(table.rows))
    email_col = _find_column(columns, EMAIL_COLUMNS)
    phone_col = _find_column(columns, PHONE_COLUMNS)

    rows: list[tuple[int, dict[str, Any]]] = []
    for index, raw in enumerate(table.rows, start=1):
        row = {col: normalize_text(raw.get(col, "")) for col in columns}
        if email_col:
            row[email_col] = normalize_email(row[email_col]).value
        rows.append((index, row))

    key_col = None
    try:
        key_col = table.column(key)
    except ValueError:
        pass
    kept, exact_removed, key_removed = dedupe(rows, columns, key_col)
    stats.exact_dupes = exact_removed
    stats.key_dupes = key_removed
    stats.rows_out = len(kept)

    protected = {col for col in (email_col, phone_col) if col}

    for _, row in kept:
        if email_col and row[email_col]:
            if EMAIL_RE.match(row[email_col]):
                stats.emails_valid += 1
            else:
                stats.emails_invalid += 1
        if phone_col and row[phone_col]:
            result = normalize_phone(row[phone_col])
            row[phone_col] = result.value
            if result.fixed:
                stats.phones_fixed += 1
            if not result.valid:
                stats.phones_invalid += 1

    kept_rows = [row for _, row in kept]
    coerced = [
        col for col in columns if col not in protected and is_numeric_column(kept_rows, col)
    ]
    for row in kept_rows:
        for col in coerced:
            parsed = parse_number(row.get(col, ""))
            if parsed is not None:
                row[col] = parsed
    stats.columns_coerced = coerced

    for index, row in kept:
        reasons: list[str] = []
        if email_col and row[email_col] and not EMAIL_RE.match(row[email_col]):
            reasons.append(f"invalid email: {row[email_col]}")
        if phone_col and row[phone_col] and not normalize_phone(row[phone_col]).valid:
            reasons.append(f"invalid phone: {row[phone_col]}")
        if reasons:
            stats.flagged.append(
                Flag(row=index, reason="; ".join(reasons), data=dict(originals[index - 1]))
            )

    return CleanResult(table=Table(columns=columns, rows=kept_rows), stats=stats)


def merge_tables(left: Table, right: Table, key: str = "email") -> MergeResult:
    columns = list(left.columns)
    key_col = left.column(key)
    right_columns = {col.lower(): col for col in right.columns}
    if key_col.lower() not in right_columns:
        raise ValueError(
            f"key column {key!r} not found in input B (available: {', '.join(right.columns)})"
        )

    left_rows = [{col: normalize_text(row.get(col, "")) for col in columns} for row in left.rows]
    right_rows: list[dict[str, Any]] = []
    for row in right.rows:
        mapped: dict[str, Any] = {}
        for col in columns:
            source = right_columns.get(col.lower())
            mapped[col] = normalize_text(row.get(source, "")) if source else ""
        if key_col:
            mapped[key_col] = mapped[key_col].lower()
        right_rows.append(mapped)

    if key_col:
        for row in left_rows:
            row[key_col] = row[key_col].lower()

    keys_left = {
        normalize_text(row.get(key_col, "")).lower()
        for row in left_rows
        if key_col and normalize_text(row.get(key_col, ""))
    }
    keys_right = {
        normalize_text(row.get(key_col, "")).lower()
        for row in right_rows
        if key_col and normalize_text(row.get(key_col, ""))
    }

    combined = [(i, row) for i, row in enumerate(left_rows, start=1)]
    combined += [(len(left_rows) + i, row) for i, row in enumerate(right_rows, start=1)]
    kept, exact_removed, key_removed = dedupe(combined, columns, key_col)

    return MergeResult(
        table=Table(columns=columns, rows=[row for _, row in kept]),
        a_rows=len(left.rows),
        b_rows=len(right.rows),
        overlap=len(keys_left & keys_right),
        new=len(keys_right - keys_left),
        dupes_removed=exact_removed + key_removed,
    )


def render_summary(stats: CleanStats, source: str, key: str = "email") -> str:
    coerced = ", ".join(stats.columns_coerced) if stats.columns_coerced else "none"
    lines = [
        "# SheetForge clean report",
        "",
        f"Input: `{source}`",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Rows in | {stats.rows_in} |",
        f"| Rows out | {stats.rows_out} |",
        f"| Exact duplicates removed | {stats.exact_dupes} |",
        f"| {key} duplicates removed | {stats.key_dupes} |",
        f"| Emails valid | {stats.emails_valid} |",
        f"| Emails invalid | {stats.emails_invalid} |",
        f"| Phones fixed | {stats.phones_fixed} |",
        f"| Phones invalid | {stats.phones_invalid} |",
        f"| Columns coerced to number | {coerced} |",
        f"| Flagged rows | {len(stats.flagged)} |",
    ]
    if stats.flagged:
        lines += [
            "",
            "## Flagged rows",
            "",
            "| row | reason |",
            "|-----|--------|",
        ]
        for flag in stats.flagged:
            lines.append(f"| {flag.row} | {flag.reason} |")
    lines.append("")
    return "\n".join(lines)


def render_report(flags: list[Flag], columns: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    header = ["row", *columns, "reason"]
    rows = [
        {"row": flag.row, **flag.data, "reason": flag.reason}
        for flag in flags
    ]
    return header, rows

"""Cleaning rules — pure functions, no file I/O."""

from pathlib import Path

import pytest

from sheetforge.clean import (
    clean_table,
    merge_tables,
    normalize_email,
    normalize_phone,
    normalize_text,
    parse_number,
    render_report,
    render_summary,
)
from sheetforge.io import Table


def _table() -> Table:
    return Table(
        columns=["name", "email", "phone", "city", "order_value"],
        rows=[
            {"name": "  Ana   Silva ", "email": " ANA@Gmail.COM ", "phone": "11999990001",
             "city": "São Paulo", "order_value": "R$ 1.299,90"},
            {"name": "Ana Silva", "email": "ana@gmail.com", "phone": "(11) 99999-0001",
             "city": "São Paulo", "order_value": "$3.99"},
            {"name": "Bruno Costa", "email": "bruno@@x", "phone": "99999-0002",
             "city": "Rio", "order_value": "1,299.90"},
            {"name": "Carla Dias", "email": "carla@x.com", "phone": "+44 20 7946 0021",
             "city": "London", "order_value": "£ 42.00"},
            {"name": "Bruno Costa", "email": "bruno@@x", "phone": "99999-0002",
             "city": "Rio", "order_value": "1,299.90"},
        ],
    )


def test_normalize_text_trims_and_collapses():
    assert normalize_text("  Ana   Silva \n") == "Ana Silva"
    assert normalize_text(None) == ""


def test_email_lowercased_and_validated():
    result = normalize_email(" ANA.SILVA@Gmail.COM ")
    assert result.value == "ana.silva@gmail.com"
    assert result.valid
    assert normalize_email("john@@x").valid is False
    assert normalize_email("").valid is False


def test_invalid_email_is_flagged_not_dropped():
    result = clean_table(_table())
    emails = [row["email"] for row in result.table.rows]
    assert "bruno@@x" in emails
    assert result.stats.emails_invalid == 1
    assert result.stats.emails_valid == 2
    reasons = [flag.reason for flag in result.stats.flagged]
    assert any("invalid email: bruno@@x" in reason for reason in reasons)


def test_phone_bare_digits_become_mobile_format():
    result = normalize_phone("11999990001")
    assert result.value == "(11) 99999-0001"
    assert result.valid and result.fixed


def test_phone_already_formatted_is_untouched():
    result = normalize_phone("(11) 99999-0001")
    assert result.value == "(11) 99999-0001"
    assert result.valid and not result.fixed


def test_phone_plus55_and_trunk_zero():
    assert normalize_phone("+55 11 99999-0002").value == "(11) 99999-0002"
    assert normalize_phone("021 99999-0005").value == "(21) 99999-0005"
    assert normalize_phone("85 3333-0015").value == "(85) 3333-0015"


def test_phone_international_kept_with_plus():
    result = normalize_phone("+1 415 555 0010")
    assert result.value == "+14155550010"
    assert result.valid and result.fixed
    assert normalize_phone("+44 20 7946 0021").value == "+442079460021"


def test_phone_invalid_is_reported_not_rewritten():
    result = normalize_phone("99999-0017")
    assert result.value == "99999-0017"
    assert result.valid is False
    assert normalize_phone("12ab").valid is False


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("R$ 1.299,90", 1299.90),
        ("1,299.90", 1299.90),
        ("$3.99", 3.99),
        ("$ 9.99", 9.99),
        ("R$ 50", 50.0),
        ("£ 42.00", 42.0),
        ("1299.90", 1299.9),
        ("1,299", 1299.0),
        ("1,5", 1.5),
        ("-12,50", -12.5),
        (45.0, 45.0),
    ],
)
def test_parse_number_formats(raw, expected):
    assert parse_number(raw) == pytest.approx(expected)


@pytest.mark.parametrize("raw", ["", "abc", "12..34", "bad email.com", None, True])
def test_parse_number_rejects(raw):
    assert parse_number(raw) is None


def test_numeric_column_coerced_to_float():
    result = clean_table(_table())
    assert result.stats.columns_coerced == ["order_value"]
    values = [row["order_value"] for row in result.table.rows]
    assert all(isinstance(value, float) for value in values)
    assert values[0] == pytest.approx(1299.90)


def test_exact_and_email_key_duplicates_removed():
    result = clean_table(_table())
    stats = result.stats
    assert stats.rows_in == 5
    assert stats.rows_out == 3
    assert stats.exact_dupes == 1
    assert stats.key_dupes == 1
    assert stats.dupes_removed == 2
    emails = [row["email"] for row in result.table.rows]
    assert emails.count("ana@gmail.com") == 1
    assert result.table.rows[0]["name"] == "Ana Silva"


def test_clean_stats_and_summary_markdown():
    result = clean_table(_table())
    stats = result.stats
    assert stats.phones_fixed >= 1
    assert stats.phones_invalid == 1
    report = render_summary(stats, "messy.csv")
    assert "| Rows in | 5 |" in report
    assert "| Rows out | 3 |" in report
    assert "| Emails invalid | 1 |" in report
    assert "## Flagged rows" in report
    header, rows = render_report(stats.flagged, result.table.columns)
    assert header[0] == "row" and header[-1] == "reason"
    assert rows[0]["row"] in {2, 3}


def test_missing_key_column_still_cleans():
    table = Table(columns=["name"], rows=[{"name": " Ana "}, {"name": "Ana"}])
    result = clean_table(table)
    assert result.stats.rows_out == 1
    assert result.stats.key_dupes == 0


def test_merge_tables_reports_overlap_and_new():
    left = Table(
        columns=["name", "email"],
        rows=[
            {"name": "Ana", "email": "ana@x.com"},
            {"name": "Bruno", "email": "bruno@x.com"},
        ],
    )
    right = Table(
        columns=["name", "email"],
        rows=[
            {"name": "Carla", "email": "carla@x.com"},
            {"name": "Ana clone", "email": "ANA@X.COM"},
            {"name": "Diego", "email": "diego@x.com"},
        ],
    )
    merged = merge_tables(left, right, key="email")
    assert merged.a_rows == 2
    assert merged.b_rows == 3
    assert merged.overlap == 1
    assert merged.new == 2
    assert merged.dupes_removed == 1
    assert len(merged.table) == 4
    emails = [row["email"] for row in merged.table.rows]
    assert emails.count("ana@x.com") == 1
    assert "carla@x.com" in emails and "diego@x.com" in emails


def test_merge_missing_key_column_raises():
    left = Table(columns=["name"], rows=[{"name": "Ana"}])
    right = Table(columns=["name"], rows=[{"name": "Ana"}])
    with pytest.raises(ValueError, match="unknown column"):
        merge_tables(left, right, key="email")

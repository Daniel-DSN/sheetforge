"""Grouped summaries — counts, aggregates, text and Markdown rendering."""

import pytest

from sheetforge.io import Table
from sheetforge.summarize import format_table, summarize, to_markdown


def _table() -> Table:
    return Table(
        columns=["city", "order_value", "email"],
        rows=[
            {"city": "São Paulo", "order_value": "R$ 100,00", "email": "a@x.com"},
            {"city": "São Paulo", "order_value": "R$ 50,00", "email": "b@x.com"},
            {"city": "Rio", "order_value": "R$ 30,50", "email": "c@x.com"},
            {"city": "Rio", "order_value": "n/a", "email": "d@x.com"},
            {"city": "", "order_value": "R$ 10,00", "email": "e@x.com"},
        ],
    )


def test_group_counts_sorted_by_size():
    result = summarize(_table(), "city")
    assert result.total_rows == 5
    assert result.groups[0].key == "Rio" and result.groups[0].count == 2
    assert result.groups[1].key == "São Paulo" and result.groups[1].count == 2
    assert result.groups[-1].key == "(blank)"


def test_sum_agg_skips_unparseable_values():
    result = summarize(_table(), "city", agg="order_value", func="sum")
    by_key = {group.key: group.value for group in result.groups}
    assert by_key["São Paulo"] == pytest.approx(150.0)
    assert by_key["Rio"] == pytest.approx(30.5)
    assert result.grand_total == pytest.approx(190.5)


def test_avg_agg_ignores_non_numeric():
    result = summarize(_table(), "city", agg="order_value", func="avg")
    by_key = {group.key: group.value for group in result.groups}
    assert by_key["São Paulo"] == pytest.approx(75.0)
    assert by_key["Rio"] == pytest.approx(30.5)


def test_count_agg_counts_non_empty_values():
    result = summarize(_table(), "city", agg="order_value", func="count")
    by_key = {group.key: group.value for group in result.groups}
    assert by_key["Rio"] == 2
    assert by_key["São Paulo"] == 2


def test_format_table_has_header_and_total():
    result = summarize(_table(), "city", agg="order_value", func="sum")
    text = format_table(result)
    lines = text.splitlines()
    assert "group by city · sum(order_value)" in lines[0]
    assert "city" in lines[1] and "rows" in lines[1]
    assert "São Paulo" in text and "150.00" in text
    assert "TOTAL" in text and "190.50" in text


def test_to_markdown_is_a_table():
    result = summarize(_table(), "city", agg="order_value", func="avg")
    text = to_markdown(result)
    assert text.startswith("Grouped by **city**")
    assert "| city | rows | avg(order_value) |" in text
    assert "| **TOTAL** |" in text


def test_unknown_column_raises():
    with pytest.raises(ValueError, match="unknown column"):
        summarize(_table(), "nope")
    with pytest.raises(ValueError, match="unknown column"):
        summarize(_table(), "city", agg="nope")


def test_unknown_function_raises():
    with pytest.raises(ValueError, match="unknown function"):
        summarize(_table(), "city", agg="order_value", func="median")


def test_sum_without_agg_raises():
    with pytest.raises(ValueError, match="--agg is required"):
        summarize(_table(), "city", func="sum")

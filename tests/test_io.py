"""File I/O and CLI — real files written to tmp_path."""

import csv
import io
import json
from pathlib import Path

import pytest

from sheetforge.cli import main
from sheetforge.io import Table, read_table, to_csv, to_json, to_xlsx, write_table


def _csv(path: Path, header: list[str], rows: list[list[str]]) -> Path:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    path.write_text(buffer.getvalue(), encoding="utf-8")
    return path


def _messy(path: Path) -> Path:
    return _csv(
        path,
        ["name", "email", "phone", "city", "order_value"],
        [
            ["  Ana  Silva", "ANA@X.COM", "11999990001", "São Paulo", "R$ 10,00"],
            ["Ana Silva", "ana@x.com", "(11) 99999-0001", "São Paulo", "R$ 10,00"],
            ["Bruno", "bad@@mail", "99999-0002", "Rio", "$3.99"],
            ["Carla", "carla@x.com", "+44 20 7946 0001", "London", "1,299.90"],
        ],
    )


def test_read_csv_with_utf8_bom(tmp_path: Path):
    path = tmp_path / "bom.csv"
    path.write_bytes(b"\xef\xbb\xbf" + "name,email\nAna,a@x.com\n".encode("utf-8"))
    table = read_table(path)
    assert table.columns[0] == "name"
    assert table.rows[0]["email"] == "a@x.com"


def test_read_latin1_fallback(tmp_path: Path):
    path = tmp_path / "latin.csv"
    path.write_bytes("name,city\nJosé,Belo Horizonte\n".encode("latin-1"))
    table = read_table(path)
    assert table.rows[0]["name"] == "José"


def test_read_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="input file not found"):
        read_table(tmp_path / "nope.csv")


def test_csv_roundtrip(tmp_path: Path):
    table = Table(columns=["name", "price"], rows=[{"name": "Ana", "price": 12.5}])
    out = to_csv(table, tmp_path / "out.csv")
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "name,price"
    assert lines[1] == "Ana,12.5"
    assert read_table(out).rows[0]["price"] == "12.5"


def test_json_roundtrip(tmp_path: Path):
    table = Table(columns=["name", "price"], rows=[{"name": "Ana", "price": 12.5}])
    out = to_json(table, tmp_path / "out.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload == [{"name": "Ana", "price": 12.5}]
    assert read_table(out).rows[0]["price"] == 12.5


def test_xlsx_roundtrip(tmp_path: Path):
    table = Table(columns=["name", "price"], rows=[{"name": "Ana", "price": 12.5}])
    out = to_xlsx(table, tmp_path / "out.xlsx")
    assert out.exists() and out.stat().st_size > 0
    back = read_table(out)
    assert back.columns == ["name", "price"]
    assert back.rows[0]["name"] == "Ana"
    assert back.rows[0]["price"] == 12.5
    from openpyxl import load_workbook

    sheet = load_workbook(out).active
    assert sheet["A1"].font.bold
    assert sheet.freeze_panes == "A2"


def test_read_json_array(tmp_path: Path):
    path = tmp_path / "in.json"
    path.write_text(json.dumps([{"name": "Ana", "city": "SP"}]), encoding="utf-8")
    table = read_table(path)
    assert table.columns == ["name", "city"]
    assert len(table) == 1


def test_unsupported_suffix(tmp_path: Path):
    table = Table(columns=["a"], rows=[{"a": "1"}])
    with pytest.raises(ValueError, match="unsupported format"):
        write_table(table, tmp_path / "out.txt")


def test_cli_clean_flags_and_exits_2(tmp_path: Path, capsys):
    src = _messy(tmp_path / "in.csv")
    out = tmp_path / "out.csv"
    report = tmp_path / "bad.csv"
    summary = tmp_path / "summary.md"
    code = main(
        ["clean", str(src), "-o", str(out), "--report", str(report),
         "--summary", str(summary)]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "4 rows in → 3 rows out" in captured.out
    assert "1 dupes removed (0 exact + 1 email)" in captured.out
    assert "emails 2 valid / 1 invalid" in captured.out
    assert "columns coerced: order_value" in captured.out
    assert out.exists()
    report_text = report.read_text(encoding="utf-8")
    assert "invalid email: bad@@mail" in report_text
    assert "invalid phone: 99999-0002" in report_text
    summary_text = summary.read_text(encoding="utf-8")
    assert "| Rows in | 4 |" in summary_text
    assert "| Rows out | 3 |" in summary_text


def test_cli_clean_clean_input_exits_0(tmp_path: Path):
    src = _csv(
        tmp_path / "ok.csv",
        ["name", "email", "order_value"],
        [["Ana", "ana@x.com", "R$ 10,00"]],
    )
    out = tmp_path / "out.csv"
    assert main(["clean", str(src), "-o", str(out)]) == 0
    table = read_table(out)
    assert float(table.rows[0]["order_value"]) == 10.0


def test_cli_clean_rejects_unknown_output_format(tmp_path: Path, capsys):
    src = _messy(tmp_path / "in.csv")
    code = main(["clean", str(src), "-o", str(tmp_path / "out.txt")])
    assert code == 1
    assert "unsupported format" in capsys.readouterr().err


def test_cli_missing_input_exits_1(tmp_path: Path, capsys):
    code = main(["clean", str(tmp_path / "nope.csv"), "-o", str(tmp_path / "o.csv")])
    assert code == 1
    assert "input file not found" in capsys.readouterr().err


def test_cli_summarize_prints_table_and_report(tmp_path: Path, capsys):
    src = _csv(
        tmp_path / "sales.csv",
        ["city", "order_value"],
        [["SP", "R$ 10,00"], ["SP", "R$ 5,50"], ["Rio", "2,00"]],
    )
    report = tmp_path / "report.md"
    code = main(
        ["summarize", str(src), "--by", "city", "--agg", "order_value",
         "--func", "sum", "--out", str(report)]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "group by city · sum(order_value)" in captured.out
    assert "TOTAL" in captured.out
    text = report.read_text(encoding="utf-8")
    assert "| city | rows | sum(order_value) |" in text
    assert "15.50" in text


def test_cli_summarize_func_requires_agg(tmp_path: Path, capsys):
    src = _csv(tmp_path / "in.csv", ["city"], [["SP"]])
    code = main(["summarize", str(src), "--by", "city", "--func", "sum"])
    assert code == 1
    assert "--func sum requires --agg" in capsys.readouterr().err


def test_cli_merge_reports_overlap(tmp_path: Path, capsys):
    left = _csv(tmp_path / "a.csv", ["name", "email"],
                [["Ana", "ana@x.com"], ["Bruno", "bruno@x.com"]])
    right = _csv(tmp_path / "b.csv", ["name", "email"],
                 [["Ana clone", "ANA@X.COM"], ["Carla", "carla@x.com"]])
    out = tmp_path / "merged.csv"
    code = main(["merge", str(left), str(right), "-o", str(out), "--key", "email"])
    captured = capsys.readouterr()
    assert code == 0
    assert "A=2 · B=2 · overlap=1 · new=1" in captured.out
    assert "dupes removed=1" in captured.out
    table = read_table(out)
    assert [row["email"] for row in table.rows] == ["ana@x.com", "bruno@x.com", "carla@x.com"]


def test_cli_merge_missing_key_in_b_exits_1(tmp_path: Path, capsys):
    left = _csv(tmp_path / "a.csv", ["name", "email"], [["Ana", "ana@x.com"]])
    right = _csv(tmp_path / "b.csv", ["name"], [["Bruno"]])
    code = main(["merge", str(left), str(right), "-o", str(tmp_path / "m.csv")])
    assert code == 1
    assert "not found in input B" in capsys.readouterr().err

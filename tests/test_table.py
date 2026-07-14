"""Table construction, strict validation, and canonical CSV output."""

from __future__ import annotations

import datetime as dt

import pytest

from tablegold import Table, TableReadError
from tablegold.table import as_table, format_cell, sniff_delimiter


class TestFromText:
    def test_reads_header_rows_quoted_fields_and_crlf(self):
        table = Table.from_text('a,b\r\n1,2\r\n3,"x,y"\r\n')
        assert table.columns == ["a", "b"]
        assert table.rows == [["1", "2"], ["3", "x,y"]]

    def test_header_whitespace_stripped_and_blank_lines_skipped(self):
        table = Table.from_text(" a , b \n1,2\n\n3,4\n")
        assert table.columns == ["a", "b"]
        assert table.n_rows == 2

    def test_malformed_tables_are_rejected_loudly(self):
        # A golden test built on a malformed file asserts nothing, so
        # reading is strict: no silent padding, no last-one-wins headers.
        with pytest.raises(TableReadError, match="empty"):
            Table.from_text("   \n")
        with pytest.raises(TableReadError, match="duplicate"):
            Table.from_text("a,a\n1,2\n")
        with pytest.raises(TableReadError, match="data row 2"):
            Table.from_text("a,b\n1,2\n3\n")


class TestFromCsvFile:
    def test_reads_utf8_with_bom_and_rejects_missing_files(self, tmp_path):
        # Spreadsheet exports routinely prepend a BOM; it must not end up
        # inside the first column name.
        path = tmp_path / "bom.csv"
        path.write_bytes(b"\xef\xbb\xbfa,b\n1,2\n")
        assert Table.from_csv(path).columns == ["a", "b"]
        with pytest.raises(TableReadError, match="cannot read"):
            Table.from_csv(tmp_path / "nope.csv")

    def test_delimiters_are_sniffed_automatically(self, tmp_path):
        path = tmp_path / "data.tsv"
        path.write_text("a\tb\n1\t2\n", encoding="utf-8")
        table = Table.from_csv(path)
        assert table.columns == ["a", "b"]
        assert table.rows == [["1", "2"]]
        # The sniffer picks the most frequent candidate, comma by default.
        assert sniff_delimiter("a;b;c") == ";"
        assert sniff_delimiter("a|b|c|d") == "|"
        assert sniff_delimiter("single_column") == ","


class TestFromRows:
    def test_dict_rows_take_column_order_from_first_row(self):
        table = Table.from_rows([{"id": 1, "score": 0.5}, {"id": 2, "score": 1.5}])
        assert table.columns == ["id", "score"]
        assert table.rows == [["1", "0.5"], ["2", "1.5"]]

    def test_bad_row_shapes_are_read_errors(self):
        with pytest.raises(TableReadError, match="row 2"):
            Table.from_rows([{"id": 1}, {"id": 2, "oops": 3}])
        with pytest.raises(TableReadError, match="columns="):
            Table.from_rows([[1, 2]])  # sequence rows need explicit columns

    def test_values_are_canonicalized_by_format_cell(self):
        table = Table.from_rows(
            [{"ok": True, "when": dt.date(2026, 7, 1), "x": None}],
        )
        assert table.rows == [["true", "2026-07-01", ""]]
        assert format_cell(0.1) == "0.1"  # shortest round-trip repr
        assert float(format_cell(1 / 3)) == 1 / 3
        # bool is a subclass of int; True must not serialize as "1".
        assert format_cell(True) == "true"
        assert format_cell(False) == "false"


class TestCanonicalOutput:
    def test_write_then_read_round_trips_raw_cells(self, tmp_path):
        table = Table.from_text('a,b\n1,"x,y"\n2,\n')
        path = tmp_path / "sub" / "out.csv"  # parent dir created on demand
        table.write_csv(path)
        again = Table.from_csv(path)
        assert again.columns == table.columns
        assert again.rows == table.rows

    def test_output_uses_lf_and_minimal_quoting(self):
        table = Table.from_text('a,b\n"1",2\n')
        assert table.to_csv_text() == "a,b\n1,2\n"


def test_as_table_coerces_paths_passes_tables_and_rejects_junk(
    golden_table, golden_file
):
    assert as_table(golden_table) is golden_table
    assert as_table(golden_file).n_rows == 4
    with pytest.raises(TableReadError, match="cannot interpret"):
        as_table(42)  # type: ignore[arg-type]

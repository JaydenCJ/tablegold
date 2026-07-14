"""Schema-level comparison: column sets, order, and dtype compatibility."""

from __future__ import annotations

import pytest

from tablegold import CompareConfig, ConfigError, compare
from tests.conftest import make_table


class TestColumnSets:
    def test_missing_and_extra_columns_are_errors_unless_extra_allowed(self):
        golden = make_table("a,b\n1,2\n")
        missing = compare(golden, make_table("a\n1\n"))
        assert not missing.ok
        assert any(i.kind == "missing-column" for i in missing.errors())
        strict = compare(make_table("a\n1\n"), make_table("a,b\n1,2\n"))
        assert any(i.kind == "extra-column" for i in strict.errors())
        relaxed = compare(
            make_table("a\n1\n"), make_table("a,b\n1,2\n"), allow_extra_columns=True
        )
        assert relaxed.ok
        assert any(i.kind == "extra-column" for i in relaxed.notes())

    def test_ignored_columns_are_invisible_even_when_absent(self):
        golden = make_table("a,ts\n1,2026-07-01\n")
        actual = make_table("a,ts\n1,2026-07-02\n")  # ts drifted
        assert not compare(golden, actual).ok
        assert compare(golden, actual, ignore_columns=["ts"]).ok
        # Ignoring also covers a column that vanished from the actual table.
        assert compare(
            make_table("a,debug\n1,x\n"), make_table("a\n1\n"), ignore_columns=["debug"]
        ).ok


class TestColumnOrder:
    def test_reordered_columns_match_with_a_note_or_fail_when_strict(self):
        golden = make_table("a,b\n1,2\n")
        actual = make_table("b,a\n2,1\n")
        relaxed = compare(golden, actual)
        assert relaxed.ok  # values matched by name, not position
        assert any(i.kind == "column-order" for i in relaxed.notes())
        strict = compare(golden, actual, strict_column_order=True)
        assert not strict.ok
        assert any(i.kind == "column-order" for i in strict.errors())

    def test_identical_order_produces_no_order_finding(self):
        golden = make_table("a,b\n1,2\n")
        result = compare(golden, golden)
        assert not any(i.kind == "column-order" for i in result.issues)


class TestDtypeChecks:
    def test_int_vs_float_widens_unless_strict(self):
        golden = make_table("x\n1\n2\n")
        actual = make_table("x\n1.0\n2.0\n")
        relaxed = compare(golden, actual)
        assert relaxed.ok
        assert any(i.kind == "dtype" for i in relaxed.notes())
        strict = compare(golden, actual, strict_dtypes=True)
        assert not strict.ok
        assert any(i.kind == "dtype" for i in strict.errors())

    def test_incomparable_dtypes_are_an_error_not_a_crash(self):
        golden = make_table("x\n1\n")
        actual = make_table("x\nhello\n")
        result = compare(golden, actual)
        assert not result.ok
        assert any("not comparable" in i.message for i in result.errors())

    def test_empty_column_is_compatible_but_holes_still_matter(self):
        # An all-missing column matches an all-missing column ...
        golden = make_table("x\nNA\nNA\n")
        assert compare(golden, make_table("x\nNA\nNA\n")).ok
        # ... but a value where the golden has a hole is a cell diff.
        result = compare(make_table("x\nNA\n"), make_table("x\n3.5\n"))
        assert not result.ok
        assert result.cell_mismatch_count == 1


class TestConfigValidation:
    def test_contradictory_or_unknown_options_are_rejected(self):
        with pytest.raises(ConfigError, match="cannot be ignored"):
            CompareConfig(key=["id"], ignore_columns=["id"])
        with pytest.raises(ConfigError, match="max_examples"):
            CompareConfig(max_examples=0)
        golden = make_table("a\n1\n")
        with pytest.raises(ConfigError, match="unknown compare option"):
            compare(golden, golden, rtool=1e-6)  # typo must not pass silently

    def test_string_key_is_treated_as_single_column(self):
        golden = make_table("id,v\n1,2\n")
        result = compare(golden, golden, key="id")
        assert result.matched_by == "key (id)"

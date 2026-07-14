"""Cell-level comparison: tolerance, semantics per dtype, and truncation."""

from __future__ import annotations

from tablegold import Tolerance, compare
from tests.conftest import make_table


class TestNumericTolerance:
    def test_float_noise_and_formatting_differences_match(self):
        # Classic IEEE-754 residue passes under the default tolerance ...
        assert compare(
            make_table("x\n0.30000000000000004\n"), make_table("x\n0.3\n")
        ).ok
        # ... and 1.50 vs 1.5 vs 2.5e0: byte-diff tools flag these; tablegold
        # compares the parsed numbers, so they are simply equal.
        golden = make_table("x\n1.50\n2.5\n")
        actual = make_table("x\n1.5\n2.5e0\n")
        assert compare(golden, actual).ok

    def test_drift_above_tolerance_fails_with_magnitudes(self):
        golden = make_table("x\n100.0\n")
        actual = make_table("x\n100.2\n")
        result = compare(golden, actual, rtol=1e-6)
        assert not result.ok
        example = result.columns[0].examples[0]
        assert "|diff|=0.2" in example.detail
        assert "rel=" in example.detail

    def test_per_column_tolerance_overrides_the_default(self):
        golden = make_table("loose,tight\n100.0,100.0\n")
        actual = make_table("loose,tight\n100.4,100.4\n")
        result = compare(
            golden,
            actual,
            rtol=1e-9,
            column_tolerances={"loose": Tolerance(rtol=0.01)},
        )
        names_with_diffs = [c.name for c in result.columns if c.mismatches]
        assert names_with_diffs == ["tight"]

    def test_integers_compare_exactly_unless_widened_to_float(self):
        # A count that is off by one is a bug no matter how generous rtol is.
        assert not compare(
            make_table("n\n1000\n"), make_table("n\n1001\n"), rtol=1.0
        ).ok
        # But an int column against a float column is compared as floats.
        assert compare(
            make_table("x\n1000\n"), make_table("x\n1000.0000001\n"), rtol=1e-6
        ).ok

    def test_nan_semantics_default_and_opt_out(self):
        # NaN == NaN by default (stable "still NaN here" assertions) ...
        golden = make_table("x\nNaN\n1.0\n")
        assert compare(golden, make_table("x\nnan\n1.0\n")).ok
        # ... NaN never equals a number ...
        assert not compare(golden, make_table("x\n2.0\n1.0\n")).ok
        # ... and nan_equal=False makes NaN-vs-NaN a diff too.
        assert not compare(
            make_table("x\nNaN\n"), make_table("x\nnan\n"), nan_equal=False
        ).ok


class TestSemanticEquality:
    def test_datetime_z_and_offset_forms_are_equal_but_drift_is_not(self):
        golden = make_table("ts\n2026-07-01T09:00:00Z\n")
        assert compare(golden, make_table("ts\n2026-07-01T09:00:00+00:00\n")).ok
        assert not compare(golden, make_table("ts\n2026-07-01T09:00:01Z\n")).ok

    def test_bool_case_is_ignored_but_string_whitespace_is_not(self):
        golden = make_table("ok\ntrue\nFALSE\n")
        actual = make_table("ok\nTRUE\nfalse\n")
        assert compare(golden, actual).ok
        # Strings compare exactly, raw, unstripped.
        assert not compare(make_table("s\nhello\n"), make_table("s\nhello \n")).ok

    def test_missing_cells_match_each_other_but_not_values(self):
        # Different missing spellings are the same hole ...
        assert compare(make_table("x\nNA\n"), make_table("x\nnull\n")).ok
        # ... but a hole where the golden has a value is a labelled diff.
        result = compare(make_table("x\n1.5\n"), make_table("x\nNA\n"))
        assert not result.ok
        example = result.columns[0].examples[0]
        assert example.actual == "<missing>"
        assert "missing" in example.detail


def test_examples_are_capped_but_counts_and_labels_stay_exact():
    rows = "\n".join("%d.0" % n for n in range(10))
    golden = make_table("x\n" + rows + "\n")
    drifted = "\n".join("%d.5" % n for n in range(10))
    actual = make_table("x\n" + drifted + "\n")
    result = compare(golden, actual, max_examples=3)
    column = result.columns[0]
    assert column.mismatches == 10
    assert len(column.examples) == 3
    assert column.examples[0].row_label == "row 1"  # 1-based data rows

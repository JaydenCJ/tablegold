"""Key-based row alignment: order independence, missing/extra/duplicate keys."""

from __future__ import annotations

from tablegold import compare
from tests.conftest import make_table


class TestKeyAlignment:
    def test_reordered_rows_match_by_key_but_not_by_position(self):
        golden = make_table("id,v\n1,10.0\n2,20.0\n3,30.0\n")
        actual = make_table("id,v\n3,30.0\n1,10.0\n2,20.0\n")
        keyed = compare(golden, actual, key=["id"])
        assert keyed.ok
        assert any(i.kind == "row-order" for i in keyed.notes())
        assert not compare(golden, actual).ok  # positional comparison fails

    def test_diff_labels_use_key_values_not_row_numbers(self):
        golden = make_table("id,v\n7,1.0\n8,2.0\n")
        actual = make_table("id,v\n8,2.5\n7,1.0\n")
        result = compare(golden, actual, key=["id"])
        assert result.columns[-1].examples[0].row_label == "id=8"

    def test_composite_keys_align_on_all_parts(self):
        golden = make_table("day,region,v\n1,east,1.0\n1,west,2.0\n2,east,3.0\n")
        actual = make_table("day,region,v\n2,east,3.0\n1,west,2.0\n1,east,1.0\n")
        result = compare(golden, actual, key=["day", "region"])
        assert result.ok
        assert result.matched_by == "key (day, region)"

    def test_key_cells_are_stripped_and_values_still_compared(self):
        assert compare(
            make_table("id,v\n1,10.0\n"), make_table("id,v\n 1 ,10.0\n"), key=["id"]
        ).ok
        # Alignment succeeding does not soften the value comparison.
        result = compare(
            make_table("id,v\n1,1.0\n2,2.0\n"),
            make_table("id,v\n2,9.0\n1,1.0\n"),
            key=["id"],
        )
        assert not result.ok
        assert result.cell_mismatch_count == 1


class TestKeySetProblems:
    def test_missing_and_unexpected_rows_are_reported_with_keys(self):
        golden = make_table("id,v\n1,1.0\n2,2.0\n3,3.0\n")
        actual = make_table("id,v\n1,1.0\n9,9.0\n")
        result = compare(golden, actual, key=["id"])
        assert not result.ok
        messages = [i.message for i in result.errors() if i.kind == "row-set"]
        missing = next(m for m in messages if "missing from actual" in m)
        assert "2 row(s)" in missing
        assert "id=2" in missing and "id=3" in missing
        unexpected = next(m for m in messages if "not in the golden table" in m)
        assert "id=9" in unexpected

    def test_key_gap_examples_are_truncated_with_a_count(self):
        golden_rows = "\n".join("%d,1.0" % n for n in range(10))
        golden = make_table("id,v\n" + golden_rows + "\n")
        actual = make_table("id,v\n0,1.0\n")
        result = compare(golden, actual, key=["id"], max_examples=3)
        message = next(i.message for i in result.errors() if i.kind == "row-set")
        assert "9 row(s)" in message
        assert "(+6 more)" in message

    def test_duplicate_keys_are_an_error_and_skipped(self):
        golden = make_table("id,v\n1,1.0\n1,2.0\n3,3.0\n")
        actual = make_table("id,v\n1,1.0\n3,3.0\n")
        result = compare(golden, actual, key=["id"])
        assert not result.ok
        assert any(i.kind == "duplicate-key" for i in result.errors())
        # The unambiguous row (id=3) is still compared.
        assert result.n_rows_compared == 1

    def test_missing_key_column_aborts_alignment_cleanly(self):
        golden = make_table("id,v\n1,1.0\n")
        actual = make_table("other,v\n1,1.0\n")
        result = compare(golden, actual, key=["id"])
        assert not result.ok
        assert any(i.kind == "key" for i in result.errors())
        assert result.n_rows_compared == 0

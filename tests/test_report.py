"""Report rendering: the text report for humans, the JSON report for tools."""

from __future__ import annotations

import json

from tablegold import compare, render_json, render_text, to_dict
from tests.conftest import make_table


def _mismatch():
    golden = make_table("id,v\n1,10.0\n2,20.0\n", source="golden.csv")
    actual = make_table("id,v\n1,10.0\n2,20.5\n", source="actual.csv")
    return compare(golden, actual, key=["id"], rtol=1e-6)


def _match():
    golden = make_table("id,v\n1,10.0\n", source="golden.csv")
    return compare(golden, golden)


class TestTextReport:
    def test_match_report_ends_with_match_line(self):
        text = render_text(_match())
        assert text.splitlines()[-1].startswith("result: MATCH")

    def test_mismatch_report_names_sources_alignment_and_tolerance(self):
        text = render_text(_mismatch())
        assert "golden golden.csv vs actual actual.csv" in text
        assert "aligned by key (id)" in text
        assert "outside tolerance (rtol=1e-06" in text
        assert "id=2: golden=20.0 actual=20.5" in text
        assert "|diff|=0.5" in text
        assert text.splitlines()[-1] == (
            "result: MISMATCH (1 cell diff(s), 0 schema/row error(s), 0 note(s))"
        )

    def test_truncated_examples_are_announced(self):
        golden = make_table("x\n" + "\n".join("%d.0" % n for n in range(8)) + "\n")
        actual = make_table("x\n" + "\n".join("%d.5" % n for n in range(8)) + "\n")
        text = render_text(compare(golden, actual, max_examples=2))
        assert "... and 6 more in this column" in text

    def test_notes_are_labelled_note_not_error(self):
        golden = make_table("a,b\n1,2\n")
        actual = make_table("b,a\n2,1\n")
        text = render_text(compare(golden, actual))
        assert "note: column order differs" in text
        assert "error:" not in text


class TestJsonReport:
    def test_json_is_valid_versioned_and_counts_agree(self):
        comparison = _mismatch()
        payload = json.loads(render_json(comparison))
        assert payload["report_version"] == 1
        assert payload["ok"] is False
        assert payload["cell_diffs"]["total"] == comparison.cell_mismatch_count
        assert payload["rows"] == {"golden": 2, "actual": 2, "compared": 2}

    def test_json_carries_examples_with_tolerance_and_omits_clean_columns(self):
        payload = to_dict(_mismatch())
        (column,) = payload["cell_diffs"]["by_column"]  # id matched: absent
        assert column["column"] == "v"
        assert column["tolerance"]["rtol"] == 1e-6
        assert column["examples"][0]["row"] == "id=2"

    def test_json_is_deterministic_and_clean_on_match(self):
        assert render_json(_mismatch()) == render_json(_mismatch())
        payload = to_dict(_match())
        assert payload["ok"] is True
        assert payload["cell_diffs"] == {"total": 0, "by_column": []}

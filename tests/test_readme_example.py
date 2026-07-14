"""The README quickstart, executed verbatim.

If the README's Python example stops working, this file fails — keeping
documentation and behavior in lockstep (the same discipline as the
committed example golden).
"""

from __future__ import annotations

import pytest

from tablegold import GoldenMismatchError, assert_matches_golden


def build_report():
    """The 'pipeline output' from the README quickstart."""
    return [
        {"id": 1001, "region": "east", "revenue": 1929.6562000000004},
        {"id": 1002, "region": "west", "revenue": 2070.1845999999996},
    ]


def test_readme_quickstart_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rows = build_report()

    # First run with TABLEGOLD_UPDATE=1 blesses the golden ...
    monkeypatch.setenv("TABLEGOLD_UPDATE", "1")
    assert_matches_golden(rows, "goldens/report.csv", key=["id"], rtol=1e-9)
    monkeypatch.delenv("TABLEGOLD_UPDATE")

    # ... later runs pass despite last-bit float noise (the README claim).
    noisy = [
        {"id": 1001, "region": "east", "revenue": 1929.6562000000001},
        {"id": 1002, "region": "west", "revenue": 2070.1846},
    ]
    comparison = assert_matches_golden(noisy, "goldens/report.csv", key=["id"], rtol=1e-9)
    assert comparison.ok


def test_readme_mismatch_is_loud(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TABLEGOLD_UPDATE", "1")
    assert_matches_golden(build_report(), "goldens/report.csv", key=["id"])
    monkeypatch.delenv("TABLEGOLD_UPDATE")

    drifted = [
        {"id": 1001, "region": "east", "revenue": 1929.6562000000004},
        {"id": 1002, "region": "west", "revenue": 2071.0},
    ]
    with pytest.raises(GoldenMismatchError, match="result: MISMATCH"):
        assert_matches_golden(drifted, "goldens/report.csv", key=["id"], rtol=1e-9)

"""Golden-file lifecycle: assert, bless, update via argument or environment."""

from __future__ import annotations

import pytest

from tablegold import (
    GoldenMismatchError,
    GoldenMissingError,
    assert_matches_golden,
    bless,
)
from tablegold.golden import UPDATE_ENV_VAR, update_requested

ROWS_V1 = [{"id": 1, "score": 0.5}, {"id": 2, "score": 1.5}]
ROWS_DRIFTED = [{"id": 1, "score": 0.5}, {"id": 2, "score": 9.9}]


class TestAssertMatchesGolden:
    def test_passes_and_returns_comparison_when_data_matches(self, tmp_path):
        golden = tmp_path / "g.csv"
        bless(ROWS_V1, golden)
        assert assert_matches_golden(ROWS_V1, golden).ok

    def test_raises_assertion_error_subclass_with_full_report(self, tmp_path):
        golden = tmp_path / "g.csv"
        bless(ROWS_V1, golden)
        with pytest.raises(AssertionError) as excinfo:
            assert_matches_golden(ROWS_DRIFTED, golden)
        # pytest renders the message; it must carry the whole report.
        assert "result: MISMATCH" in str(excinfo.value)
        assert excinfo.value.comparison is not None

    def test_update_creates_and_re_blesses_goldens(self, tmp_path):
        # Without update mode, a missing golden fails with a how-to hint.
        with pytest.raises(GoldenMissingError, match=UPDATE_ENV_VAR):
            assert_matches_golden(ROWS_V1, tmp_path / "never.csv")
        golden = tmp_path / "new" / "g.csv"
        assert assert_matches_golden(ROWS_V1, golden, update=True).ok
        assert golden.exists()
        # Re-blessing overwrites: afterwards the old data must fail.
        assert_matches_golden(ROWS_DRIFTED, golden, update=True)
        with pytest.raises(GoldenMismatchError):
            assert_matches_golden(ROWS_V1, golden)

    def test_compare_options_flow_through(self, tmp_path):
        golden = tmp_path / "g.csv"
        bless(ROWS_V1, golden)
        noisy = [{"id": 1, "score": 0.5000001}, {"id": 2, "score": 1.5}]
        with pytest.raises(GoldenMismatchError):
            assert_matches_golden(noisy, golden)  # default rtol is strict
        assert assert_matches_golden(noisy, golden, rtol=1e-3).ok


class TestUpdateEnvironment:
    def test_env_var_enables_update_but_explicit_false_wins(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv(UPDATE_ENV_VAR, "1")
        golden = tmp_path / "g.csv"
        assert assert_matches_golden(ROWS_V1, golden).ok
        assert golden.exists()
        with pytest.raises(GoldenMissingError):
            assert_matches_golden(ROWS_V1, tmp_path / "other.csv", update=False)

    def test_truthy_and_falsy_env_spellings(self, monkeypatch):
        for value in ("1", "true", "YES", " on "):
            monkeypatch.setenv(UPDATE_ENV_VAR, value)
            assert update_requested() is True, value
        for value in ("", "0", "false", "off"):
            monkeypatch.setenv(UPDATE_ENV_VAR, value)
            assert update_requested() is False, value


class TestBless:
    def test_bless_writes_canonical_bytes_even_from_crlf_input(self, tmp_path):
        golden = tmp_path / "g.csv"
        bless(ROWS_V1, golden)
        assert golden.read_text(encoding="utf-8") == "id,score\n1,0.5\n2,1.5\n"
        source = tmp_path / "crlf.csv"
        source.write_bytes(b"a,b\r\n1,2\r\n")
        bless(source, golden)
        assert b"\r" not in golden.read_bytes()

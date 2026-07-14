"""The ``tablegold`` pytest fixture, exercised through pytester.

Each test spins up a miniature pytest project in a temp dir and runs it
in-process — real fixture resolution, real golden files, no subprocess.
The inner runs block the entry-point copy of the plugin (``no:tablegold``)
and register it via conftest instead, so they behave identically whether
the suite runs from a plain checkout or an installed package.
"""

from __future__ import annotations

INNER_CONFTEST = 'pytest_plugins = ["tablegold.pytest_plugin"]\n'


def _make_project(pytester, test_body: str) -> None:
    pytester.makeconftest(INNER_CONFTEST)
    pytester.makepyfile(test_body)


def _run(pytester, *args):
    return pytester.runpytest("-p", "no:tablegold", *args)


def test_fixture_blesses_then_passes_on_rerun(pytester, monkeypatch):
    _make_project(
        pytester,
        """
        ROWS = [{"id": 1, "v": 0.5}, {"id": 2, "v": 1.5}]

        def test_metrics(tablegold):
            tablegold.check(ROWS, key=["id"])
        """,
    )
    # First run in update mode creates goldens/test_metrics.csv ...
    monkeypatch.setenv("TABLEGOLD_UPDATE", "1")
    _run(pytester).assert_outcomes(passed=1)
    golden = pytester.path / "goldens" / "test_metrics.csv"
    assert golden.exists()
    # ... second run without update mode verifies against it.
    monkeypatch.delenv("TABLEGOLD_UPDATE")
    _run(pytester).assert_outcomes(passed=1)


def test_fixture_failure_shows_the_full_report(pytester, monkeypatch):
    monkeypatch.delenv("TABLEGOLD_UPDATE", raising=False)
    pytester.makeconftest(INNER_CONFTEST)
    (pytester.path / "goldens").mkdir()
    (pytester.path / "goldens" / "test_drift.csv").write_text(
        "id,v\n1,10.0\n", encoding="utf-8"
    )
    pytester.makepyfile(
        """
        def test_drift(tablegold):
            tablegold.check([{"id": 1, "v": 10.4}])
        """
    )
    result = _run(pytester)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*result: MISMATCH*"])


def test_missing_golden_fails_with_update_hint(pytester, monkeypatch):
    monkeypatch.delenv("TABLEGOLD_UPDATE", raising=False)
    _make_project(
        pytester,
        """
        def test_new(tablegold):
            tablegold.check([{"id": 1}])
        """,
    )
    result = _run(pytester)
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*TABLEGOLD_UPDATE=1*"])


def test_update_command_line_flag_blesses(pytester, monkeypatch):
    monkeypatch.delenv("TABLEGOLD_UPDATE", raising=False)
    _make_project(
        pytester,
        """
        def test_flagged(tablegold):
            tablegold.check([{"id": 1}])
        """,
    )
    _run(pytester, "--tablegold-update").assert_outcomes(passed=1)
    assert (pytester.path / "goldens" / "test_flagged.csv").exists()


def test_golden_dir_ini_option_moves_goldens(pytester, monkeypatch):
    monkeypatch.setenv("TABLEGOLD_UPDATE", "1")
    pytester.makeconftest(INNER_CONFTEST)
    pytester.makeini("[pytest]\ntablegold_dir = expected\n")
    pytester.makepyfile(
        """
        def test_located(tablegold):
            tablegold.check([{"id": 1}])
        """
    )
    _run(pytester).assert_outcomes(passed=1)
    assert (pytester.path / "expected" / "test_located.csv").exists()


def test_parametrized_test_names_are_sanitized(pytester, monkeypatch):
    monkeypatch.setenv("TABLEGOLD_UPDATE", "1")
    _make_project(
        pytester,
        """
        import pytest

        @pytest.mark.parametrize("region", ["east", "west"])
        def test_regions(tablegold, region):
            tablegold.check([{"region": region}])
        """,
    )
    _run(pytester).assert_outcomes(passed=2)
    names = sorted(p.name for p in (pytester.path / "goldens").iterdir())
    assert names == ["test_regions_east_.csv", "test_regions_west_.csv"]

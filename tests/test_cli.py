"""End-to-end CLI behavior through ``tablegold.cli.main`` (no subprocesses).

Exit codes are part of the contract: 0 match, 1 mismatch, 2 error — CI
pipelines branch on them.
"""

from __future__ import annotations

import json

import pytest

from tablegold import __version__
from tablegold.cli import EXIT_ERROR, EXIT_MATCH, EXIT_MISMATCH, main


def write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


@pytest.fixture
def files(tmp_path):
    golden = write(tmp_path / "golden.csv", "id,v\n1,10.0\n2,20.0\n")
    noisy = write(tmp_path / "noisy.csv", "id,v\n1,10.000000001\n2,20.0\n")
    drifted = write(tmp_path / "drifted.csv", "id,v\n1,10.0\n2,20.5\n")
    return {"golden": golden, "noisy": noisy, "drifted": drifted}


class TestDiff:
    def test_noise_within_tolerance_matches_with_exit_zero(self, files, capsys):
        code = main(["diff", files["golden"], files["noisy"]])
        assert code == EXIT_MATCH
        assert "result: MATCH" in capsys.readouterr().out

    def test_real_drift_exits_one_with_a_report(self, files, capsys):
        code = main(["diff", files["golden"], files["drifted"]])
        assert code == EXIT_MISMATCH
        out = capsys.readouterr().out
        assert "column v [float]" in out
        assert "result: MISMATCH" in out

    def test_rtol_and_per_column_tol_flags_loosen_the_comparison(self, files):
        assert main(["diff", files["golden"], files["drifted"]]) == EXIT_MISMATCH
        assert (
            main(["diff", "--rtol", "0.1", files["golden"], files["drifted"]])
            == EXIT_MATCH
        )
        assert (
            main(["diff", "--tol", "v:0.1", files["golden"], files["drifted"]])
            == EXIT_MATCH
        )

    def test_key_and_ignore_flags_shape_the_comparison(self, tmp_path):
        golden = write(tmp_path / "g.csv", "id,v\n1,1.0\n2,2.0\n")
        shuffled = write(tmp_path / "a.csv", "id,v\n2,2.0\n1,1.0\n")
        assert main(["diff", golden, shuffled]) == EXIT_MISMATCH
        assert main(["diff", "--key", "id", golden, shuffled]) == EXIT_MATCH
        golden2 = write(tmp_path / "g2.csv", "v,ts\n1.0,2026-07-01\n")
        actual2 = write(tmp_path / "a2.csv", "v,ts\n1.0,2026-07-02\n")
        assert main(["diff", golden2, actual2]) == EXIT_MISMATCH
        assert main(["diff", "--ignore", "ts", golden2, actual2]) == EXIT_MATCH

    def test_strict_column_order_and_tab_delimiter_flags(self, tmp_path):
        golden = write(tmp_path / "g.csv", "a,b\n1,2\n")
        reordered = write(tmp_path / "a.csv", "b,a\n2,1\n")
        assert main(["diff", golden, reordered]) == EXIT_MATCH
        assert (
            main(["diff", "--strict-column-order", golden, reordered])
            == EXIT_MISMATCH
        )
        tsv_golden = write(tmp_path / "g.tsv", "a\tb\n1\t2\n")
        tsv_actual = write(tmp_path / "a.tsv", "a\tb\n1\t2\n")
        assert main(["diff", "--delimiter", r"\t", tsv_golden, tsv_actual]) == EXIT_MATCH

    def test_json_format_emits_machine_report(self, files, capsys):
        code = main(["diff", "--format", "json", files["golden"], files["drifted"]])
        assert code == EXIT_MISMATCH
        payload = json.loads(capsys.readouterr().out)
        assert payload["ok"] is False
        assert payload["cell_diffs"]["total"] == 1

    def test_usage_problems_exit_two_with_stderr_messages(self, files, capsys):
        assert main(["diff", files["golden"], "/nonexistent/a.csv"]) == EXIT_ERROR
        assert "tablegold: error:" in capsys.readouterr().err
        code = main(["diff", "--tol", "v", files["golden"], files["noisy"]])
        assert code == EXIT_ERROR
        assert "invalid --tol spec" in capsys.readouterr().err


class TestShowAndBless:
    def test_show_prints_schema_and_non_empty_counts(self, tmp_path, capsys):
        path = write(tmp_path / "holes.csv", "n,x\n1,1.5\n2,\n")
        assert main(["show", path]) == EXIT_MATCH
        out = capsys.readouterr().out
        assert "rows: 2" in out
        assert "columns: 2" in out
        assert "int" in out and "float" in out
        assert "1/2 non-empty" in out  # x has one hole

    def test_bless_writes_golden_then_diffs_clean(self, tmp_path, capsys):
        actual = write(tmp_path / "a.csv", "a,b\n1,2\n3,4\n")
        golden = tmp_path / "golden" / "g.csv"
        assert main(["bless", actual, str(golden)]) == EXIT_MATCH
        assert "blessed" in capsys.readouterr().out
        assert golden.read_text(encoding="utf-8") == "a,b\n1,2\n3,4\n"
        assert main(["diff", str(golden), actual]) == EXIT_MATCH


class TestTopLevel:
    def test_version_flag_and_bare_invocation(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["--version"])
        assert excinfo.value.code == 0
        assert capsys.readouterr().out.strip() == "tablegold %s" % __version__
        # No command: print help (all subcommands listed) and exit 2.
        assert main([]) == EXIT_ERROR
        out = capsys.readouterr().out
        for command in ("diff", "show", "bless"):
            assert command in out

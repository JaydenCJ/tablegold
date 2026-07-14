# Contributing to tablegold

Thanks for your interest in contributing. Issues, discussions, and pull
requests are all welcome.

## Getting started

You need Python 3.9 or newer; the runtime has zero dependencies and the test
suite needs only pytest.

```bash
git clone https://github.com/JaydenCJ/tablegold
cd tablegold
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                 # 90 tests: unit, CLI, plugin, README, examples
bash scripts/smoke.sh  # end-to-end CLI smoke; must print SMOKE OK
```

`scripts/smoke.sh` runs the example pipeline and the real CLI (bless, show,
diff, JSON report, exit codes) in a temp directory and must print `SMOKE OK`.

## Before you open a pull request

1. Format touched files consistently with the surrounding code (PEP 8,
   4-space indents, docstrings in English) — formatting is enforced in review.
2. `pytest` must pass with zero failures, fully offline.
3. `bash scripts/smoke.sh` must print `SMOKE OK`.
4. Add tests for behavior changes; keep logic in pure, unit-testable modules
   (`dtypes`, `tolerance`, `compare`) rather than in the CLI shell.
5. If you change what a comparison verdict *means* (dtype rules, missing
   tokens, closeness formula), update `docs/comparison-semantics.md` and the
   README in the same pull request.

## Ground rules

- **No runtime dependencies.** The package is standard-library only; that is
  a feature. Test-only dependencies belong in the `dev` extra, and adding one
  needs justification in the PR.
- No network calls, no telemetry — the tool reads and writes local files only.
- The JSON report is a versioned format: field changes bump `report_version`.
- Keep the three READMEs aligned. `README.md`, `README.zh.md`, and
  `README.ja.md` share the same line-for-line structure; update all three
  when you change one (English is the authoritative version).

## Reporting bugs

Please include `tablegold --version` output, the exact command or API call,
both CSV files (or a minimal pair that reproduces it), and the full report —
the `result:` line plus any `error:`/`note:` lines are usually enough to
diagnose a verdict.

## Security

Please do not report security issues in public GitHub issues. Use GitHub's
private vulnerability reporting on the repository instead.

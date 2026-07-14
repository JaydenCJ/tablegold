# Changelog

All notable changes to this project are documented in this file. The format is
based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-12

### Added

- Column-semantic comparison engine (`compare`): columns matched by name,
  with missing/extra-column errors, an `allow_extra_columns` escape hatch,
  and column order reported as a note (or an error under
  `strict_column_order`).
- Dtype inference per column (`bool`, `int`, `float`, `date`, `datetime`,
  `string`, `empty`) with conservative rules: int+float widens to float,
  every other mix degrades to string; dtype drift is a schema finding, and
  `strict_dtypes` forbids even the int/float widening.
- Numeric tolerance: symmetric `|a-b| <= max(atol, rtol*max(|a|,|b|))`
  closeness, per-column `Tolerance` overrides, explicit NaN semantics
  (NaN == NaN by default, opt out with `nan_equal=False`), signed-zero and
  infinity handling, and honest `|diff|`/`rel` magnitudes in every report.
- Row alignment by position or by key columns (`key=["id"]`): reordered
  rows compare clean with a note, while duplicate, missing, and unexpected
  keys are reported with example key values.
- Semantic cell equality beyond floats: `2026-07-01T09:00:00Z` equals
  `…+00:00`, `TRUE` equals `true`, and `NA`/`null`/empty are the same hole —
  while strings still compare byte-exact.
- Golden lifecycle: `assert_matches_golden` (raises an `AssertionError`
  subclass carrying the full report), `bless` for canonical golden writing,
  and update mode via `TABLEGOLD_UPDATE=1` or `update=True`.
- pytest plugin: a `tablegold` fixture that stores goldens next to the test
  file (`tablegold_dir` ini option), sanitizes parametrized test names, and
  re-blesses via `--tablegold-update`.
- `tablegold` CLI: `diff` (exit 0 match / 1 mismatch / 2 error, `--format
  json` machine report), `show` (inferred schema), and `bless`; delimiter
  sniffing for CSV/TSV and a strict, BOM-tolerant reader.
- Runnable example: a deterministic aggregation pipeline whose fold-order
  float noise passes and whose injected regression is caught
  (`examples/pipeline_demo.py` plus an example pytest suite).
- 90 pytest tests (unit, CLI, plugin-via-pytester, README, examples) and
  `scripts/smoke.sh` covering the CLI end to end.

### Notes

- The repository ships no CI workflow; verification is local — `pip install -e '.[dev]' && pytest && bash scripts/smoke.sh`.

[0.1.0]: https://github.com/JaydenCJ/tablegold/releases/tag/v0.1.0

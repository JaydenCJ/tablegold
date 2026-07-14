"""The column-semantic comparison engine.

``compare(golden, actual)`` produces a :class:`Comparison` that separates
three kinds of findings:

- **schema issues** — missing/extra columns, incompatible dtypes, column
  order (an error only under ``strict_column_order``);
- **row issues** — row-count mismatch, and with key columns: duplicate,
  missing, or unexpected keys;
- **cell diffs** — per column, per aligned row, with numeric columns
  judged by tolerance and everything else by parsed semantic equality.

Notes never fail a comparison; errors and cell diffs do. The engine never
raises on mismatching data — bad *configuration* raises
:class:`~tablegold.errors.ConfigError`, bad *data* becomes a finding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from . import dtypes
from .errors import ConfigError
from .table import Table, TableLike, as_table
from .tolerance import (
    DEFAULT_ATOL,
    DEFAULT_RTOL,
    Tolerance,
    diff_magnitudes,
    floats_close,
)

ERROR = "error"
NOTE = "note"

MISSING_DISPLAY = "<missing>"


@dataclass(frozen=True)
class CompareConfig:
    """Everything that shapes a comparison. All fields have safe defaults."""

    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL
    nan_equal: bool = True
    column_tolerances: Mapping[str, Tolerance] = field(default_factory=dict)
    key: Sequence[str] = ()
    ignore_columns: Sequence[str] = ()
    strict_column_order: bool = False
    strict_dtypes: bool = False
    allow_extra_columns: bool = False
    max_examples: int = 5

    def __post_init__(self) -> None:
        # Accept a bare string for single-column key/ignore specs.
        if isinstance(self.key, str):
            object.__setattr__(self, "key", (self.key,))
        if isinstance(self.ignore_columns, str):
            object.__setattr__(self, "ignore_columns", (self.ignore_columns,))
        overlap = set(self.key) & set(self.ignore_columns)
        if overlap:
            raise ConfigError(
                "key columns cannot be ignored: %s" % ", ".join(sorted(overlap))
            )
        if self.max_examples < 1:
            raise ConfigError("max_examples must be >= 1")
        # Validates rtol/atol eagerly so a typo fails at configure time.
        Tolerance(self.rtol, self.atol, self.nan_equal)

    def tolerance_for(self, column: str) -> Tolerance:
        override = self.column_tolerances.get(column)
        if override is not None:
            return override
        return Tolerance(rtol=self.rtol, atol=self.atol, nan_equal=self.nan_equal)


@dataclass
class Issue:
    """A schema- or row-level finding."""

    kind: str  # e.g. "missing-column", "row-count", "duplicate-key"
    message: str
    severity: str = ERROR  # ERROR fails the comparison; NOTE never does


@dataclass
class CellDiff:
    """One cell that differs between golden and actual."""

    column: str
    row_label: str  # "row 3" or "id=1003"
    golden: str  # raw cell (or <missing>)
    actual: str
    detail: str = ""  # e.g. "|diff|=0.5 rel=4e-04"


@dataclass
class ColumnResult:
    """Comparison outcome for one column that was value-compared."""

    name: str
    dtype: str  # unified dtype the values were compared under
    compared: int  # number of aligned row pairs examined
    mismatches: int = 0  # total, including truncated examples
    examples: List[CellDiff] = field(default_factory=list)
    tolerance: Optional[Tolerance] = None  # set for numeric columns


@dataclass
class Comparison:
    """The full result of one golden-vs-actual comparison."""

    golden_source: str
    actual_source: str
    issues: List[Issue] = field(default_factory=list)
    columns: List[ColumnResult] = field(default_factory=list)
    matched_by: str = "position"
    n_rows_golden: int = 0
    n_rows_actual: int = 0
    n_rows_compared: int = 0
    n_columns_compared: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == ERROR)

    @property
    def note_count(self) -> int:
        return sum(1 for issue in self.issues if issue.severity == NOTE)

    @property
    def cell_mismatch_count(self) -> int:
        return sum(column.mismatches for column in self.columns)

    @property
    def ok(self) -> bool:
        return self.error_count == 0 and self.cell_mismatch_count == 0

    def notes(self) -> List[Issue]:
        return [issue for issue in self.issues if issue.severity == NOTE]

    def errors(self) -> List[Issue]:
        return [issue for issue in self.issues if issue.severity == ERROR]


def compare(
    golden: TableLike,
    actual: TableLike,
    config: Optional[CompareConfig] = None,
    delimiter: Optional[str] = None,
    **overrides: Any,
) -> Comparison:
    """Compare *actual* against *golden* and return a :class:`Comparison`.

    Both sides accept a file path, a :class:`~tablegold.table.Table`, or
    in-memory rows (``list[dict]``). Keyword overrides are applied on top
    of *config* (or the defaults), e.g. ``compare(a, b, rtol=1e-6)``.
    """
    if overrides:
        base = config or CompareConfig()
        merged = {
            name: getattr(base, name) for name in CompareConfig.__dataclass_fields__
        }
        unknown = set(overrides) - set(merged)
        if unknown:
            raise ConfigError(
                "unknown compare option(s): %s" % ", ".join(sorted(unknown))
            )
        merged.update(overrides)
        config = CompareConfig(**merged)
    elif config is None:
        config = CompareConfig()

    golden_table = as_table(golden, delimiter=delimiter)
    actual_table = as_table(actual, delimiter=delimiter)

    result = Comparison(
        golden_source=golden_table.source,
        actual_source=actual_table.source,
        n_rows_golden=golden_table.n_rows,
        n_rows_actual=actual_table.n_rows,
    )

    shared = _compare_schema(golden_table, actual_table, config, result)
    pairs = _align_rows(golden_table, actual_table, config, result)
    if pairs is None:
        return result
    result.n_rows_compared = len(pairs)
    _compare_cells(golden_table, actual_table, shared, pairs, config, result)
    return result


# -- schema ---------------------------------------------------------------


def _compare_schema(
    golden: Table, actual: Table, config: CompareConfig, result: Comparison
) -> List[Tuple[str, str]]:
    """Report column-set, order, and dtype findings.

    Returns the list of ``(column, unified_dtype)`` pairs that are safe to
    value-compare.
    """
    ignored = set(config.ignore_columns)
    golden_cols = [c for c in golden.columns if c not in ignored]
    actual_cols = [c for c in actual.columns if c not in ignored]
    golden_set, actual_set = set(golden_cols), set(actual_cols)

    for name in (c for c in golden_cols if c not in actual_set):
        result.issues.append(
            Issue("missing-column", "column %r is missing from actual" % name)
        )
    for name in (c for c in actual_cols if c not in golden_set):
        severity = NOTE if config.allow_extra_columns else ERROR
        result.issues.append(
            Issue(
                "extra-column",
                "column %r is not in the golden table" % name,
                severity,
            )
        )

    common = [c for c in golden_cols if c in actual_set]
    actual_order = [c for c in actual_cols if c in golden_set]
    if common != actual_order:
        severity = ERROR if config.strict_column_order else NOTE
        result.issues.append(
            Issue(
                "column-order",
                "column order differs (golden: %s | actual: %s)"
                % (", ".join(common), ", ".join(actual_order)),
                severity,
            )
        )

    golden_schema, actual_schema = golden.schema(), actual.schema()
    shared: List[Tuple[str, str]] = []
    for name in common:
        g_dtype, a_dtype = golden_schema[name], actual_schema[name]
        unified, note = dtypes.unify_dtypes(g_dtype, a_dtype)
        if config.strict_dtypes and g_dtype != a_dtype:
            result.issues.append(
                Issue(
                    "dtype",
                    "column %r dtype differs: golden is %s, actual is %s"
                    % (name, g_dtype, a_dtype),
                )
            )
            continue  # strict mode: do not value-compare a retyped column
        if unified is None:
            result.issues.append(
                Issue(
                    "dtype",
                    "column %r is not comparable: golden is %s, actual is %s"
                    % (name, g_dtype, a_dtype),
                )
            )
            continue
        if note:
            result.issues.append(Issue("dtype", "column %r %s" % (name, note), NOTE))
        shared.append((name, unified))
    result.n_columns_compared = len(shared)
    return shared


# -- row alignment ----------------------------------------------------------


def _align_rows(
    golden: Table, actual: Table, config: CompareConfig, result: Comparison
) -> Optional[List[Tuple[int, int, str]]]:
    """Return aligned ``(golden_row, actual_row, label)`` triples.

    Positional alignment pairs rows by index; key alignment pairs rows by
    the values of the key columns and reports missing/unexpected/duplicate
    keys. Returns None when alignment is impossible (bad key columns).
    """
    if not config.key:
        result.matched_by = "position"
        if golden.n_rows != actual.n_rows:
            result.issues.append(
                Issue(
                    "row-count",
                    "row count differs: %d in golden vs %d in actual"
                    % (golden.n_rows, actual.n_rows),
                )
            )
        shared_count = min(golden.n_rows, actual.n_rows)
        return [(i, i, "row %d" % (i + 1)) for i in range(shared_count)]

    key_cols = list(config.key)
    result.matched_by = "key (%s)" % ", ".join(key_cols)
    for name in key_cols:
        for side, table in (("golden", golden), ("actual", actual)):
            if name not in table.columns:
                result.issues.append(
                    Issue("key", "key column %r is missing from %s" % (name, side))
                )
    if any(issue.kind == "key" for issue in result.issues):
        return None

    golden_keys = _key_map(golden, key_cols, "golden", config, result)
    actual_keys = _key_map(actual, key_cols, "actual", config, result)

    missing = [k for k in golden_keys if k not in actual_keys]
    unexpected = [k for k in actual_keys if k not in golden_keys]
    _report_key_gap(missing, key_cols, "missing from actual", config, result)
    _report_key_gap(unexpected, key_cols, "not in the golden table", config, result)

    common = [k for k in golden_keys if k in actual_keys]
    actual_side_order = [k for k in actual_keys if k in golden_keys]
    if common != actual_side_order:
        result.issues.append(
            Issue("row-order", "row order differs (rows aligned by key)", NOTE)
        )
    return [
        (golden_keys[k], actual_keys[k], _key_label(key_cols, k)) for k in common
    ]


def _key_map(
    table: Table,
    key_cols: List[str],
    side: str,
    config: CompareConfig,
    result: Comparison,
) -> Dict[tuple, int]:
    """Map key tuple -> row index, dropping and reporting duplicate keys."""
    indexes = [table.column_index(name) for name in key_cols]
    first_seen: Dict[tuple, int] = {}
    duplicates: List[tuple] = []
    for row_index, row in enumerate(table.rows):
        key = table.key_for_row(row, indexes)
        if key in first_seen:
            if key not in duplicates:
                duplicates.append(key)
        else:
            first_seen[key] = row_index
    if duplicates:
        shown = ", ".join(_key_label(key_cols, k) for k in duplicates[: config.max_examples])
        more = len(duplicates) - min(len(duplicates), config.max_examples)
        suffix = " (+%d more)" % more if more else ""
        result.issues.append(
            Issue(
                "duplicate-key",
                "%d duplicate key(s) in %s: %s%s" % (len(duplicates), side, shown, suffix),
            )
        )
        for key in duplicates:
            del first_seen[key]  # ambiguous rows are not compared
    return first_seen


def _report_key_gap(
    keys: List[tuple],
    key_cols: List[str],
    what: str,
    config: CompareConfig,
    result: Comparison,
) -> None:
    if not keys:
        return
    shown = ", ".join(_key_label(key_cols, k) for k in keys[: config.max_examples])
    more = len(keys) - min(len(keys), config.max_examples)
    suffix = " (+%d more)" % more if more else ""
    result.issues.append(
        Issue("row-set", "%d row(s) %s: %s%s" % (len(keys), what, shown, suffix))
    )


def _key_label(key_cols: Sequence[str], key: tuple) -> str:
    return ", ".join("%s=%s" % (name, value) for name, value in zip(key_cols, key))


# -- cells ------------------------------------------------------------------


def _compare_cells(
    golden: Table,
    actual: Table,
    shared: List[Tuple[str, str]],
    pairs: List[Tuple[int, int, str]],
    config: CompareConfig,
    result: Comparison,
) -> None:
    for name, unified in shared:
        g_index = golden.column_index(name)
        a_index = actual.column_index(name)
        tolerance = config.tolerance_for(name) if unified == dtypes.FLOAT else None
        column = ColumnResult(
            name=name, dtype=unified, compared=len(pairs), tolerance=tolerance
        )
        for g_row, a_row, label in pairs:
            g_raw = golden.rows[g_row][g_index]
            a_raw = actual.rows[a_row][a_index]
            equal, detail = _cells_equal(g_raw, a_raw, unified, tolerance)
            if equal:
                continue
            column.mismatches += 1
            if len(column.examples) < config.max_examples:
                column.examples.append(
                    CellDiff(
                        column=name,
                        row_label=label,
                        golden=_display(g_raw),
                        actual=_display(a_raw),
                        detail=detail,
                    )
                )
        result.columns.append(column)


def _cells_equal(
    g_raw: str, a_raw: str, unified: str, tolerance: Optional[Tolerance]
) -> Tuple[bool, str]:
    """Compare two raw cells under a unified dtype; return (equal, detail)."""
    g_missing, a_missing = dtypes.is_missing(g_raw), dtypes.is_missing(a_raw)
    if g_missing or a_missing:
        if g_missing and a_missing:
            return True, ""
        return False, "missing on one side only"

    g_value = dtypes.parse_value(g_raw, unified)
    a_value = dtypes.parse_value(a_raw, unified)

    if unified == dtypes.FLOAT and tolerance is not None:
        if isinstance(g_value, float) and isinstance(a_value, float):
            if floats_close(g_value, a_value, tolerance):
                return True, ""
            absolute, relative = diff_magnitudes(g_value, a_value)
            return False, "|diff|=%s rel=%s" % (_fmt(absolute), _fmt(relative))
        return False, "not parseable as float on both sides"

    if unified == dtypes.STRING:
        return (g_raw == a_raw), "string values differ"

    if type(g_value) is not type(a_value):
        return False, "parsed types differ"
    return (g_value == a_value), "values differ"


def _fmt(value: float) -> str:
    if math.isnan(value):
        return "nan"
    return "%.3g" % value


def _display(raw: str) -> str:
    return MISSING_DISPLAY if dtypes.is_missing(raw) else raw

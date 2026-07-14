"""Rendering a :class:`~tablegold.compare.Comparison` for humans and machines.

Two renderers, one truth:

- :func:`render_text` — the report printed by the CLI and embedded in
  :class:`~tablegold.errors.GoldenMismatchError` messages. Designed to be
  readable in a CI log: one line per finding, examples indented.
- :func:`render_json` — a stable machine format (``report_version: 1``)
  with deterministic key order, for piping into other tooling.
"""

from __future__ import annotations

import json
from typing import Any, Dict

from .compare import Comparison

REPORT_VERSION = 1


def render_text(comparison: Comparison) -> str:
    """Render the human-readable report, ending with a MATCH/MISMATCH line."""
    lines = [
        "tablegold: golden %s vs actual %s"
        % (comparison.golden_source, comparison.actual_source)
    ]
    lines.append(
        "rows: %d golden vs %d actual, aligned by %s"
        % (comparison.n_rows_golden, comparison.n_rows_actual, comparison.matched_by)
    )
    for issue in comparison.issues:
        lines.append("%s: %s" % (issue.severity, issue.message))
    for column in comparison.columns:
        if not column.mismatches:
            continue
        if column.tolerance is not None:
            what = "values outside tolerance (%s)" % column.tolerance.describe()
        else:
            what = "values differ"
        lines.append(
            "column %s [%s]: %d of %d %s"
            % (column.name, column.dtype, column.mismatches, column.compared, what)
        )
        for example in column.examples:
            detail = "  %s" % example.detail if example.detail else ""
            lines.append(
                "  %s: golden=%s actual=%s%s"
                % (example.row_label, example.golden, example.actual, detail)
            )
        hidden = column.mismatches - len(column.examples)
        if hidden:
            lines.append("  ... and %d more in this column" % hidden)
    lines.append(_summary_line(comparison))
    return "\n".join(lines)


def _summary_line(comparison: Comparison) -> str:
    if comparison.ok:
        detail = "%d row(s) x %d column(s) within tolerance" % (
            comparison.n_rows_compared,
            comparison.n_columns_compared,
        )
        if comparison.note_count:
            detail += ", %d note(s)" % comparison.note_count
        return "result: MATCH (%s)" % detail
    return "result: MISMATCH (%d cell diff(s), %d schema/row error(s), %d note(s))" % (
        comparison.cell_mismatch_count,
        comparison.error_count,
        comparison.note_count,
    )


def render_json(comparison: Comparison) -> str:
    """Render the machine-readable report as a JSON document."""
    return json.dumps(to_dict(comparison), indent=2, sort_keys=True)


def to_dict(comparison: Comparison) -> Dict[str, Any]:
    """The JSON report as plain Python data (stable schema, version 1)."""
    return {
        "report_version": REPORT_VERSION,
        "ok": comparison.ok,
        "golden": comparison.golden_source,
        "actual": comparison.actual_source,
        "aligned_by": comparison.matched_by,
        "rows": {
            "golden": comparison.n_rows_golden,
            "actual": comparison.n_rows_actual,
            "compared": comparison.n_rows_compared,
        },
        "columns_compared": comparison.n_columns_compared,
        "issues": [
            {
                "kind": issue.kind,
                "severity": issue.severity,
                "message": issue.message,
            }
            for issue in comparison.issues
        ],
        "cell_diffs": {
            "total": comparison.cell_mismatch_count,
            "by_column": [
                {
                    "column": column.name,
                    "dtype": column.dtype,
                    "compared": column.compared,
                    "mismatches": column.mismatches,
                    "tolerance": (
                        {"rtol": column.tolerance.rtol, "atol": column.tolerance.atol}
                        if column.tolerance is not None
                        else None
                    ),
                    "examples": [
                        {
                            "row": example.row_label,
                            "golden": example.golden,
                            "actual": example.actual,
                            "detail": example.detail,
                        }
                        for example in column.examples
                    ],
                }
                for column in comparison.columns
                if column.mismatches
            ],
        },
    }

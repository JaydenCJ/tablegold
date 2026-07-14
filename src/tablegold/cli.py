"""The ``tablegold`` command-line interface.

Subcommands:

- ``diff GOLDEN ACTUAL`` — compare two tables; exit 0 on match, 1 on
  mismatch, 2 on configuration or read errors. ``--format json`` emits the
  machine report.
- ``show FILE`` — print the inferred schema (columns, dtypes, missing
  counts) of one table.
- ``bless ACTUAL GOLDEN`` — write the actual table as a canonical golden.

The CLI is a thin shell: every behavior here is a one-line call into the
library, so scripts and test suites always agree with the command line.
"""

from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional, Sequence

from . import __version__
from .compare import CompareConfig, compare
from .errors import TableGoldError
from .report import render_json, render_text
from .table import Table
from .tolerance import Tolerance, parse_tolerance_spec
from .golden import bless

EXIT_MATCH = 0
EXIT_MISMATCH = 1
EXIT_ERROR = 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tablegold",
        description="Golden-file testing for CSV and tabular data: "
        "numeric tolerance, column order, dtype checks.",
    )
    parser.add_argument(
        "--version", action="version", version="tablegold %s" % __version__
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    diff = subparsers.add_parser(
        "diff", help="compare an actual table against a golden table"
    )
    diff.add_argument("golden", help="path to the golden CSV/TSV file")
    diff.add_argument("actual", help="path to the actual CSV/TSV file")
    diff.add_argument(
        "--rtol", type=float, default=None, help="relative tolerance (default 1e-9)"
    )
    diff.add_argument(
        "--atol", type=float, default=None, help="absolute tolerance (default 1e-12)"
    )
    diff.add_argument(
        "--tol",
        action="append",
        default=[],
        metavar="COL:RTOL[:ATOL]",
        help="per-column tolerance override (repeatable)",
    )
    diff.add_argument(
        "--key",
        default=None,
        metavar="COLS",
        help="comma-separated key columns; rows are aligned by key, not position",
    )
    diff.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="COLS",
        help="comma-separated columns to exclude from the comparison (repeatable)",
    )
    diff.add_argument(
        "--strict-column-order",
        action="store_true",
        help="treat a changed column order as an error, not a note",
    )
    diff.add_argument(
        "--strict-dtypes",
        action="store_true",
        help="require identical inferred dtypes (no int/float widening)",
    )
    diff.add_argument(
        "--allow-extra-columns",
        action="store_true",
        help="extra columns in the actual table are a note, not an error",
    )
    diff.add_argument(
        "--nan-differs",
        action="store_true",
        help="treat NaN as unequal to NaN (default: NaN == NaN)",
    )
    diff.add_argument(
        "--max-examples",
        type=int,
        default=5,
        metavar="N",
        help="mismatch examples to show per column (default 5)",
    )
    diff.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="report format (default text)",
    )
    diff.add_argument(
        "--delimiter",
        default=None,
        help=r"field delimiter for both files (default: sniffed; use '\t' for tabs)",
    )

    show = subparsers.add_parser("show", help="print a table's inferred schema")
    show.add_argument("file", help="path to a CSV/TSV file")
    show.add_argument("--delimiter", default=None, help="field delimiter (default: sniffed)")

    bless_cmd = subparsers.add_parser(
        "bless", help="write an actual table as the canonical golden file"
    )
    bless_cmd.add_argument("actual", help="path to the actual CSV/TSV file")
    bless_cmd.add_argument("golden", help="destination golden path")
    bless_cmd.add_argument(
        "--delimiter", default=None, help="field delimiter (default: sniffed)"
    )
    return parser


def _decode_delimiter(raw: Optional[str]) -> Optional[str]:
    if raw in (r"\t", "tab", "TAB"):
        return "\t"
    return raw


def _split_columns(specs: Sequence[str]) -> List[str]:
    columns: List[str] = []
    for spec in specs:
        columns.extend(name.strip() for name in spec.split(",") if name.strip())
    return columns


def _config_from_args(args: argparse.Namespace) -> CompareConfig:
    column_tolerances: Dict[str, Tolerance] = {}
    for spec in args.tol:
        column, rtol, atol = parse_tolerance_spec(spec)
        column_tolerances[column] = Tolerance(
            rtol=rtol, atol=atol, nan_equal=not args.nan_differs
        )
    options = {}
    if args.rtol is not None:
        options["rtol"] = args.rtol
    if args.atol is not None:
        options["atol"] = args.atol
    return CompareConfig(
        nan_equal=not args.nan_differs,
        column_tolerances=column_tolerances,
        key=_split_columns([args.key] if args.key else []),
        ignore_columns=_split_columns(args.ignore),
        strict_column_order=args.strict_column_order,
        strict_dtypes=args.strict_dtypes,
        allow_extra_columns=args.allow_extra_columns,
        max_examples=args.max_examples,
        **options,
    )


def _cmd_diff(args: argparse.Namespace) -> int:
    config = _config_from_args(args)
    comparison = compare(
        args.golden,
        args.actual,
        config=config,
        delimiter=_decode_delimiter(args.delimiter),
    )
    if args.format == "json":
        print(render_json(comparison))
    else:
        print(render_text(comparison))
    return EXIT_MATCH if comparison.ok else EXIT_MISMATCH


def _cmd_show(args: argparse.Namespace) -> int:
    table = Table.from_csv(args.file, delimiter=_decode_delimiter(args.delimiter))
    schema = table.schema()
    print("file: %s" % table.source)
    print("rows: %d" % table.n_rows)
    print("columns: %d" % table.n_columns)
    width = max(len(name) for name in table.columns)
    for name in table.columns:
        values = table.raw_column(name)
        present = sum(1 for raw in values if raw.strip() != "")
        print(
            "  %-*s  %-9s %d/%d non-empty"
            % (width, name, schema[name], present, table.n_rows)
        )
    return EXIT_MATCH


def _cmd_bless(args: argparse.Namespace) -> int:
    table = bless(
        args.actual, args.golden, delimiter=_decode_delimiter(args.delimiter)
    )
    print(
        "blessed %s (%d row(s), %d column(s))"
        % (args.golden, table.n_rows, table.n_columns)
    )
    return EXIT_MATCH


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point; returns the process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return EXIT_ERROR
    handlers = {"diff": _cmd_diff, "show": _cmd_show, "bless": _cmd_bless}
    try:
        return handlers[args.command](args)
    except TableGoldError as exc:
        print("tablegold: error: %s" % exc, file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

"""tablegold — golden-file testing for CSV and tabular data.

Tolerance-aware, column-semantic diffing: numeric noise below your chosen
tolerance never fails a build, while schema drift (columns, dtypes, keys)
always does. Standard library only.

Public API::

    from tablegold import assert_matches_golden, compare, bless, Table

See the README for the full quickstart.
"""

from __future__ import annotations

from .compare import (
    CellDiff,
    ColumnResult,
    CompareConfig,
    Comparison,
    Issue,
    compare,
)
from .errors import (
    ConfigError,
    GoldenMismatchError,
    GoldenMissingError,
    TableGoldError,
    TableReadError,
)
from .golden import assert_matches_golden, bless, update_requested
from .report import render_json, render_text, to_dict
from .table import Table
from .tolerance import Tolerance, floats_close

__version__ = "0.1.0"

__all__ = [
    "CellDiff",
    "ColumnResult",
    "CompareConfig",
    "Comparison",
    "ConfigError",
    "GoldenMismatchError",
    "GoldenMissingError",
    "Issue",
    "Table",
    "TableGoldError",
    "TableReadError",
    "Tolerance",
    "__version__",
    "assert_matches_golden",
    "bless",
    "compare",
    "floats_close",
    "render_json",
    "render_text",
    "to_dict",
    "update_requested",
]

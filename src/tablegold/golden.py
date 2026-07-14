"""Golden-file lifecycle: assert, bless, update.

The one-call API for test suites is :func:`assert_matches_golden`:

- golden exists → compare, raise :class:`GoldenMismatchError` on drift
  (an ``AssertionError`` subclass, so pytest prints the full report);
- golden missing → raise :class:`GoldenMissingError` with a hint, unless
  update mode is on, in which case the golden is written (blessed);
- update mode → re-bless the golden from the actual data, then verify the
  written file round-trips.

Update mode is enabled by ``update=True`` or the ``TABLEGOLD_UPDATE``
environment variable (``1``/``true``/``yes``/``on``), so a whole suite can
be re-blessed with ``TABLEGOLD_UPDATE=1 pytest`` without touching code.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional, Union

from .compare import Comparison, compare
from .errors import GoldenMismatchError, GoldenMissingError
from .report import render_text
from .table import Table, TableLike, as_table

UPDATE_ENV_VAR = "TABLEGOLD_UPDATE"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


def update_requested(explicit: Optional[bool] = None) -> bool:
    """Resolve update mode: an explicit argument beats the environment."""
    if explicit is not None:
        return explicit
    return os.environ.get(UPDATE_ENV_VAR, "").strip().lower() in _TRUTHY


def bless(
    actual: TableLike,
    golden_path: Union[str, "os.PathLike[str]"],
    delimiter: Optional[str] = None,
) -> Table:
    """Write *actual* to *golden_path* in canonical form and return it.

    Canonical means LF newlines, minimal quoting, UTF-8 — so re-blessing
    on any platform produces byte-identical goldens for identical data.
    """
    table = as_table(actual, delimiter=delimiter)
    table.write_csv(golden_path)
    return table


def assert_matches_golden(
    actual: TableLike,
    golden_path: Union[str, "os.PathLike[str]"],
    *,
    update: Optional[bool] = None,
    delimiter: Optional[str] = None,
    **compare_options: Any,
) -> Comparison:
    """Assert that *actual* matches the golden file at *golden_path*.

    Returns the :class:`~tablegold.compare.Comparison` on success. Any
    keyword accepted by :class:`~tablegold.compare.CompareConfig` can be
    passed through, e.g. ``rtol=1e-6, key=["id"]``.
    """
    golden_path = Path(golden_path)
    if update_requested(update):
        bless(actual, golden_path, delimiter=delimiter)
    elif not golden_path.exists():
        raise GoldenMissingError(
            "golden file %s does not exist; run with %s=1 (or update=True) "
            "to create it from the actual output" % (golden_path, UPDATE_ENV_VAR)
        )
    comparison = compare(
        golden_path, actual, delimiter=delimiter, **compare_options
    )
    if not comparison.ok:
        raise GoldenMismatchError(render_text(comparison), comparison)
    return comparison

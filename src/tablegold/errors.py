"""Exception hierarchy for tablegold.

Every exception raised on purpose by this package derives from
:class:`TableGoldError`, so callers can catch one type at the boundary.
:class:`GoldenMismatchError` additionally derives from ``AssertionError``
so pytest renders it as a plain test failure with the full diff report.
"""

from __future__ import annotations


class TableGoldError(Exception):
    """Base class for all tablegold errors."""


class TableReadError(TableGoldError):
    """An input file or in-memory payload could not be read as a table."""


class ConfigError(TableGoldError):
    """A comparison was configured with contradictory or invalid options."""


class GoldenMissingError(TableGoldError):
    """The golden file does not exist and update mode is off."""


class GoldenMismatchError(TableGoldError, AssertionError):
    """The actual table does not match the golden table.

    The full human-readable report is the exception message; the structured
    result is available as :attr:`comparison`.
    """

    def __init__(self, message: str, comparison: object = None) -> None:
        super().__init__(message)
        self.comparison = comparison

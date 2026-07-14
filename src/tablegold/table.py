"""The in-memory table model and CSV/TSV I/O.

A :class:`Table` keeps every cell as its raw string, exactly as the file
had it; dtype inference and parsing happen on top of the raw layer. That
split is what lets tablegold report "``1.50`` vs ``1.5`` — equal as floats"
instead of silently rewriting anybody's data.

Reading is strict: duplicate or empty header names and ragged rows raise
:class:`~tablegold.errors.TableReadError` with the offending line number,
because a golden test built on a malformed file asserts nothing.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import os
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from . import dtypes
from .errors import TableReadError

#: Delimiters tried by the sniffer, in priority order for ties.
CANDIDATE_DELIMITERS = (",", "\t", ";", "|")

TableLike = Union["Table", str, "os.PathLike[str]", Sequence[Any]]


def sniff_delimiter(header_line: str) -> str:
    """Pick the candidate delimiter that occurs most often in the header."""
    best, best_count = ",", 0
    for candidate in CANDIDATE_DELIMITERS:
        count = header_line.count(candidate)
        if count > best_count:
            best, best_count = candidate, count
    return best


def format_cell(value: Any) -> str:
    """Convert a Python value to its canonical raw-cell string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return repr(value)  # shortest string that round-trips
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    return str(value)


class Table:
    """An immutable-by-convention table of raw string cells."""

    def __init__(
        self,
        columns: Sequence[str],
        rows: Sequence[Sequence[str]],
        source: str = "<memory>",
    ) -> None:
        self.columns: List[str] = list(columns)
        self.rows: List[List[str]] = [list(row) for row in rows]
        self.source = source
        self._schema: Optional[Dict[str, str]] = None
        self._validate()

    # -- construction --------------------------------------------------

    @classmethod
    def from_csv(
        cls,
        path: Union[str, "os.PathLike[str]"],
        delimiter: Optional[str] = None,
    ) -> "Table":
        """Read a delimited text file (CSV/TSV; delimiter sniffed by default)."""
        path = Path(path)
        try:
            # utf-8-sig transparently drops a BOM written by spreadsheets.
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise TableReadError("cannot read %s: %s" % (path, exc.strerror or exc)) from exc
        except UnicodeDecodeError as exc:
            raise TableReadError("%s is not valid UTF-8: %s" % (path, exc)) from exc
        return cls.from_text(text, delimiter=delimiter, source=str(path))

    @classmethod
    def from_text(
        cls,
        text: str,
        delimiter: Optional[str] = None,
        source: str = "<text>",
    ) -> "Table":
        """Parse delimited text; the first record is the header."""
        if not text.strip():
            raise TableReadError("%s is empty (no header row)" % source)
        if delimiter is None:
            delimiter = sniff_delimiter(text.splitlines()[0])
        reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
        records = [row for row in reader if row]  # skip blank records
        header = [name.strip() for name in records[0]]
        return cls(header, records[1:], source=source)

    @classmethod
    def from_rows(
        cls,
        rows: Sequence[Any],
        columns: Optional[Sequence[str]] = None,
        source: str = "<memory>",
    ) -> "Table":
        """Build a table from ``list[dict]`` or ``list[sequence]`` data.

        With dict rows the column order comes from the first row (or the
        explicit *columns*); every row must supply exactly those keys.
        Values are converted with :func:`format_cell`, so floats become
        their shortest round-trip representation.
        """
        rows = list(rows)
        if rows and isinstance(rows[0], Mapping):
            if columns is None:
                columns = list(rows[0].keys())
            cells = []
            for index, row in enumerate(rows, start=1):
                extra = set(row) - set(columns)
                if extra:
                    raise TableReadError(
                        "row %d has keys not in the header: %s"
                        % (index, ", ".join(sorted(extra)))
                    )
                cells.append([format_cell(row.get(name)) for name in columns])
        else:
            if columns is None:
                if not rows:
                    raise TableReadError(
                        "cannot infer columns from zero rows; pass columns="
                    )
                raise TableReadError("columns= is required for sequence rows")
            cells = [[format_cell(value) for value in row] for row in rows]
        return cls(list(columns), cells, source=source)

    # -- validation -----------------------------------------------------

    def _validate(self) -> None:
        if not self.columns:
            raise TableReadError("%s has no columns" % self.source)
        seen: Dict[str, int] = {}
        for name in self.columns:
            if not name:
                raise TableReadError("%s has an empty column name" % self.source)
            if name in seen:
                raise TableReadError("%s has a duplicate column name: %r" % (self.source, name))
            seen[name] = 1
        width = len(self.columns)
        for index, row in enumerate(self.rows, start=1):  # 1-based data rows
            if len(row) != width:
                raise TableReadError(
                    "%s data row %d has %d fields, expected %d"
                    % (self.source, index, len(row), width)
                )

    # -- accessors ------------------------------------------------------

    @property
    def n_rows(self) -> int:
        return len(self.rows)

    @property
    def n_columns(self) -> int:
        return len(self.columns)

    def column_index(self, name: str) -> int:
        try:
            return self.columns.index(name)
        except ValueError:
            raise KeyError(name) from None

    def raw_column(self, name: str) -> List[str]:
        """All raw cell strings of one column, top to bottom."""
        index = self.column_index(name)
        return [row[index] for row in self.rows]

    def schema(self) -> Dict[str, str]:
        """Inferred dtype per column, in column order (cached)."""
        if self._schema is None:
            self._schema = {
                name: dtypes.infer_dtype(self.raw_column(name)) for name in self.columns
            }
        return self._schema

    def key_for_row(self, row: Sequence[str], key_indexes: Sequence[int]) -> tuple:
        return tuple(row[i].strip() for i in key_indexes)

    # -- output ---------------------------------------------------------

    def to_csv_text(self, delimiter: str = ",") -> str:
        """Serialize canonically: LF newlines, minimal quoting."""
        buffer = io.StringIO()
        writer = csv.writer(
            buffer, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL
        )
        writer.writerow(self.columns)
        writer.writerows(self.rows)
        return buffer.getvalue()

    def write_csv(
        self, path: Union[str, "os.PathLike[str]"], delimiter: str = ","
    ) -> None:
        """Write the canonical form, creating parent directories."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_csv_text(delimiter=delimiter), encoding="utf-8")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "Table(%d row(s) x %d column(s) from %s)" % (
            self.n_rows,
            self.n_columns,
            self.source,
        )


def as_table(value: TableLike, delimiter: Optional[str] = None) -> Table:
    """Coerce a path, Table, or row payload into a :class:`Table`."""
    if isinstance(value, Table):
        return value
    if isinstance(value, (str, os.PathLike)):
        return Table.from_csv(value, delimiter=delimiter)
    if isinstance(value, Sequence):
        return Table.from_rows(value)
    raise TableReadError(
        "cannot interpret %r as a table (expected a path, Table, or rows)"
        % type(value).__name__
    )

"""Dtype inference and value parsing for table cells.

Every cell arrives as a string (that is what CSV gives you). This module
decides, per column, what those strings *mean* — so that ``1.50`` equals
``1.5``, ``2024-01-02T03:04:05Z`` equals ``2024-01-02T03:04:05+00:00``,
and ``true`` is a boolean rather than four characters.

The dtype lattice, most specific first:

    bool > int > float > date > datetime > string

Column inference rules (deliberately conservative):

- a column mixing ``int`` and ``float`` values is ``float``;
- any other mix (``bool`` + ``int``, ``date`` + ``datetime``, anything +
  ``string``) degrades to ``string`` — guessing further would hide bugs;
- a column whose values are all missing has the special dtype ``empty``,
  which is compatible with every other dtype.

Missing values: the empty string and the case-insensitive tokens ``NA``,
``N/A``, ``NULL`` and ``None`` are treated as missing in every dtype.
``NaN`` is *not* missing — it parses as the IEEE-754 float NaN.
"""

from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Iterable, Optional, Tuple

BOOL = "bool"
INT = "int"
FLOAT = "float"
DATE = "date"
DATETIME = "datetime"
STRING = "string"
EMPTY = "empty"

#: All dtypes a column can have, most specific first.
ALL_DTYPES = (BOOL, INT, FLOAT, DATE, DATETIME, STRING, EMPTY)

#: Case-insensitive tokens (after stripping whitespace) treated as missing.
MISSING_TOKENS = frozenset({"", "na", "n/a", "null", "none"})

_INT_RE = re.compile(r"^[+-]?[0-9]+$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"  # date, separator, HH:MM
    r"(?::\d{2}(?:\.\d{1,6})?)?"  # optional :SS[.ffffff]
    r"(?:Z|[+-]\d{2}:?\d{2})?$"  # optional zone: Z, +HH:MM or +HHMM
)


def is_missing(raw: str) -> bool:
    """Return True when *raw* denotes a missing value."""
    return raw.strip().lower() in MISSING_TOKENS


def _try_float(text: str) -> Optional[float]:
    # Underscores ("1_000") are valid Python literals but not tabular data.
    if "_" in text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _normalize_datetime(text: str) -> str:
    """Rewrite an ISO-8601-ish string so ``datetime.fromisoformat`` accepts
    it on every supported Python version (3.9 needs exact fraction widths
    and rejects ``Z`` and ``+HHMM`` offsets)."""
    text = text.strip().replace(" ", "T")
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    # +HHMM -> +HH:MM
    match = re.search(r"([+-]\d{2})(\d{2})$", text)
    if match:
        text = text[: match.start()] + match.group(1) + ":" + match.group(2)
    # Pad fractional seconds to 6 digits for Python < 3.11.
    match = re.search(r"\.(\d{1,6})(?=$|[+-])", text)
    if match and len(match.group(1)) < 6:
        padded = match.group(1).ljust(6, "0")
        text = text[: match.start(1)] + padded + text[match.end(1) :]
    return text


def parse_datetime(text: str) -> Optional[_dt.datetime]:
    """Parse a strict ISO-8601 datetime; return None when it is not one."""
    if not _DATETIME_RE.match(text.strip()):
        return None
    try:
        return _dt.datetime.fromisoformat(_normalize_datetime(text))
    except ValueError:
        return None


def parse_date(text: str) -> Optional[_dt.date]:
    """Parse a strict ``YYYY-MM-DD`` date; return None when it is not one."""
    if not _DATE_RE.match(text.strip()):
        return None
    try:
        return _dt.date.fromisoformat(text.strip())
    except ValueError:
        return None


def classify_value(raw: str) -> Optional[str]:
    """Classify one cell into the most specific dtype.

    Returns None for missing values — they carry no dtype information.
    """
    if is_missing(raw):
        return None
    text = raw.strip()
    if text.lower() in ("true", "false"):
        return BOOL
    if _INT_RE.match(text):
        return INT
    if _try_float(text) is not None:
        return FLOAT
    if parse_date(text) is not None:
        return DATE
    if parse_datetime(text) is not None:
        return DATETIME
    return STRING


def infer_dtype(values: Iterable[str]) -> str:
    """Infer a column dtype from its raw cell values."""
    seen = set()
    for raw in values:
        kind = classify_value(raw)
        if kind is not None:
            seen.add(kind)
            if kind == STRING:
                break  # cannot get less specific than string
    if not seen:
        return EMPTY
    if len(seen) == 1:
        return next(iter(seen))
    if seen <= {INT, FLOAT}:
        return FLOAT
    return STRING


def parse_value(raw: str, dtype: str) -> Any:
    """Parse one cell under a column dtype.

    Missing values parse to None in every dtype. When a value does not fit
    the dtype (possible when a column is compared under a *unified* dtype),
    the raw string is returned unchanged — the comparison layer then reports
    a plain value mismatch instead of crashing.
    """
    if is_missing(raw):
        return None
    text = raw.strip()
    if dtype == BOOL:
        lowered = text.lower()
        if lowered in ("true", "false"):
            return lowered == "true"
    elif dtype == INT:
        if _INT_RE.match(text):
            return int(text)
    elif dtype == FLOAT:
        number = _try_float(text)
        if number is not None:
            return number
    elif dtype == DATE:
        parsed_date = parse_date(text)
        if parsed_date is not None:
            return parsed_date
    elif dtype == DATETIME:
        parsed_dt = parse_datetime(text)
        if parsed_dt is not None:
            return parsed_dt
    else:  # STRING or EMPTY: the raw text is the value, unstripped.
        return raw
    return raw


def unify_dtypes(golden: str, actual: str) -> Tuple[Optional[str], Optional[str]]:
    """Decide how two column dtypes are compared.

    Returns ``(unified_dtype, note)``. ``unified_dtype`` is None when the
    dtypes are incompatible (a schema error). ``note`` is a human-readable
    remark for benign widenings such as int vs float.
    """
    if golden == actual:
        return golden, None
    if golden == EMPTY:
        return actual, None
    if actual == EMPTY:
        return golden, None
    if {golden, actual} == {INT, FLOAT}:
        return FLOAT, "compared as float (golden is %s, actual is %s)" % (golden, actual)
    return None, None

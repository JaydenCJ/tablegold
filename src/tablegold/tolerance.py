"""Numeric tolerance rules.

The closeness test is symmetric (unlike ``numpy.isclose``, which scales the
relative term by ``|b|`` only, so ``isclose(a, b) != isclose(b, a)`` near the
boundary):

    |a - b| <= max(atol, rtol * max(|a|, |b|))

Special values are handled explicitly:

- NaN equals NaN when ``nan_equal`` is on (the default — golden testing
  wants "the pipeline still produces NaN here" to be a stable assertion);
- infinities are equal only to the same-signed infinity;
- an infinity is never close to any finite number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

from .errors import ConfigError

DEFAULT_RTOL = 1e-9
DEFAULT_ATOL = 1e-12


@dataclass(frozen=True)
class Tolerance:
    """Per-column numeric tolerance."""

    rtol: float = DEFAULT_RTOL
    atol: float = DEFAULT_ATOL
    nan_equal: bool = True

    def __post_init__(self) -> None:
        for field_name in ("rtol", "atol"):
            value = getattr(self, field_name)
            if not isinstance(value, (int, float)) or math.isnan(value) or value < 0:
                raise ConfigError(
                    "%s must be a non-negative number, got %r" % (field_name, value)
                )

    def describe(self) -> str:
        """Short human-readable form used in reports."""
        return "rtol=%g, atol=%g" % (self.rtol, self.atol)


def floats_close(a: float, b: float, tol: Tolerance) -> bool:
    """Return True when *a* and *b* are equal within *tol*."""
    a = float(a)
    b = float(b)
    if math.isnan(a) or math.isnan(b):
        return math.isnan(a) and math.isnan(b) and tol.nan_equal
    if a == b:  # covers same-signed infinities and exact matches
        return True
    if math.isinf(a) or math.isinf(b):
        return False
    return abs(a - b) <= max(tol.atol, tol.rtol * max(abs(a), abs(b)))


def diff_magnitudes(a: float, b: float) -> Tuple[float, float]:
    """Return ``(absolute_diff, relative_diff)`` for reporting.

    The relative diff is against ``max(|a|, |b|)``; when either side is NaN
    or infinite both magnitudes are reported as NaN/inf so the report stays
    honest instead of inventing a number.
    """
    a = float(a)
    b = float(b)
    if math.isnan(a) or math.isnan(b):
        return math.nan, math.nan
    if a == b:
        return 0.0, 0.0
    if math.isinf(a) or math.isinf(b):
        return math.inf, math.inf
    absolute = abs(a - b)
    scale = max(abs(a), abs(b))
    return absolute, absolute / scale if scale else math.inf


def parse_tolerance_spec(spec: str) -> Tuple[str, float, float]:
    """Parse a CLI per-column spec ``COLUMN:RTOL[:ATOL]``.

    Returns ``(column, rtol, atol)``; atol defaults to :data:`DEFAULT_ATOL`.
    """
    parts = spec.rsplit(":", 2)
    if len(parts) >= 2:
        # Distinguish COL:RTOL from COL:RTOL:ATOL — the column name itself
        # may contain a colon, so parse numbers from the right.
        try:
            if len(parts) == 3:
                return parts[0], _non_negative(parts[1]), _non_negative(parts[2])
        except ValueError:
            # Not two trailing numbers; retry as a single trailing number.
            parts = spec.rsplit(":", 1)
        try:
            column = ":".join(parts[:-1])
            return column, _non_negative(parts[-1]), DEFAULT_ATOL
        except ValueError:
            pass
    raise ConfigError(
        "invalid --tol spec %r (expected COLUMN:RTOL or COLUMN:RTOL:ATOL)" % spec
    )


def _non_negative(text: str) -> float:
    value = float(text)
    if math.isnan(value) or value < 0:
        raise ValueError(text)
    return value

"""Dtype inference and value parsing.

These tests pin down the semantic layer: what a raw CSV cell *means*.
Getting this wrong silently changes what a golden test asserts, so the
edge cases (missing tokens, NaN-vs-NA, mixed columns, timezone forms)
each get explicit coverage.
"""

from __future__ import annotations

import datetime as dt
import math

from tablegold.dtypes import (
    BOOL,
    DATE,
    DATETIME,
    EMPTY,
    FLOAT,
    INT,
    STRING,
    classify_value,
    infer_dtype,
    is_missing,
    parse_value,
    unify_dtypes,
)


class TestClassifyValue:
    def test_numbers_with_signs_and_scientific_notation(self):
        assert classify_value("42") == INT
        assert classify_value("-7") == INT
        assert classify_value("+0") == INT
        assert classify_value("1.5") == FLOAT
        assert classify_value("-2.5e-3") == FLOAT
        assert classify_value("1e10") == FLOAT

    def test_nan_and_infinities_are_floats_not_missing(self):
        # "NaN" must stay a float value: a pipeline emitting NaN where the
        # golden has a number is a real regression, not a missing cell.
        assert classify_value("NaN") == FLOAT
        assert classify_value("inf") == FLOAT
        assert classify_value("-Infinity") == FLOAT
        assert not is_missing("nan")

    def test_booleans_missing_tokens_and_whitespace(self):
        # 0/1 columns stay numeric; guessing bool would break tolerance math.
        assert classify_value("true") == BOOL
        assert classify_value("FALSE") == BOOL
        assert classify_value("0") == INT
        assert classify_value("1") == INT
        for token in ("", "NA", "n/a", "NULL", "None", "  "):
            assert classify_value(token) is None, token
            assert is_missing(token), token
        assert classify_value("  42 ") == INT  # padding is ignored

    def test_iso_dates_datetimes_and_lookalikes(self):
        assert classify_value("2026-07-01") == DATE
        assert classify_value("2026-07-01T09:00:00") == DATETIME
        assert classify_value("2026-07-01 09:00:00.123456+09:00") == DATETIME
        assert classify_value("07/01/2026") == STRING  # not ISO
        assert classify_value("2026-13-40") == STRING  # right shape, bad date
        assert classify_value("1_000") == STRING  # Python literal, not data


class TestInferDtype:
    def test_uniform_empty_and_numeric_widening(self):
        assert infer_dtype(["1", "2", "3"]) == INT
        assert infer_dtype(["", "NA", "null"]) == EMPTY
        assert infer_dtype(["1", "2.5", "3"]) == FLOAT  # int + float -> float
        # Missing values never affect the inferred dtype.
        assert infer_dtype(["1.5", "", "NA", "2.5"]) == FLOAT

    def test_unsafe_mixes_degrade_to_string(self):
        # Guessing "1 means true" or "midnight was implied" would be a lie.
        assert infer_dtype(["1", "2", "oops"]) == STRING
        assert infer_dtype(["true", "1"]) == STRING
        assert infer_dtype(["2026-07-01", "2026-07-01T09:00:00"]) == STRING


class TestParseValue:
    def test_datetime_timezone_and_fraction_normalization(self):
        # Z, +00:00 and +0000-style offsets must all mean the same instant.
        z_form = parse_value("2026-07-01T09:00:00Z", DATETIME)
        assert z_form == parse_value("2026-07-01T09:00:00+00:00", DATETIME)
        compact = parse_value("2026-07-01T18:00:00+0900", DATETIME)
        assert compact == parse_value("2026-07-01T18:00:00+09:00", DATETIME)
        fractional = parse_value("2026-07-01T09:00:00.5", DATETIME)
        assert fractional == dt.datetime(2026, 7, 1, 9, 0, 0, 500000)

    def test_naive_and_aware_datetimes_do_not_compare_equal(self):
        naive = parse_value("2026-07-01T09:00:00", DATETIME)
        aware = parse_value("2026-07-01T09:00:00Z", DATETIME)
        assert naive != aware  # == between them is False, never an exception

    def test_missing_strings_nan_and_the_fallback_path(self):
        # Missing tokens parse to None under every dtype.
        for dtype in (BOOL, INT, FLOAT, DATE, DATETIME, STRING):
            assert parse_value("NA", dtype) is None, dtype
        # String cells keep their raw text, unstripped.
        assert parse_value("  spaced  ", STRING) == "  spaced  "
        # NaN is a real float value.
        nan_value = parse_value("nan", FLOAT)
        assert isinstance(nan_value, float) and math.isnan(nan_value)
        # Defensive path: a value that does not fit the unified dtype must
        # surface as a mismatch, not crash the comparison.
        assert parse_value("oops", FLOAT) == "oops"


def test_unify_dtypes_compatibility_matrix():
    # Identical dtypes and the empty column are always compatible.
    assert unify_dtypes(INT, INT) == (INT, None)
    assert unify_dtypes(EMPTY, FLOAT)[0] == FLOAT
    assert unify_dtypes(DATE, EMPTY)[0] == DATE
    # int/float widening is allowed, but flagged with a note.
    unified, note = unify_dtypes(INT, FLOAT)
    assert unified == FLOAT
    assert note is not None and "float" in note
    # Everything else is incompatible -> a schema error upstream.
    assert unify_dtypes(INT, STRING) == (None, None)
    assert unify_dtypes(DATE, DATETIME) == (None, None)

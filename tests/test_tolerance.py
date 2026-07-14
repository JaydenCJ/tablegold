"""Numeric tolerance semantics.

The closeness predicate is the reason tablegold exists: float noise below
the threshold must pass, anything above must fail, and the special values
(NaN, infinities, signed zero) must behave predictably in CI.
"""

from __future__ import annotations

import math

import pytest

from tablegold.errors import ConfigError
from tablegold.tolerance import (
    DEFAULT_ATOL,
    Tolerance,
    diff_magnitudes,
    floats_close,
    parse_tolerance_spec,
)


class TestFloatsClose:
    def test_rtol_separates_noise_from_drift(self):
        tol = Tolerance(rtol=1e-9, atol=0.0)
        assert floats_close(1e6, 1e6 * (1 + 1e-10), tol)  # below: passes
        assert not floats_close(1e6, 1e6 * (1 + 1e-8), tol)  # above: fails

    def test_symmetry_at_the_boundary(self):
        # numpy.isclose is asymmetric near the edge; tablegold must not be —
        # a golden test should not change verdict when sides are swapped.
        tol = Tolerance(rtol=1e-6, atol=0.0)
        a, b = 1.0, 1.0000005
        assert floats_close(a, b, tol) == floats_close(b, a, tol)

    def test_atol_dominates_near_zero_and_exact_matches_need_no_slack(self):
        # Relative tolerance is useless around 0; atol covers the residue.
        assert floats_close(0.0, 5e-13, Tolerance(rtol=1e-9, atol=1e-12))
        assert not floats_close(0.0, 5e-12, Tolerance(rtol=1e-9, atol=1e-12))
        zero_tol = Tolerance(rtol=0.0, atol=0.0)
        assert floats_close(1.5, 1.5, zero_tol)
        assert floats_close(0.0, -0.0, zero_tol)  # signed zero is equal

    def test_nan_semantics(self):
        assert floats_close(math.nan, math.nan, Tolerance())  # default: equal
        assert not floats_close(math.nan, math.nan, Tolerance(nan_equal=False))
        assert not floats_close(math.nan, 0.0, Tolerance())  # never a number

    def test_infinity_semantics(self):
        assert floats_close(math.inf, math.inf, Tolerance())
        assert not floats_close(math.inf, -math.inf, Tolerance())
        # Without the explicit guard, inf - big would be inf <= inf -> True.
        assert not floats_close(math.inf, 1e308, Tolerance(rtol=1.0, atol=1e308))


def test_diff_magnitudes_reports_honest_numbers():
    absolute, relative = diff_magnitudes(100.0, 101.0)
    assert absolute == pytest.approx(1.0)
    assert relative == pytest.approx(1.0 / 101.0)
    # Special values report NaN/inf rather than inventing a magnitude.
    absolute, relative = diff_magnitudes(math.nan, 1.0)
    assert math.isnan(absolute) and math.isnan(relative)
    absolute, relative = diff_magnitudes(math.inf, 1.0)
    assert math.isinf(absolute) and math.isinf(relative)


class TestParseToleranceSpec:
    def test_valid_specs_including_colons_in_column_names(self):
        assert parse_tolerance_spec("price:1e-6") == ("price", 1e-6, DEFAULT_ATOL)
        assert parse_tolerance_spec("price:1e-6:0.01") == ("price", 1e-6, 0.01)
        # Numbers are parsed from the right, so odd column names survive.
        assert parse_tolerance_spec("ns:price:1e-6") == ("ns:price", 1e-6, DEFAULT_ATOL)

    def test_malformed_specs_and_tolerances_are_config_errors(self):
        for bad in ("price", "price:", "price:x", "price:-1"):
            with pytest.raises(ConfigError):
                parse_tolerance_spec(bad)
        with pytest.raises(ConfigError):
            Tolerance(rtol=-1e-9)
        with pytest.raises(ConfigError):
            Tolerance(atol=math.nan)

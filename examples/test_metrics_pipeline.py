"""Example pytest suite: guard the demo pipeline with the tablegold fixture.

These run as part of the repository test suite (see ``testpaths`` in
pyproject.toml) against the committed golden in ``examples/goldens/`` —
proof that the fixture, the golden, and the demo all agree.

Re-bless after an intended metrics change:

    TABLEGOLD_UPDATE=1 pytest examples/
"""

from __future__ import annotations

import pytest

from pipeline_demo import summarize, summarize_discounted, summarize_sorted
from tablegold import GoldenMismatchError


def test_daily_metrics_match_the_committed_golden(tablegold):
    tablegold.check(summarize(), name="daily_metrics.csv", key=["region"])


def test_reimplementation_noise_stays_within_tolerance(tablegold):
    # v1.1 folds the same numbers in a different order; the golden still
    # holds. update=False: only the v1 test above may re-bless this golden.
    tablegold.check(
        summarize_sorted(), name="daily_metrics.csv", key=["region"], update=False
    )


def test_discount_regression_is_caught(tablegold):
    with pytest.raises(GoldenMismatchError) as excinfo:
        tablegold.check(
            summarize_discounted(),
            name="daily_metrics.csv",
            key=["region"],
            update=False,
        )
    assert "column revenue [float]" in str(excinfo.value)

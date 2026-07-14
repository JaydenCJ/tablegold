"""pytest integration: the ``tablegold`` fixture.

Request the fixture and call ``check`` with whatever your code produced —
a path, a ``Table``, or plain ``list[dict]`` rows::

    def test_report(tablegold):
        rows = build_report()
        tablegold.check(rows, key=["id"], rtol=1e-6)

The golden lives next to the test file, in ``goldens/<test name>.csv``
(directory configurable via the ``tablegold_dir`` ini option). Re-bless a
suite after an intended change with ``TABLEGOLD_UPDATE=1 pytest`` or
``pytest --tablegold-update``.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import pytest

from .compare import Comparison
from .golden import assert_matches_golden, update_requested
from .table import TableLike

_UNSAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def pytest_addoption(parser: Any) -> None:
    parser.addini(
        "tablegold_dir",
        default="goldens",
        help="directory for tablegold golden files, relative to the test file",
    )
    group = parser.getgroup("tablegold")
    group.addoption(
        "--tablegold-update",
        action="store_true",
        default=False,
        help="re-bless golden files from actual outputs (same as TABLEGOLD_UPDATE=1)",
    )


class GoldenFixture:
    """Per-test handle that knows where this test's golden files live."""

    def __init__(self, request: Any) -> None:
        self._request = request
        base = Path(request.node.path).parent
        self.golden_dir = base / request.config.getini("tablegold_dir")
        self.update = update_requested(
            True if request.config.getoption("--tablegold-update") else None
        )

    def path_for(self, name: Optional[str] = None) -> Path:
        """Golden path for this test (default: ``<test name>.csv``)."""
        if name is None:
            name = _UNSAFE_CHARS.sub("_", self._request.node.name) + ".csv"
        return self.golden_dir / name

    def check(
        self,
        actual: TableLike,
        name: Optional[str] = None,
        update: Optional[bool] = None,
        **options: Any,
    ) -> Comparison:
        """Assert *actual* matches this test's golden file.

        ``update=False`` opts a single check out of suite-wide re-blessing —
        useful for tests that assert a mismatch *is* caught.
        """
        if update is None:
            update = self.update
        return assert_matches_golden(
            actual, self.path_for(name), update=update, **options
        )


@pytest.fixture
def tablegold(request: Any) -> GoldenFixture:
    """A golden-file checker bound to the current test."""
    return GoldenFixture(request)

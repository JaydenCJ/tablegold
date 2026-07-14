"""Shared fixtures and helpers for the tablegold test suite.

Everything here is deterministic and offline: tables are built in memory
or written to pytest's ``tmp_path``, never fetched or timed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tablegold import Table

GOLDEN_TEXT = (
    "id,region,units,revenue,updated_at\n"
    "1001,east,12,100.5,2026-07-01T09:00:00Z\n"
    "1002,west,7,88.25,2026-07-01T09:05:00Z\n"
    "1003,east,3,1250.4,2026-07-01T09:10:00Z\n"
    "1004,north,9,0.0,2026-07-01T09:15:00Z\n"
)


def make_table(text: str, source: str = "<test>") -> Table:
    """Build a Table from inline CSV text (header on the first line)."""
    return Table.from_text(text, source=source)


@pytest.fixture
def golden_table() -> Table:
    """The canonical four-row metrics table used across compare tests."""
    return make_table(GOLDEN_TEXT, source="golden.csv")


@pytest.fixture
def golden_file(tmp_path: Path) -> Path:
    """The canonical table written to disk as golden.csv."""
    path = tmp_path / "golden.csv"
    path.write_text(GOLDEN_TEXT, encoding="utf-8")
    return path

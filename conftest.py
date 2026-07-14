"""Repo-root pytest configuration.

Makes ``src/`` importable and loads the tablegold pytest plugin, so the
whole suite runs from a plain checkout — no install step required. When
the package *is* installed, the ``pytest11`` entry point has already
imported and registered the plugin before this conftest is collected, so
registering it again (under a second name) must be skipped.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

_already_registered = "tablegold.pytest_plugin" in sys.modules

# pytester powers the pytest-plugin tests; it ships with pytest itself.
pytest_plugins = (
    ["pytester"] if _already_registered else ["tablegold.pytest_plugin", "pytester"]
)

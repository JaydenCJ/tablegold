"""Allow ``python -m tablegold`` to behave exactly like the ``tablegold`` script."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())

"""Make the framework scripts and the package importable from the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT: Path = Path(__file__).resolve().parents[1]
for relative in ("scripts", "src"):
    candidate = ROOT / relative
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

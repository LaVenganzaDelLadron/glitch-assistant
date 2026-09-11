"""Shared pytest configuration and fixtures.

Ensures the repository root is importable regardless of how pytest is
invoked (e.g. plain ``pytest`` vs ``python -m pytest``).
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
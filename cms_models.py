"""CMS model helpers (lightweight; DB schema is created in shared/db.py).

This module intentionally stays minimal because the codebase uses sqlite3.Row
and direct SQL in route handlers.

If/when the project moves to full ORM patterns, these helpers can be expanded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


def _to_int(val: Any, default: int = 0) -> int:
    try:
        if val is None:
            return default
        return int(val)
    except Exception:
        return default


def _to_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None:
            return default
        return float(val)
    except Exception:
        return default


@dataclass
class CmsRow:
    """Base dataclass for CMS rows."""

    id: Optional[int] = None

    @classmethod
    def from_row(cls, row):  # pragma: no cover
        return cls(id=row["id"] if row and "id" in row.keys() else None)


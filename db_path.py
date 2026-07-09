"""Canonical SQLite DB path + initialization helpers.

Problem (Vercel): `sqlite3.OperationalError: unable to open database file`

Root causes found in this repo:
- Multiple modules define different DB_PATH values.
- Some DB_PATH values point at directories that may not exist at runtime.
- Some initialization only runs under `if __name__ == '__main__'`.

This module provides:
- A single absolute DB path constructed using `pathlib.Path` and `__file__`.
- Writable runtime directory selection (env override, Vercel fallback, local fallback).
- Directory creation before opening SQLite.
- DB file existence + schema initialization before any query.

Usage:
    from db_path import DB_PATH, ensure_db_initialized
"""

from __future__ import annotations

import os

# sqlite3 is intentionally imported only for local-development SQLite fallback.
# In production (DATABASE_URL present), code paths must not reach this import.
if not os.getenv("DATABASE_URL"):
    import sqlite3



# NOTE: PostgreSQL mode does not use this module for DB connections.
# It remains only to compute the local SQLite DB path when DATABASE_URL is missing.


from pathlib import Path
from typing import Optional


def _is_vercel_runtime() -> bool:
    # Vercel sets `VERCEL` in most runtimes.
    return os.environ.get("VERCEL", "").lower() in {"1", "true", "yes"}


def _project_root() -> Path:
    # Repo root = directory containing this file.
    return Path(__file__).resolve().parent


def _default_db_dir() -> Path:
    # 1) Explicit override.
    override = os.environ.get("SQLITE_DB_DIR") or os.environ.get("SQLITE_DB_PATH")
    if override:
        # If SQLITE_DB_PATH is provided, use its parent.
        p = Path(override)
        if p.suffix:  # looks like a filename
            return p.parent
        return p

    # 2) Vercel runtime: use /tmp (writable).
    if _is_vercel_runtime():
        return Path("/tmp")

    # 3) Local/dev: use repo-root (writeable in typical dev).
    return _project_root()


def _compute_db_path() -> Path:
    override_path = os.environ.get("SQLITE_DB_PATH")
    if override_path:
        return Path(override_path).expanduser().resolve()

    db_dir = _default_db_dir()
    db_file = "bookings.db"
    return (db_dir / db_file).resolve()


DB_PATH: str = str(_compute_db_path())


def ensure_db_dir_exists(db_path: Optional[str] = None) -> Path:
    """Ensure the parent directory for the DB path exists."""
    p = Path(db_path or DB_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _try_create_db_file(db_path: str) -> None:
    """Create SQLite DB file if missing by opening a connection."""
    # Ensure directory exists first.
    ensure_db_dir_exists(db_path)

    # Opening the connection will create the file if it doesn't exist.
    conn = sqlite3.connect(db_path)
    try:
        # Lightweight pragma; no schema changes here.
        conn.execute("PRAGMA journal_mode=WAL")
    finally:
        conn.close()


def ensure_db_initialized() -> None:
    """Ensure DB directory/file exists and schema init runs before queries.

    In PostgreSQL mode (DATABASE_URL set), this is a no-op because PostgreSQL
    manages its own storage and does not use SQLite.

    Important: do NOT call shared.db.init_db() here, because shared.db.init_db()
    calls get_db_connection(), which calls ensure_db_initialized() again.
    That creates infinite recursion.
    """
    if os.getenv("DATABASE_URL"):
        return
    _try_create_db_file(DB_PATH)


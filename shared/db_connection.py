import os
import re
from pathlib import Path
from typing import Any, Optional, Sequence

from db_path import DB_PATH, ensure_db_initialized

if not os.getenv("DATABASE_URL"):
    import sqlite3

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover
    psycopg2 = None


DATABASE_URL = os.getenv("DATABASE_URL")
DB_ENGINE = "postgres" if DATABASE_URL else "sqlite"


def _normalize_placeholders(sql: str) -> str:
    """Convert SQLite-style ? placeholders to PostgreSQL %s."""
    if DB_ENGINE != "postgres":
        return sql
    return re.sub(r"\?(?![\w\d])", "%s", sql)


class _CompatibleRow:
    """Row wrapper that supports both key and integer indexing."""

    def __init__(self, row: Any):
        self._row = row
        self._values = None

    def _get_values(self):
        if self._values is None:
            if hasattr(self._row, "values"):
                self._values = list(self._row.values())
            else:
                self._values = list(self._row)
        return self._values

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._get_values()[key]
        return self._row[key]

    def __getattr__(self, name):
        try:
            return self._row[name]
        except (KeyError, TypeError):
            raise AttributeError(name)

    def __iter__(self):
        return iter(self._get_values())

    def __len__(self):
        return len(self._get_values())

    def __repr__(self):
        return repr(self._get_values())

    def __eq__(self, other):
        if isinstance(other, _CompatibleRow):
            return self._row == other._row
        return self._row == other

    def keys(self):
        if hasattr(self._row, "keys"):
            return self._row.keys()
        raise AttributeError("keys")

    def items(self):
        if hasattr(self._row, "items"):
            return self._row.items()
        raise AttributeError("items")

    def values(self):
        if hasattr(self._row, "values"):
            return self._row.values()
        return self._get_values()


class DBCursorWrapper:
    """Cursor wrapper that emulates SQLite cursor behavior over psycopg2/SQLite cursors."""

    def __init__(self, cursor, engine: str, lastrowid: Any = None):
        self._cursor = cursor
        self._engine = engine
        self._lastrowid = lastrowid

    def execute(self, sql, params=()):
        if self._engine == "postgres":
            sql = _normalize_placeholders(sql)
        self._cursor.execute(sql, params)
        return self

    def executemany(self, sql, seq_of_params):
        if self._engine == "postgres":
            sql = _normalize_placeholders(sql)
        self._cursor.executemany(sql, seq_of_params)
        return self

    def fetchone(self):
        row = self._cursor.fetchone()
        if row is None:
            return None
        if self._engine == "postgres":
            return _CompatibleRow(row)
        return row

    def fetchall(self):
        rows = self._cursor.fetchall()
        if self._engine == "postgres":
            return [_CompatibleRow(row) for row in rows]
        return rows

    @property
    def lastrowid(self):
        if self._engine == "postgres":
            return self._lastrowid
        return self._cursor.lastrowid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cursor.close()
        return False


class DBConnectionWrapper:
    """Connection wrapper providing SQLite-compatible conn.execute() semantics."""

    def __init__(self, conn, engine: str):
        self._conn = conn
        self._engine = engine

    def execute(self, sql, params=()):
        stripped = None
        if self._engine == "postgres":
            sql = _normalize_placeholders(sql)
            stripped = sql.strip().upper()
            if stripped.startswith("INSERT") and "RETURNING" not in sql.upper():
                sql = sql.rstrip().rstrip(";") + " RETURNING id"

        if self._engine == "postgres":
            cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cursor = self._conn.cursor()
        cursor.execute(sql, params)

        lastrowid = None
        if self._engine == "postgres" and stripped is not None and stripped.startswith("INSERT"):
            try:
                row = cursor.fetchone()
                if row is not None:
                    lastrowid = row["id"] if isinstance(row, dict) else row[0]
            except Exception:
                pass

        return DBCursorWrapper(cursor, self._engine, lastrowid=lastrowid)

    def executemany(self, sql, seq_of_params):
        if self._engine == "postgres":
            sql = _normalize_placeholders(sql)
            cursor = self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            cursor = self._conn.cursor()
        cursor.executemany(sql, seq_of_params)
        return DBCursorWrapper(cursor, self._engine)

    def cursor(self, **kwargs):
        if self._engine == "postgres":
            kwargs.setdefault("cursor_factory", psycopg2.extras.RealDictCursor)
        raw_cursor = self._conn.cursor(**kwargs)
        return DBCursorWrapper(raw_cursor, self._engine)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.close()
        return False


def _is_vercel_runtime() -> bool:
    return os.environ.get("VERCEL", "").lower() in {"1", "true", "yes"}


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _default_db_dir() -> Path:
    override = os.environ.get("SQLITE_DB_DIR") or os.environ.get("SQLITE_DB_PATH")
    if override:
        p = Path(override)
        if p.suffix:
            return p.parent
        return p

    if _is_vercel_runtime():
        return Path("/tmp")

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
    ensure_db_dir_exists(db_path)

    conn = sqlite3.connect(db_path)
    try:
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


def _init_sqlite() -> Any:
    """Local development fallback only."""
    ensure_db_initialized()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass

    return conn


def _init_postgres() -> Any:
    """Production backend."""
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed but DATABASE_URL is set. "
            "Add psycopg2-binary to requirements.txt and reinstall."
        )

    conn = psycopg2.connect(DATABASE_URL)

    conn.autocommit = False
    return conn


def get_db_connection(timeout: float = 30.0):
    """Return a DB connection.

    Enforced rules:
    - If DATABASE_URL is configured: use PostgreSQL only.
    - Otherwise: use local SQLite for development only.

    Note: `timeout` is ignored in PostgreSQL mode (handled by psycopg2).
    """
    import inspect
    import logging

    calling = None
    try:
        frame = inspect.currentframe()
        if frame is not None and frame.f_back is not None:
            calling = f"{frame.f_back.f_globals.get('__name__','?')}.{frame.f_back.f_code.co_name}"
    except Exception:
        calling = None

    has_url = bool(DATABASE_URL)

    if DB_ENGINE == "postgres":
        conn = _init_postgres()
        try:
            conn_cls = conn.__class__
            conn_name = getattr(conn_cls, '__name__', str(conn_cls))
            if conn_name and conn_name.lower().find('connection') == -1:
                pass
        except Exception:
            conn_name = type(conn).__name__

        logging.getLogger(__name__).info(
            "[DB DEBUG] DATABASE_URL=%s ENGINE=PostgreSQL CONNECTION_CLASS=%s CALLING=%s",
            has_url,
            type(conn).__module__ + '.' + type(conn).__name__,
            calling,
        )
        return DBConnectionWrapper(conn, "postgres")

    conn = _init_sqlite()
    try:
        conn_fq = type(conn).__module__ + '.' + type(conn).__name__
    except Exception:
        conn_fq = type(conn).__name__

    logging.getLogger(__name__).info(
        "[DB DEBUG] DATABASE_URL=%s ENGINE=SQLite CONNECTION_CLASS=%s CALLING=%s",
        has_url,
        conn_fq,
        calling,
    )
    return DBConnectionWrapper(conn, "sqlite")


def get_cursor(conn, *, dict_rows: bool = True):
    """Create cursor with consistent row access style.

    In PostgreSQL mode we always return dict-like rows (psycopg2 RealDictCursor)
    so production code can safely use row['col'].

    In SQLite fallback mode we return sqlite3 cursor rows.
    """
    if DB_ENGINE == "postgres":
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    return conn.cursor()


def fetch_one(conn, query: str, params: Optional[tuple] = None):
    params = params or ()
    with get_cursor(conn) as cur:
        cur.execute(query, params)
        return cur.fetchone()


def fetch_all(conn, query: str, params: Optional[tuple] = None):
    params = params or ()
    with get_cursor(conn) as cur:
        cur.execute(query, params)
        return cur.fetchall()

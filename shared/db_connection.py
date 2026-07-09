import os
from typing import Optional

from db_path import DB_PATH, ensure_db_initialized

# SQLite must be permitted ONLY for local development fallback.
# When DATABASE_URL is set (PostgreSQL mode), this module must never import or use sqlite3.

try:
    import psycopg2
    import psycopg2.extras
except Exception:  # pragma: no cover
    psycopg2 = None


DATABASE_URL = os.getenv("DATABASE_URL")
DB_ENGINE = "postgres" if DATABASE_URL else "sqlite"


def _init_sqlite():
    """Local development fallback only."""
    # Import sqlite3 lazily so this module can be imported in PostgreSQL mode
    # without ever touching sqlite3.
    import sqlite3

    ensure_db_initialized()
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row

    # Best-effort concurrency settings (SQLite only)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass

    return conn


def _init_postgres():
    """Production backend."""
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is not installed but DATABASE_URL is set. "
            "Add psycopg2-binary to requirements.txt and reinstall."
        )

    conn = psycopg2.connect(DATABASE_URL)

    # Use non-autocommit; callers call commit() where needed.
    conn.autocommit = False
    return conn


def get_db_connection(timeout: float = 30.0):
    """Return a DB connection.

    Enforced rules:
    - If DATABASE_URL is configured: use PostgreSQL only.
    - Otherwise: use local SQLite for development only.

    Note: `timeout` is ignored in PostgreSQL mode (handled by psycopg2).
    """
    # Temporary runtime diagnostics (for Vercel log inspection)
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
                # keep it compact but still useful
                pass
        except Exception:
            conn_name = type(conn).__name__

        logging.getLogger(__name__).info(
            "[DB DEBUG] DATABASE_URL=%s ENGINE=PostgreSQL CONNECTION_CLASS=%s CALLING=%s",
            has_url,
            type(conn).__module__ + '.' + type(conn).__name__,
            calling,
        )
        return conn

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
    return conn




def get_cursor(conn, *, dict_rows: bool = True):
    """Create cursor with consistent row access style.

    In PostgreSQL mode we always return dict-like rows (psycopg2 RealDictCursor)
    so production code can safely use row['col'].

    In SQLite fallback mode we return sqlite3 cursor rows.
    """
    if DB_ENGINE == "postgres":
        # psycopg2: always return dict rows
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # sqlite3 fallback
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


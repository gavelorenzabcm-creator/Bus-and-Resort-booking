# TODO - SQLite path fix for Vercel

- [ ] Add canonical DB path + initializer module using `pathlib.Path` and writable directory selection (env override + Vercel-safe fallback).
- [ ] Refactor `database.py` to use the canonical `DB_PATH` and to ensure initialization before connecting.
- [ ] Refactor `shared/db.py` to remove its hardcoded DB_PATH and use canonical DB path/initializer.
- [ ] Update `vercel_entry.py` to trigger DB initialization on startup before dispatching to Flask apps.
- [ ] Run smoke checks locally: import DB modules and call `ensure_db_initialized()`.
- [ ] Run existing tests (if any) and perform a quick local admin dashboard route test.
- [ ] Explain all files changed and why (final response).


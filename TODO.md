# Migration TODO (SQLite -> PostgreSQL via Supabase)

- [ ] Step 1: Add centralized DB connection module that chooses PostgreSQL when `DATABASE_URL` is set, otherwise falls back to local SQLite.
- [ ] Step 2: Add psycopg2-binary to `requirements.txt`.
- [x] Step 3: Refactor `database.py` to remove direct `sqlite3` usage and use the centralized connection.

- [x] Step 4: Refactor `shared/db.py` to remove direct `sqlite3` usage and use the centralized connection.

- [ ] Step 5: Refactor `vercel_entry.py` to initialize schema safely for both DB engines (no SQLite-only assumptions).
- [ ] Step 6: Convert schema SQL in `database.py` to PostgreSQL-compatible DDL (SERIAL, placeholder changes if any, remove PRAGMA/sqlite_master usage).
- [ ] Step 7: Convert query SQL placeholder styles where needed (`?` -> `%s`) for PostgreSQL.
- [ ] Step 8: Update `system_audit.py` (dev script) to use centralized DB access.
- [ ] Step 9: Replace every remaining `sqlite3.connect()` in the project with centralized connection usage.

- [ ] Step 10: Remove all `import sqlite3` dependencies across the app code (except within SQLite-only fallback sections).
- [ ] Step 11: Verify calendar/API routes return JSON correctly (manual + automated tests).
- [ ] Step 12: Run `pytest` and fix any failing routes/tests.


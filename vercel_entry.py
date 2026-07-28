"""Vercel entrypoint (single process) for BusResort.

Vercel expects a single Python entry file exporting a WSGI-compatible handler
named `app`.

This repo contains TWO independent Flask apps:
  - main_site.app       (customer website)
  - admin_site.admin_app (admin dashboard)

The admin app defines *absolute* routes like:
  - /admin
  - /admin/login
  - /dashboard
  - /delete/<booking_type>/<booking_id>
  - /api/admin/...

Therefore, we must not mount the admin app under a prefix (e.g. /admin) because
that shifts route rules and causes 404s.

Instead, we dispatch requests to the correct Flask app based on a strict,
explicit list of path prefixes that belong to the admin app. Anything not
matching one of these prefixes is sent to the main (customer) site.

NOTE: If you add a new absolute route to admin_app that does not start with
/admin, /dashboard, or /api/admin/ (like /delete/... below), you must add its
prefix to _ADMIN_PREFIXES here too, or it will 404 (main_app has no matching
route and admin_app never gets the request).
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from db_path import ensure_db_initialized

ensure_db_initialized()

from shared.db import init_db, init_website_settings

init_db()
init_website_settings()

from main_site.app import app as main_app  # noqa: E402
from admin_site.admin_app import app as admin_app  # noqa: E402

# Explicit prefixes: any path under these always goes to admin_app.
# Kept as a strict, predictable allow-list rather than dynamically matching
# against admin_app's url_map — dynamic matching previously caused main-site
# routes (e.g. "/") to be incorrectly hijacked by admin_app's own catch-all
# and static-file routes.
#
# This list was built by scanning every @app.route(...) decorator in
# admin_site/admin_app.py. Anything NOT under /admin, /dashboard, or
# /api/admin/ needs its own explicit entry here, or it will 404 (main_app has
# no matching route and admin_app never receives the request).
#
# If you add a new absolute route to admin_app.py in the future that isn't
# under one of the existing prefixes, add its prefix here too.
_ADMIN_PREFIXES = (
    "/admin",
    "/dashboard",
    "/api/admin/",
    "/confirm/",
    "/cancel/",
    "/delete/",
    "/edit/",
    "/uploads/",
)


def _belongs_to_admin(path: str, method: str) -> bool:
    return path == "/admin" or path == "/dashboard" or path.startswith(_ADMIN_PREFIXES)


def _create_dispatched_app():
    """Return a WSGI application that routes requests to the correct Flask app."""

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        method = environ.get("REQUEST_METHOD", "GET")

        if _belongs_to_admin(path, method):
            return admin_app.wsgi_app(environ, start_response)

        return main_app.wsgi_app(environ, start_response)

    return app


app = _create_dispatched_app()
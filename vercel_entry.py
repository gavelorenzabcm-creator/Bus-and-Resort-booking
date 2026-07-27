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

Instead, we dispatch requests to the correct Flask app based on whether the
incoming path actually matches one of admin_app's registered routes. This is
more robust than a hardcoded list of prefixes: any route added to admin_app in
the future (e.g. /delete/..., /approve/..., /export/...) is picked up
automatically without needing to edit this dispatcher again.
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

from werkzeug.routing import Map, RequestRedirect
from werkzeug.exceptions import MethodNotAllowed, NotFound


def _build_admin_matcher(flask_app):
    """Build a Werkzeug URL matcher from admin_app's own url_map.

    This lets us ask, for a given path, "does admin_app have a route for
    this?" without needing to duplicate/hardcode its route list here.
    """
    return flask_app.url_map.bind("dummy")  # server_name is unused for matching only


_admin_matcher = _build_admin_matcher(admin_app)

# Explicit fallback prefixes, kept as a safety net in case URL matching
# (which also checks HTTP method) rejects a path for a reason unrelated to
# "does this belong to the admin app" (e.g. method mismatch on a valid admin
# route). Any path under these prefixes always goes to admin_app.
_ADMIN_PREFIXES = (
    "/admin",
    "/dashboard",
    "/api/admin/",
    "/delete/",
)


def _belongs_to_admin(path: str, method: str) -> bool:
    if path.startswith(_ADMIN_PREFIXES) or path == "/admin" or path == "/dashboard":
        return True

    try:
        _admin_matcher.match(path, method=method)
        return True
    except MethodNotAllowed:
        # Path exists on admin_app, just not for this method — still admin's.
        return True
    except RequestRedirect:
        return True
    except NotFound:
        return False


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
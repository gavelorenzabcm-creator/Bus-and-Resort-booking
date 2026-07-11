"""Vercel entrypoint (single process) for BusResort.

Vercel expects a single Python entry file exporting a WSGI-compatible handler
named `app`.

This repo contains TWO independent Flask apps:
  - main_site.app  (customer website)
  - admin_site.admin_app  (admin dashboard)

The admin app defines *absolute* routes like:
  - /admin
  - /admin/login
  - /dashboard
  - /admin/...

Therefore, we must not mount the admin app under a prefix (e.g. /admin) because
that shifts route rules and causes 404s.

Instead, we dispatch requests to the correct Flask app based on PATH_INFO.
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


# Vercel/Python expects a single exported WSGI callable named `app`.
# Do not create multi-process server launchers here.


def _create_dispatched_app():
    """Return a WSGI application that routes requests to the correct Flask app."""

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "") or ""

        # -----------------------------
        # Admin Dashboard
        # -----------------------------
        if path == "/dashboard" or path.startswith("/dashboard/"):
            return admin_app.wsgi_app(environ, start_response)

        # -----------------------------
        # Admin Pages
        # -----------------------------
        if path == "/admin" or path.startswith("/admin/"):
            return admin_app.wsgi_app(environ, start_response)

        # -----------------------------
        # Admin API Endpoints
        # -----------------------------
        if path.startswith("/api/admin/"):
            return admin_app.wsgi_app(environ, start_response)

        # -----------------------------
        # Customer Website
        # -----------------------------
        return main_app.wsgi_app(environ, start_response)

    return app

app = _create_dispatched_app()
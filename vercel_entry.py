"""Vercel entrypoint (single process) for BusResort.

Vercel expects a single Python entry file exporting WSGI-compatible handler.
This project normally runs TWO Flask apps (main + admin) via run.py.

To deploy on Vercel with a single handler, we mount the admin app under /admin
and keep the main app at /. This yields one deployable application.
"""

import os
import sys

# Ensure project root is importable
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from main_site.app import app as main_app  # noqa: E402
from admin_site.admin_app import app as admin_app  # noqa: E402


def _create_mounted_app():
    from werkzeug.middleware.dispatcher import DispatcherMiddleware

    # We mount by forwarding /admin/* to admin_app.
    # Admin app already defines its routes under /admin/... and also has / and /admin/login.
    # We mount admin_app at /admin to avoid exposing its root.
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from werkzeug.wsgi import ClosingIterator

    main_app_wrapped = main_app

    # Remove admin_app root route responsiveness by mounting admin at /admin.
    # Routes like /admin/... are already prefixed; mounting at /admin will make them /admin/admin/...
    # However, your admin_app also defines routes like / (redirects to admin_login).
    # To keep URLs correct, we mount admin_app at /admin and also strip the extra prefix.
    # Simpler: mount admin_app at / (root) but route selection is done via Dispatcher.
    # We'll mount admin_app at /admin and additionally add a fallback so /admin/* works.

    # Best mapping: mount admin_app at /admin and also change admin_app's idea of URL.
    # Since we can't easily rewrite all route rules, we mount admin_app at /admin and keep
    # its internal routes as-is. Your admin_app uses /admin/... paths already.
    # That means accessing /admin/dashboard (in browser) would hit admin_app rule /admin/dashboard
    # only if admin_app sees SCRIPT_NAME='/admin'. Mounting at /admin makes that true.

    # Mount admin_app at root.
    # admin_app already defines admin URLs as absolute routes:
    #   /admin (login), /dashboard (admin dashboard), /admin/... (all admin endpoints)
    # Mounting it under /admin would shift routes to /admin/admin/... and commonly cause
    # /dashboard to 404 on Vercel.
    application = DispatcherMiddleware(
        main_app_wrapped,
        {
            "/": admin_app,
        },
    )


    return application


# Vercel looks for `app` or `handler`
app = _create_mounted_app()


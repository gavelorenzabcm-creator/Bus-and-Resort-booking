import sys

sys.path.insert(0, r"c:/Users/Nitro/OneDrive/Documents/bus-resort-booking-system")

from admin_site.admin_app import app


def test_admin_dashboard_renders_successfully():
    client = app.test_client()

    login_response = client.post(
        "/admin",
        data={"username": "admin", "password": "admin123"},
        follow_redirects=False,
    )

    assert login_response.status_code == 302

    dashboard_response = client.get("/dashboard", follow_redirects=False)

    assert dashboard_response.status_code == 200
    assert b"Admin Dashboard" in dashboard_response.data
    assert b"Resort Room Management" in dashboard_response.data
    assert b"Exclusive Option" in dashboard_response.data

"""Shared DB operations.

This repo originally used SQLite everywhere.

For the migration to PostgreSQL we keep this module as a stable import target
for the rest of the codebase, but the underlying connection is provided by
`shared.db_connection`.

Important:
- This module must be safe in both PostgreSQL (DATABASE_URL present) and the
  explicit local SQLite fallback (DATABASE_URL absent).
- Any SQLite-only SQL must never run in PostgreSQL mode.

Booking/business logic is preserved; only initialization SQL is migrated.
"""

from werkzeug.security import generate_password_hash

from shared.db_connection import get_db_connection
from shared.db_connection import DB_ENGINE


def cancel_booking(conn, booking_type: str, booking_id: int, cancelled_by: str) -> dict:
    """Idempotent cancellation workflow for both bus + resort."""
    if booking_type not in ("bus", "resort"):
        raise ValueError("booking_type must be 'bus' or 'resort'")

    active_table = "BusBookings" if booking_type == "bus" else "ResortBookings"
    cancelled_table = "CancelledBusBookings" if booking_type == "bus" else "CancelledResortBookings"
    date_column = "datetime" if booking_type == "bus" else "checkin"

    row = conn.execute(
        f"SELECT id, name, status, {date_column} FROM {active_table} WHERE id = ?",
        (booking_id,),
    ).fetchone()

    if not row:
        return {"found": False}

    raw_date = row[date_column] if row[date_column] else None
    travel_date = str(raw_date)[:10] if raw_date else "Unknown"

    notif_type = "cancel_bus" if booking_type == "bus" else "cancel_resort"
    notif_msg = f"Booking cancelled by {row['name']} for {travel_date}"

    if (row["status"] or "").strip() == "Cancelled":
        # Ensure cancelled row exists.
        try:
            exists = conn.execute(
                f"SELECT 1 FROM {cancelled_table} WHERE booking_id = ? LIMIT 1",
                (booking_id,),
            ).fetchone()
            if not exists:
                if booking_type == "bus":
                    src = conn.execute(
                        "SELECT * FROM BusBookings WHERE id = ?",
                        (booking_id,),
                    ).fetchone()
                    conn.execute(
                        """
                        INSERT INTO CancelledBusBookings (
                            booking_id, name, contact, email, pickup, destination, datetime, checkin, checkout,
                            passengers, price, created_at, cancelled_at, cancelled_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                        """,
                        (
                            src["id"],
                            src["name"],
                            src["contact"],
                            src["email"],
                            src["pickup"],
                            src["destination"],
                            src["datetime"],
                            src["checkin"],
                            src["checkout"],
                            src["passengers"],
                            src["price"],
                            src["created_at"],
                            cancelled_by,
                        ),
                    )
                else:
                    src = conn.execute(
                        "SELECT * FROM ResortBookings WHERE id = ?",
                        (booking_id,),
                    ).fetchone()
                    conn.execute(
                        """
                        INSERT INTO CancelledResortBookings (
                            booking_id, name, contact, email, checkin, checkout, checkin_time, checkout_time,
                            guests, room_type, payment_method, status, price_per_night, total_cost, price,
                            is_exclusive, exclusive_price, appliances_json, appliances_cost, room_instances,
                            created_at, cancelled_at, cancelled_by
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                        """,
                        (
                            src["id"],
                            src["name"],
                            src["contact"],
                            src["email"],
                            src["checkin"],
                            src["checkout"],
                            src["checkin_time"],
                            src["checkout_time"],
                            src["guests"],
                            src["room_type"],
                            src["payment_method"],
                            src["status"],
                            src["price_per_night"],
                            src["total_cost"],
                            src["price"],
                            src["is_exclusive"],
                            src["exclusive_price"],
                            src["appliances_json"],
                            src["appliances_cost"],
                            src["room_instances"],
                            src["created_at"],
                            cancelled_by,
                        ),
                    )
        except Exception:
            # Keep idempotent behavior: do not fail cancellation if the move copy fails.
            pass

        return {
            "found": True,
            "already_cancelled": True,
            "booking_id": booking_id,
            "booking_type": booking_type,
            "travel_date": travel_date,
            "notification_type": notif_type,
        }

    conn.execute(
        f"UPDATE {active_table} SET status = 'Cancelled' WHERE id = ?",
        (booking_id,),
    )

    already_moved = conn.execute(
        f"SELECT 1 FROM {cancelled_table} WHERE booking_id = ? LIMIT 1",
        (booking_id,),
    ).fetchone()

    if not already_moved:
        if booking_type == "bus":
            src = conn.execute("SELECT * FROM BusBookings WHERE id = ?", (booking_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO CancelledBusBookings (
                    booking_id, name, contact, email, pickup, destination, datetime, checkin, checkout,
                    passengers, price, created_at, cancelled_at, cancelled_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    src["id"],
                    src["name"],
                    src["contact"],
                    src["email"],
                    src["pickup"],
                    src["destination"],
                    src["datetime"],
                    src["checkin"],
                    src["checkout"],
                    src["passengers"],
                    src["price"],
                    src["created_at"],
                    cancelled_by,
                ),
            )
        else:
            src = conn.execute("SELECT * FROM ResortBookings WHERE id = ?", (booking_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO CancelledResortBookings (
                    booking_id, name, contact, email, checkin, checkout, checkin_time, checkout_time,
                    guests, room_type, payment_method, status, price_per_night, total_cost, price,
                    is_exclusive, exclusive_price, appliances_json, appliances_cost, room_instances,
                    created_at, cancelled_at, cancelled_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    src["id"],
                    src["name"],
                    src["contact"],
                    src["email"],
                    src["checkin"],
                    src["checkout"],
                    src["checkin_time"],
                    src["checkout_time"],
                    src["guests"],
                    src["room_type"],
                    src["payment_method"],
                    src["status"],
                    src["price_per_night"],
                    src["total_cost"],
                    src["price"],
                    src["is_exclusive"],
                    src["exclusive_price"],
                    src["appliances_json"],
                    src["appliances_cost"],
                    src["room_instances"],
                    src["created_at"],
                    cancelled_by,
                ),
            )

    log_exists = conn.execute(
        "SELECT 1 FROM CancellationLog WHERE booking_type = ? AND booking_id = ? LIMIT 1",
        (booking_type, booking_id),
    ).fetchone()

    if not log_exists:
        conn.execute(
            """
            INSERT INTO CancellationLog (booking_type, booking_id, customer_name, travel_date, cancelled_by, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (booking_type, booking_id, row["name"], travel_date, cancelled_by, ""),
        )

    notif_exists = conn.execute(
        """
        SELECT 1 FROM Notification
        WHERE type = ? AND message = ?
        ORDER BY id DESC LIMIT 1
        """,
        (notif_type, notif_msg),
    ).fetchone()

    if not notif_exists:
        conn.execute(
            "INSERT INTO Notification (message, type) VALUES (?, ?)",
            (notif_msg, notif_type),
        )

    return {
        "found": True,
        "already_cancelled": False,
        "booking_id": booking_id,
        "booking_type": booking_type,
        "travel_date": travel_date,
        "notification_type": notif_type,
    }


def init_db():
    """Initialize schema idempotently.

    Must be PostgreSQL-compatible when DATABASE_URL is present.
    SQLite fallback remains supported but should only execute when DATABASE_URL
    is absent.
    """

    conn = get_db_connection()
    try:
        # PostgreSQL-safe: rely only on IF NOT EXISTS and ON CONFLICT.
        # (SQLite fallback also supports these constructs.)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Admin (
                id SERIAL PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255) DEFAULT '',
                email_enabled INTEGER DEFAULT 0
            )
            """
        )
        # Default admin row
        conn.execute(
            """
            INSERT INTO Admin (username, password)
            VALUES ('admin', %s)
            ON CONFLICT(username) DO NOTHING
            """
            if DB_ENGINE == "postgres"
            else """
            INSERT INTO Admin (username, password)
            VALUES ('admin', ?)
            ON CONFLICT(username) DO NOTHING
            """,
            (
                generate_password_hash('admin123'),
            ) if DB_ENGINE == "postgres" else (generate_password_hash('admin123'),),
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Notification (
                id SERIAL PRIMARY KEY,
                message TEXT NOT NULL,
                type VARCHAR(50) NOT NULL CHECK(type IN ('booking_bus', 'booking_resort', 'review', 'cancel_bus', 'cancel_resort')),
                is_read INTEGER DEFAULT 0,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS CancellationLog (
                id SERIAL PRIMARY KEY,
                booking_type VARCHAR(20) NOT NULL,
                booking_id INTEGER NOT NULL,
                customer_name VARCHAR(255),
                travel_date VARCHAR(10),
                cancelled_by VARCHAR(20) NOT NULL,
                reason TEXT,
                date_cancelled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS Feedback (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >=1 AND rating <=5),
                comment TEXT NOT NULL,
                date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS BusBookings (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                contact VARCHAR(50),
                email VARCHAR(255),
                pickup VARCHAR(255),
                destination VARCHAR(255) NOT NULL,
                datetime TIMESTAMP NOT NULL,
                checkin TIMESTAMP,
                checkout TIMESTAMP NOT NULL,
                passengers INTEGER DEFAULT 1,
                price REAL DEFAULT 0,
                status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ResortBookings (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                contact VARCHAR(50),
                email VARCHAR(255),
                checkin DATE NOT NULL,
                checkout DATE NOT NULL,
                checkin_time VARCHAR(5) DEFAULT '14:00',
                checkout_time VARCHAR(5) DEFAULT '12:00',
                guests INTEGER DEFAULT 1,
                room_type TEXT,
                payment_method VARCHAR(20) DEFAULT 'Cash',
                status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
                price_per_night REAL DEFAULT 0,
                total_cost REAL DEFAULT 0,
                price REAL DEFAULT 0,
                is_exclusive INTEGER DEFAULT 0,
                exclusive_price REAL DEFAULT 0,
                appliances_json TEXT,
                appliances_cost REAL DEFAULT 0,
                room_instances TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.commit()
    finally:
        conn.close()


def migrate_cms_schema(conn=None) -> None:
    """Legacy stub for compatibility."""
    return


def init_website_settings():
    """Ensure WebsiteSettings exists with a default row.

    Safe for PostgreSQL and local SQLite fallback.
    """
    conn = get_db_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS WebsiteSettings (
                id INTEGER PRIMARY KEY DEFAULT 1,
                site_name VARCHAR(255) DEFAULT 'BusResort',
                homepage_welcome TEXT DEFAULT 'Welcome to BusResort',
                homepage_description TEXT DEFAULT 'Book Mini Bus rentals and cozy resort stays seamlessly.',
                contact_email VARCHAR(255) DEFAULT '',
                contact_phone VARCHAR(50) DEFAULT '',
                logo TEXT DEFAULT '',
                homepage_image TEXT DEFAULT '',
                resort_image TEXT DEFAULT '',
                bus_image TEXT DEFAULT ''
            )
            """
        )

        if DB_ENGINE == "postgres":
            conn.execute(
                """
                INSERT INTO WebsiteSettings (id)
                VALUES (1)
                ON CONFLICT (id) DO NOTHING
                """
            )
        else:
            conn.execute(
                """
                INSERT INTO WebsiteSettings (id)
                VALUES (1)
                ON CONFLICT (id) DO NOTHING
                """
            )

        conn.commit()
    finally:
        conn.close()


import os
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash

from db_path import DB_PATH, ensure_db_initialized


def get_db_connection(timeout=30.0):
    """Return sqlite3 connection with row_factory and timeout.

    In Vercel/production the DB file may exist but the schema may not be
    initialized yet (because init_db() previously only ran under __main__).

    This function guarantees the schema exists by calling init_db() exactly
    once when a sentinel table is missing.

    Args:
        timeout: Maximum time (in seconds) to wait for a database lock to clear.
                 Default is 30 seconds to prevent indefinite hanging.
    """
    ensure_db_initialized()
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row

    # Enable WAL mode for better concurrency
    conn.execute('PRAGMA journal_mode=WAL')
    # Set busy timeout in milliseconds
    conn.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')

    # Schema guard (idempotent) - only validate after we can connect.
    # ResortBookings is used because the failing page is /resort.
    try:
        sentinel = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ResortBookings'"
        ).fetchone()
        if sentinel is None:
            # Import-free call: init_db() is defined below in this module.
            init_db()
            # Re-open connection after init_db(), since it closes its own conn.
            conn.close()
            conn = sqlite3.connect(DB_PATH, timeout=timeout)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute(f'PRAGMA busy_timeout={int(timeout * 1000)}')
    except Exception:
        # If the sentinel check itself fails, let the actual queries raise
        # their real errors rather than masking them.
        pass

    return conn

def cancel_booking(conn, booking_type: str, booking_id: int, cancelled_by: str) -> dict:
    """Idempotent cancellation workflow for both bus + resort.

    Guarantees:
      - Runs within an outer transaction (caller should BEGIN/COMMIT/ROLLBACK).
      - Copies the booking into Cancelled*Bookings tables.
      - Updates original booking status to 'Cancelled' (no hard delete).
      - Inserts CancellationLog + Notification exactly once per booking.

    Returns:
      dict with keys:
        - found: bool
        - already_cancelled: bool
        - booking_type, booking_id
        - travel_date (str)
        - notification_type (str)
    """
    if booking_type not in ("bus", "resort"):
        raise ValueError("booking_type must be 'bus' or 'resort'")

    active_table = "BusBookings" if booking_type == "bus" else "ResortBookings"
    cancelled_table = "CancelledBusBookings" if booking_type == "bus" else "CancelledResortBookings"
    date_column = "datetime" if booking_type == "bus" else "checkin"

    # Fetch booking row (minimal columns needed)
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

    # Idempotency: if already cancelled, do NOT duplicate move/log/notification.
    if (row["status"] or "").strip() == "Cancelled":
        # Best-effort: ensure cancelled table has the row. If it doesn't, create it once.
        try:
            exists = conn.execute(
                f"SELECT 1 FROM {cancelled_table} WHERE booking_id = ? LIMIT 1",
                (booking_id,),
            ).fetchone()
            if not exists:
                # Copy minimal fields. Keep schema expansion safe by selecting only known cols.
                if booking_type == 'bus':
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
                            src["id"], src["name"], src["contact"], src["email"], src["pickup"], src["destination"],
                            src["datetime"], src["checkin"], src["checkout"], src["passengers"], src["price"],
                            src["created_at"], cancelled_by,
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
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                        """,
                        (
                            src["id"], src["name"], src["contact"], src["email"], src["checkin"], src["checkout"],
                            src["checkin_time"], src["checkout_time"], src["guests"], src["room_type"],
                            src["payment_method"], src["status"], src["price_per_night"], src["total_cost"],
                            src["price"], src["is_exclusive"], src["exclusive_price"], src["appliances_json"],
                            src["appliances_cost"], src["room_instances"], src["created_at"], cancelled_by,
                        ),
                    )
        except Exception:
            # If best-effort move fails, still keep cancellation idempotent.
            pass

        return {
            "found": True,
            "already_cancelled": True,
            "booking_id": booking_id,
            "booking_type": booking_type,
            "travel_date": travel_date,
            "notification_type": notif_type,
        }

    # Perform the move + updates exactly once
    # 1) Update active booking status
    conn.execute(
        f"UPDATE {active_table} SET status = 'Cancelled' WHERE id = ?",
        (booking_id,),
    )

    # 2) Copy into cancelled bookings table (if not already moved)
    already_moved = conn.execute(
        f"SELECT 1 FROM {cancelled_table} WHERE booking_id = ? LIMIT 1",
        (booking_id,),
    ).fetchone()

    if not already_moved:
        if booking_type == 'bus':
            src = conn.execute("SELECT * FROM BusBookings WHERE id = ?", (booking_id,)).fetchone()
            conn.execute(
                """
                INSERT INTO CancelledBusBookings (
                    booking_id, name, contact, email, pickup, destination, datetime, checkin, checkout,
                    passengers, price, created_at, cancelled_at, cancelled_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    src["id"], src["name"], src["contact"], src["email"], src["pickup"], src["destination"],
                    src["datetime"], src["checkin"], src["checkout"], src["passengers"], src["price"],
                    src["created_at"], cancelled_by,
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
                """,
                (
                    src["id"], src["name"], src["contact"], src["email"], src["checkin"], src["checkout"],
                    src["checkin_time"], src["checkout_time"], src["guests"], src["room_type"],
                    src["payment_method"], src["status"], src["price_per_night"], src["total_cost"],
                    src["price"], src["is_exclusive"], src["exclusive_price"], src["appliances_json"],
                    src["appliances_cost"], src["room_instances"], src["created_at"], cancelled_by,
                ),
            )

    # 3) Insert audit log + notification only if we haven’t already logged this booking
    #    (defensive against duplicate helper calls within the same overall request)
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

    """Create all tables and defaults if missing.

    Note: this function is idempotent. If the DB already exists, we still ensure
    missing tables are created (so future CMS schema upgrades apply automatically).
    """
    conn = get_db_connection()
    try:
        # If DB already initialized, we continue instead of returning.
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Admin'")
        db_has_schema = bool(cursor.fetchone())

        # Admin and booking tables (legacy schema)
        if not db_has_schema:
            conn.execute("""
            CREATE TABLE Admin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username VARCHAR(255) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(255) DEFAULT '',
                email_enabled INTEGER DEFAULT 0
            )
            """)
            conn.execute(
                "INSERT OR IGNORE INTO Admin (username, password) VALUES ('admin', ?)",
                (generate_password_hash('admin123'),),
            )

            conn.execute("""
            CREATE TABLE Notification (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                type VARCHAR(50) NOT NULL CHECK(type IN ('booking_bus', 'booking_resort', 'review', 'cancel_bus', 'cancel_resort')),
                is_read INTEGER DEFAULT 0,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE CancellationLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                booking_type VARCHAR(20) NOT NULL,
                booking_id INTEGER NOT NULL,
                customer_name VARCHAR(255),
                travel_date VARCHAR(10),
                cancelled_by VARCHAR(20) NOT NULL,
                reason TEXT,
                date_cancelled DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE Feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL,
                service_type VARCHAR(50) NOT NULL,
                rating INTEGER NOT NULL CHECK(rating >=1 AND rating <=5),
                comment TEXT NOT NULL,
                date_created DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE BusBookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                contact VARCHAR(50),
                email VARCHAR(255),
                pickup VARCHAR(255),
                destination VARCHAR(255) NOT NULL,
                datetime DATETIME NOT NULL,
                checkin DATETIME,
                checkout DATETIME NOT NULL,
                passengers INTEGER DEFAULT 1,
                price REAL DEFAULT 0,
                status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE ResortBookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)

            conn.execute("""
            CREATE TABLE BusPricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                destination VARCHAR(255) UNIQUE NOT NULL,
                price REAL DEFAULT 0
            )
            """)
            conn.execute("""
            CREATE TABLE RoomPricing (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_type VARCHAR(100) UNIQUE NOT NULL,
                price_per_night REAL DEFAULT 0
            )
            """)
            conn.execute("""
            CREATE TABLE ResortOptions (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                exclusive_price REAL DEFAULT 0
            )
            """)
            conn.execute("INSERT OR IGNORE INTO ResortOptions (id, exclusive_price) VALUES (1, 0)")
            conn.execute("""
            CREATE TABLE ResortRooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) NOT NULL,
                room_type VARCHAR(100) NOT NULL,
                capacity INTEGER DEFAULT 2,
                status VARCHAR(20) DEFAULT 'Available' CHECK(status IN ('Available', 'Unavailable')),
                image_path TEXT
            )
            """)
            conn.execute("""
            CREATE TABLE RentableAppliances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(255) UNIQUE NOT NULL,
                price REAL DEFAULT 0
            )
            """)

        # Room photo gallery (up to 3 photos per resort room)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS ResortRoomPhotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            photo_order INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            UNIQUE(room_id, photo_order),
            FOREIGN KEY(room_id) REFERENCES ResortRooms(id) ON DELETE CASCADE
        )
        """)

        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")

        # CMS tables (created even for existing DBs)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_Homepage (
            id INTEGER PRIMARY KEY DEFAULT 1,
            website_title TEXT DEFAULT '',
            hero_title TEXT DEFAULT '',
            hero_subtitle TEXT DEFAULT '',
            booking_section_title TEXT DEFAULT '',
            booking_description TEXT DEFAULT '',
            booking_placeholder_full_name TEXT DEFAULT '',
            booking_placeholder_phone TEXT DEFAULT '',
            booking_button_text TEXT DEFAULT '',
            search_labels TEXT DEFAULT '',
            booking_success_message TEXT DEFAULT '',
            booking_error_message TEXT DEFAULT '',

            -- Booking Success Popup configuration
            booking_success_popup_title TEXT DEFAULT 'Booking Submitted Successfully!',
            booking_success_popup_message TEXT DEFAULT 'Thank you for choosing BusResort!\nYour booking has been successfully submitted and is now awaiting confirmation from our administrator. We appreciate your trust in our service and look forward to serving you. Please keep your booking reference number for future inquiries.',
            booking_success_popup_ok_text TEXT DEFAULT 'OK',
            booking_success_popup_view_text TEXT DEFAULT 'View My Booking',
            booking_success_popup_show_icon INTEGER DEFAULT 1
        )
        """)



        conn.execute("INSERT OR IGNORE INTO CMS_Homepage (id) VALUES (1)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_HeroSlides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slide_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            background_image_path TEXT DEFAULT '',
            carousel_image_path TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_HeroButtons (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            button_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            text TEXT DEFAULT '',
            href TEXT DEFAULT '#',
            color TEXT DEFAULT 'blue'
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_NavMenuItems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_order INTEGER DEFAULT 0,
            is_visible INTEGER DEFAULT 1,
            name TEXT DEFAULT '',
            href TEXT DEFAULT '#'
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_BusCatalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sort_order INTEGER DEFAULT 0,
            is_available INTEGER DEFAULT 1,
            image_path TEXT DEFAULT '',
            name TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            features_json TEXT DEFAULT '[]'
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_ResortCatalog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sort_order INTEGER DEFAULT 0,
            promo_text TEXT DEFAULT '',
            resort_image_path TEXT DEFAULT '',
            room_image_path TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_ResortRooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sort_order INTEGER DEFAULT 0,
            resort_room_name TEXT DEFAULT '',
            room_type TEXT DEFAULT '',
            image_path TEXT DEFAULT '',
            description TEXT DEFAULT '',
            price REAL DEFAULT 0,
            amenities_json TEXT DEFAULT '[]',
            capacity INTEGER DEFAULT 1,
            is_available INTEGER DEFAULT 1
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_FeatureCards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_order INTEGER DEFAULT 0,
            icon_class TEXT DEFAULT '',
            title TEXT DEFAULT '',
            description TEXT DEFAULT ''
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_Testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_order INTEGER DEFAULT 0,
            customer_name TEXT DEFAULT '',
            customer_photo_path TEXT DEFAULT '',
            rating INTEGER DEFAULT 5,
            review TEXT DEFAULT ''
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_GalleryImages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_order INTEGER DEFAULT 0,
            image_path TEXT DEFAULT '',
            caption TEXT DEFAULT ''
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_ContactInfo (
            id INTEGER PRIMARY KEY DEFAULT 1,
            business_name TEXT DEFAULT '',
            business_tagline TEXT DEFAULT '',

            phone TEXT DEFAULT '',
            secondary_phone TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            whatsapp_number TEXT DEFAULT '',

            email TEXT DEFAULT '',
            office_address TEXT DEFAULT '',
            google_maps_link TEXT DEFAULT '',
            business_hours TEXT DEFAULT '',

            facebook_url TEXT DEFAULT '',
            instagram_url TEXT DEFAULT '',
            x_url TEXT DEFAULT '',
            tiktok_url TEXT DEFAULT '',
            youtube_url TEXT DEFAULT ''
        )
        """)
        conn.execute("INSERT OR IGNORE INTO CMS_ContactInfo (id) VALUES (1)")


        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_SocialLinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT DEFAULT '',
            href TEXT DEFAULT '',
            is_visible INTEGER DEFAULT 1,
            link_order INTEGER DEFAULT 0
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_FooterContent (
            id INTEGER PRIMARY KEY DEFAULT 1,
            footer_logo_path TEXT DEFAULT '',
            footer_description TEXT DEFAULT '',
            quick_links_json TEXT DEFAULT '[]',
            contact_section_title TEXT DEFAULT '',
            copyright_text TEXT DEFAULT '',
            privacy_policy_href TEXT DEFAULT '',
            terms_href TEXT DEFAULT ''
        )
        """)

        conn.execute("INSERT OR IGNORE INTO CMS_FooterContent (id) VALUES (1)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_BrandingAssets (
            id INTEGER PRIMARY KEY DEFAULT 1,
            primary_color TEXT DEFAULT '#2563EB',
            secondary_color TEXT DEFAULT '#16A34A',
            accent_color TEXT DEFAULT '#F59E0B',
            site_logo_path TEXT DEFAULT '',
            favicon_path TEXT DEFAULT '',
            default_button_colors TEXT DEFAULT 'blue'
        )
        """)
        conn.execute("INSERT OR IGNORE INTO CMS_BrandingAssets (id) VALUES (1)")

        # Legacy WebsiteSettings still needed by existing templates
        conn.execute("""
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
        """)
        conn.execute("INSERT OR IGNORE INTO WebsiteSettings (id) VALUES (1)")

        # Cancelled bookings tables (move destination)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CancelledBusBookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            pickup VARCHAR(255),
            destination VARCHAR(255) NOT NULL,
            datetime DATETIME NOT NULL,
            checkin DATETIME,
            checkout DATETIME NOT NULL,
            passengers INTEGER,
            price REAL,
            created_at DATETIME,
            cancelled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            cancelled_by VARCHAR(20) NOT NULL,
            UNIQUE(booking_id)
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CancelledResortBookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER NOT NULL,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            checkin DATE NOT NULL,
            checkout DATE NOT NULL,
            checkin_time VARCHAR(5),
            checkout_time VARCHAR(5),
            guests INTEGER,
            room_type TEXT,
            payment_method VARCHAR(20),
            status VARCHAR(20),
            price_per_night REAL,
            total_cost REAL,
            price REAL,
            is_exclusive INTEGER,
            exclusive_price REAL,
            appliances_json TEXT,
            appliances_cost REAL,
            room_instances TEXT,
            created_at DATETIME,
            cancelled_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            cancelled_by VARCHAR(20) NOT NULL,
            UNIQUE(booking_id)
        )
        """)

        conn.execute("CREATE INDEX IF NOT EXISTS idx_cancelled_bus_booking_id ON CancelledBusBookings(booking_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cancelled_resort_booking_id ON CancelledResortBookings(booking_id)")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_bookings_status_created ON BusBookings(status, created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_resort_bookings_status ON ResortBookings(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_read ON Notification(is_read, date_created DESC)")

        # IMPORTANT: keep the remainder of init_db idempotent.
        # Do NOT re-create tables with plain CREATE TABLE after we've already created them.
        # This block previously re-created CancellationLog/BusBookings/etc without IF NOT EXISTS,
        # causing "table ... already exists" and aborting further initialization.

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CancellationLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_type VARCHAR(20) NOT NULL,
            booking_id INTEGER NOT NULL,
            customer_name VARCHAR(255),
            travel_date VARCHAR(10),
            cancelled_by VARCHAR(20) NOT NULL,
            reason TEXT,
            date_cancelled DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS Feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            email VARCHAR(255) NOT NULL,
            service_type VARCHAR(50) NOT NULL,
            rating INTEGER NOT NULL CHECK(rating >=1 AND rating <=5),
            comment TEXT NOT NULL,
            date_created DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS BusBookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            contact VARCHAR(50),
            email VARCHAR(255),
            pickup VARCHAR(255),
            destination VARCHAR(255) NOT NULL,
            datetime DATETIME NOT NULL,
            checkin DATETIME,
            checkout DATETIME NOT NULL,
            passengers INTEGER DEFAULT 1,
            price REAL DEFAULT 0,
            status VARCHAR(20) DEFAULT 'Pending' CHECK(status IN ('Pending', 'Confirmed', 'Cancelled')),
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS ResortBookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS BusPricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            destination VARCHAR(255) UNIQUE NOT NULL,
            price REAL DEFAULT 0
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS RoomPricing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_type VARCHAR(100) UNIQUE NOT NULL,
            price_per_night REAL DEFAULT 0
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS ResortOptions (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            exclusive_price REAL DEFAULT 0
        )
        """)
        conn.execute("INSERT OR IGNORE INTO ResortOptions (id, exclusive_price) VALUES (1, 0)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS ResortRooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) NOT NULL,
            room_type VARCHAR(100) NOT NULL,
            capacity INTEGER DEFAULT 2,
            status VARCHAR(20) DEFAULT 'Available' CHECK(status IN ('Available', 'Unavailable')),
            image_path TEXT
        )
        """)

        conn.execute("""
        CREATE TABLE IF NOT EXISTS RentableAppliances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(255) UNIQUE NOT NULL,
            price REAL DEFAULT 0
        )
        """)

        conn.execute("""
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
        """)
        conn.execute("INSERT OR IGNORE INTO WebsiteSettings (id) VALUES (1)")

        migrate_cms_schema(conn)

        conn.commit()
        print("Database schema initialized/updated successfully (including CMS tables).")
    except Exception as e:
        conn.rollback()
        print(f"Database init error: {e}")
        raise e
    finally:
        conn.close()


def _table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row[1] for row in rows}


def _ensure_columns(conn, table_name: str, column_defs: dict[str, str]) -> None:
    """Add missing columns to an existing table (SQLite ALTER TABLE ADD COLUMN)."""
    existing = _table_columns(conn, table_name)
    for col, typedef in column_defs.items():
        if col not in existing:
            conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {typedef}")


def migrate_cms_schema(conn=None) -> None:
    """Upgrade CMS tables when the DB was created with an older schema.

    CREATE TABLE IF NOT EXISTS does not add new columns to existing tables, so
    admin Site Content saves can fail with 'no such column' until this runs.
    """

    close_conn = False
    if conn is None:
        conn = get_db_connection()
        close_conn = True
    try:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_ContactInfo (
            id INTEGER PRIMARY KEY DEFAULT 1,
            business_name TEXT DEFAULT '',
            business_tagline TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            secondary_phone TEXT DEFAULT '',
            mobile TEXT DEFAULT '',
            whatsapp_number TEXT DEFAULT '',
            email TEXT DEFAULT '',
            office_address TEXT DEFAULT '',
            google_maps_link TEXT DEFAULT '',
            business_hours TEXT DEFAULT '',
            facebook_url TEXT DEFAULT '',
            instagram_url TEXT DEFAULT '',
            x_url TEXT DEFAULT '',
            tiktok_url TEXT DEFAULT '',
            youtube_url TEXT DEFAULT ''
        )
        """)

        # Ensure booking success popup columns exist in older DBs
        _ensure_columns(conn, "CMS_Homepage", {
            "booking_success_popup_title": "TEXT DEFAULT 'Booking Submitted Successfully!'",
            "booking_success_popup_message": "TEXT DEFAULT 'Thank you for choosing BusResort!\\nYour booking has been successfully submitted and is now awaiting confirmation from our administrator. We appreciate your trust in our service and look forward to serving you. Please keep your booking reference number for future inquiries.'",
            "booking_success_popup_ok_text": "TEXT DEFAULT 'OK'",
            "booking_success_popup_view_text": "TEXT DEFAULT 'View My Booking'",
            "booking_success_popup_show_icon": "INTEGER DEFAULT 1",
        })

        _ensure_columns(conn, "CMS_ContactInfo", {
            "business_name": "TEXT DEFAULT ''",
            "business_tagline": "TEXT DEFAULT ''",
            "phone": "TEXT DEFAULT ''",
            "secondary_phone": "TEXT DEFAULT ''",
            "mobile": "TEXT DEFAULT ''",
            "whatsapp_number": "TEXT DEFAULT ''",
            "email": "TEXT DEFAULT ''",
            "office_address": "TEXT DEFAULT ''",
            "google_maps_link": "TEXT DEFAULT ''",
            "business_hours": "TEXT DEFAULT ''",
            "facebook_url": "TEXT DEFAULT ''",
            "instagram_url": "TEXT DEFAULT ''",
            "x_url": "TEXT DEFAULT ''",
            "tiktok_url": "TEXT DEFAULT ''",
            "youtube_url": "TEXT DEFAULT ''",
        })
        conn.execute("INSERT OR IGNORE INTO CMS_ContactInfo (id) VALUES (1)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_FooterContent (
            id INTEGER PRIMARY KEY DEFAULT 1,
            footer_logo_path TEXT DEFAULT '',
            footer_description TEXT DEFAULT '',
            quick_links_json TEXT DEFAULT '[]',
            contact_section_title TEXT DEFAULT '',
            copyright_text TEXT DEFAULT '',
            privacy_policy_href TEXT DEFAULT '',
            terms_href TEXT DEFAULT ''
        )
        """)
        _ensure_columns(conn, "CMS_FooterContent", {
            "footer_logo_path": "TEXT DEFAULT ''",
            "footer_description": "TEXT DEFAULT ''",
            "quick_links_json": "TEXT DEFAULT '[]'",
            "contact_section_title": "TEXT DEFAULT ''",
            "copyright_text": "TEXT DEFAULT ''",
            "privacy_policy_href": "TEXT DEFAULT ''",
            "terms_href": "TEXT DEFAULT ''",
        })
        conn.execute("INSERT OR IGNORE INTO CMS_FooterContent (id) VALUES (1)")

        conn.execute("""
        CREATE TABLE IF NOT EXISTS CMS_SocialLinks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            platform TEXT DEFAULT '',
            href TEXT DEFAULT '',
            is_visible INTEGER DEFAULT 1,
            link_order INTEGER DEFAULT 0
        )
        """)

        conn.commit()
    finally:
        if close_conn:
            conn.close()


def init_website_settings():
    """Initialize WebsiteSettings table with CREATE TABLE IF NOT EXISTS for safe migrations.
    This function is idempotent and can be run safely even if the table already exists.
    """
    conn = get_db_connection()
    try:
        # Use CREATE TABLE IF NOT EXISTS to be safe
        conn.execute("""
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
        """)
        # Insert default row if not exists
        conn.execute("INSERT OR IGNORE INTO WebsiteSettings (id) VALUES (1)")
        migrate_cms_schema(conn)
        conn.commit()
    except Exception as e:
        print(f"Error initializing WebsiteSettings: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

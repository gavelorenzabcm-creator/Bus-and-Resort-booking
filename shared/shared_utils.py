import sqlite3
import logging
import json

logger = logging.getLogger(__name__)


def create_notification(conn: sqlite3.Connection, message: str, ntype: str):
    """Create admin notification for new booking/review"""
    conn.execute(
        "INSERT INTO Notification (message, type) VALUES (?, ?)",
        (message, ntype)
    )


def safe_create_notification(conn: sqlite3.Connection, message: str, ntype: str):
    """Create admin notification, catching errors so the main transaction isn't affected."""
    try:
        create_notification(conn, message, ntype)
    except Exception as exc:
        logger.error("Failed to create notification (%s): %s", ntype, exc, exc_info=True)


def get_notifications(conn: sqlite3.Connection):
    """Get unread_count and all notifications"""
    cursor = conn.execute("SELECT COUNT(*) FROM Notification WHERE is_read = 0")
    unread_count = cursor.fetchone()[0]
    cursor = conn.execute("SELECT * FROM Notification ORDER BY date_created DESC LIMIT 50")
    notifications = cursor.fetchall()
    return unread_count, notifications


def log_cancellation(conn: sqlite3.Connection, booking_type: str, booking_id: int,
                     customer_name: str, travel_date: str, cancelled_by: str, reason: str = ""):
    """Log a cancellation action for audit/history tracking."""
    try:
        conn.execute(
            """
            INSERT INTO CancellationLog (booking_type, booking_id, customer_name, travel_date, cancelled_by, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (booking_type, booking_id, customer_name, travel_date, cancelled_by, reason)
        )
    except Exception as exc:
        logger.error("Failed to log cancellation for %s booking %s: %s", booking_type, booking_id, exc, exc_info=True)


def get_available_rooms_for_dates(conn, checkin, checkout):
    """Get available resort rooms for given checkin/checkout dates"""
    bookings = conn.execute("""
        SELECT room_instances FROM ResortBookings 
        WHERE status IN ('Pending', 'Confirmed')
        AND NOT (? <= checkin OR ? >= checkout)
    """, (checkout, checkin)).fetchall()

    
    booked_rooms = set()
    for b in bookings:
        if b['room_instances']:
            try:
                rooms_json = json.loads(b['room_instances'])
                booked_rooms.update(rooms_json)
            except:
                pass
    
    all_rooms = conn.execute(
        "SELECT id, name, room_type, capacity, COALESCE(image_path, '') AS image_path "
        "FROM ResortRooms WHERE status = 'Available'"
    ).fetchall()
    
    available = []
    for room in all_rooms:
        room_id = str(room['id'])
        if room_id not in booked_rooms:
            room_dict = dict(room)
            price = conn.execute("SELECT price_per_night FROM RoomPricing WHERE room_type = ?", (room['room_type'],)).fetchone()
            room_dict['price'] = float(price['price_per_night']) if price else 0
            available.append(room_dict)
    
    return [dict(r) for r in available]

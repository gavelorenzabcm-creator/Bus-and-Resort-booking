from __future__ import annotations

import datetime as dt
import json
import logging
import os
import sys
# Fix shared import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared import *

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for
from flask_mail import Mail, Message
from werkzeug.utils import secure_filename

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config.from_object('shared.config.Config')
mail = Mail(app)

# DB init moved to __main__ only


# ── Security Headers ──
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    if os.environ.get("FLASK_ENV", "development").lower() == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


# ── Error Handlers ──
@app.errorhandler(404)
def not_found(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(error):
    logger.error("Server error: %s", error, exc_info=True)
    return render_template("500.html"), 500


# ── Health Check ──
@app.route("/health")
def health_check():
    return jsonify({"status": "ok", "service": "busresort-main"}), 200


def _get_room_pricing_map(conn) -> dict[str, float]:
    rows = conn.execute("SELECT room_type, price_per_night FROM RoomPricing").fetchall()
    return {r["room_type"]: float(r["price_per_night"]) for r in rows}


def _get_room_pricing_rows(conn):
    rows = conn.execute("SELECT id, room_type, price_per_night FROM RoomPricing ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def _get_resort_rooms(conn):
    return conn.execute(
        "SELECT id, name, room_type, capacity, COALESCE(status, 'Available') AS status, "
        "COALESCE(image_path, '') AS image_path "
        "FROM ResortRooms ORDER BY room_type, name"
    ).fetchall()


def _get_resort_room_photos(conn, room_id: int):
    # Up to 3 photos; return ordered gallery
    return conn.execute(
        """
        SELECT photo_order, image_path
        FROM ResortRoomPhotos
        WHERE room_id = ?
          AND image_path IS NOT NULL
          AND image_path != ''
        ORDER BY photo_order ASC
        """,
        (room_id,),
    ).fetchall()



def _get_bus_pricing(conn):
    return conn.execute("SELECT destination, price FROM BusPricing ORDER BY destination").fetchall()


def _get_exclusive_price(conn) -> float:
    row = conn.execute("SELECT exclusive_price FROM ResortOptions WHERE id = 1").fetchone()
    return float(row["exclusive_price"]) if row else 0.0


def _get_rentable_appliances(conn):
    return conn.execute("SELECT id, name, price FROM RentableAppliances ORDER BY name").fetchall()


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except Exception:
        return None


def _normalize_time(value: str, default: str) -> str:
    candidate = (value or "").strip()
    try:
        return dt.time.fromisoformat(candidate).strftime("%H:%M")
    except Exception:
        return default


def _parse_datetime(value: str) -> dt.datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return dt.datetime.fromisoformat(raw)
    except Exception:
        return None


def _ensure_upload_folder() -> str:
    """Get the unified uploads folder path from config."""
    folder = app.config.get("UPLOAD_FOLDER")
    if not folder:
        # Fallback to project root static/uploads
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.join(project_root, "static", "uploads")
    os.makedirs(folder, exist_ok=True)
    return folder


ALLOWED_IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

def _save_uploaded_room_image(file_storage) -> str | None:
    """Save uploaded room image and return relative path."""
    if not file_storage or not file_storage.filename:
        return None
    
    upload_dir = _ensure_upload_folder()
    raw_name = secure_filename(file_storage.filename)
    if not raw_name:
        return None
    
    # Validate file extension (jpg, jpeg, png, webp only)
    stem, ext = os.path.splitext(raw_name)
    ext_lower = ext.lower()
    if ext_lower not in ALLOWED_IMAGE_EXTENSIONS:
        logger.warning(f"Invalid image extension: {ext}")
        return None
    
    # Generate unique filename
    unique_name = f"room_{dt.datetime.now().strftime('%Y%m%d%H%M%S%f')}_{stem}{ext_lower}"
    save_path = os.path.join(upload_dir, unique_name)
    
    try:
        file_storage.save(save_path)
        logger.info(f"Room image saved: {save_path}")
        # Return relative path for static serves (uploads/filename.jpg)
        return f"uploads/{unique_name}"
    except Exception as e:
        logger.error(f"Failed to save room image: {e}")
        return None


def _send_admin_email(subject: str, message: str) -> None:
    """Send email to admin if email notifications are enabled."""
    conn = get_db_connection()
    admin = conn.execute("SELECT email, email_enabled FROM Admin LIMIT 1").fetchone()
    conn.close()

    if not admin or not admin["email"] or admin["email_enabled"] == 0:
        return

    if not (
        app.config.get("MAIL_SERVER")
        and app.config.get("MAIL_USERNAME")
        and app.config.get("MAIL_PASSWORD")
    ):
        return

    try:
        msg = Message(subject=subject, recipients=[admin["email"]], body=message)
        mail.send(msg)
    except Exception:
        pass


@app.context_processor
def inject_site_settings():
    """Inject legacy site settings + CMS footer/contact data into all templates.

    Keeps existing behavior (WebsiteSettings) while adding:
      - cms_contact_info
      - cms_social_links
      - cms_footer_content

    Templates can hide empty optional fields gracefully.
    """
    conn = None
    try:
        conn = get_db_connection(timeout=5.0)

        # Legacy settings (used across the site)
        settings = conn.execute("SELECT * FROM WebsiteSettings WHERE id = 1").fetchone()

        # New CMS contact/footer settings
        contact = conn.execute("SELECT * FROM CMS_ContactInfo WHERE id = 1").fetchone()
        footer = conn.execute("SELECT * FROM CMS_FooterContent WHERE id = 1").fetchone()

        # Social links are stored in CMS_SocialLinks as well as in CMS_ContactInfo.
        # We prefer CMS_SocialLinks if present; fallback to CMS_ContactInfo columns.
        social_rows = conn.execute(
            "SELECT platform, href, is_visible, link_order FROM CMS_SocialLinks ORDER BY link_order ASC, id ASC"
        ).fetchall()

        # Fallback: build social list from contact info columns if social rows are empty.
        social_list = []
        if social_rows:
            for r in social_rows:
                if (r["is_visible"] or 0) != 1:
                    continue
                social_list.append({
                    "platform": r["platform"],
                    "href": r["href"],
                    "is_visible": 1,
                    "link_order": r["link_order"] or 0,
                })
        elif contact:
            # Map contact-info columns to platform names used in the admin form.
            def _maybe_add(platform: str, href: str):
                if href and str(href).strip():
                    social_list.append({"platform": platform, "href": href, "is_visible": 1, "link_order": 0})

            _maybe_add("facebook", contact.get("facebook_url") if hasattr(contact, 'get') else contact["facebook_url"])
            _maybe_add("instagram", contact.get("instagram_url") if hasattr(contact, 'get') else contact["instagram_url"])
            _maybe_add("x", contact.get("x_url") if hasattr(contact, 'get') else contact["x_url"])
            _maybe_add("tiktok", contact.get("tiktok_url") if hasattr(contact, 'get') else contact["tiktok_url"])
            _maybe_add("youtube", contact.get("youtube_url") if hasattr(contact, 'get') else contact["youtube_url"])

        # Normalize: filter out empty hrefs
        social_list = [s for s in social_list if s.get("href") and str(s.get("href")).strip()]

        conn.close()
        return {
            "site_settings": settings,
            "cms_contact_info": contact,
            "cms_social_links": social_list,
            "cms_footer_content": footer,
        }

    except Exception as e:
        logger.warning(f"Could not load CMS contact/footer data (non-fatal): {e}")
        if conn:
            try:
                conn.close()
            except:
                pass
        return {"site_settings": None, "cms_contact_info": None, "cms_social_links": [], "cms_footer_content": None}



@app.route('/', methods=['GET', 'POST'])
def home():
    bookings = []
    full_name = ''
    phone = ''
    
    if request.method == 'POST':
        full_name = (request.form.get('full_name', '').strip()).lower()
        phone = request.form.get('phone', '').strip()
        
        if not full_name:
            flash("Please enter your full name.", "error")
        else:
            conn = get_db_connection()
            
            if phone:
                bus_query = """
                    SELECT id, name, email, contact, pickup, destination, datetime, checkout, passengers, 
                           price, status, 'bus' as type, created_at
                    FROM BusBookings 
                    WHERE LOWER(TRIM(name)) = ? AND LOWER(TRIM(contact)) = ?
                    ORDER BY created_at DESC
                """
                bus_bookings = conn.execute(bus_query, (full_name, phone.lower())).fetchall()
            else:
                bus_query = """
                    SELECT id, name, email, contact, pickup, destination, datetime, checkout, passengers, 
                           price, status, 'bus' as type, created_at
                    FROM BusBookings 
                    WHERE LOWER(TRIM(name)) = ?
                    ORDER BY created_at DESC
                """
                bus_bookings = conn.execute(bus_query, (full_name,)).fetchall()
            
            if phone:
                resort_query = """
                    SELECT id, name, email, contact, checkin, checkout, checkin_time, checkout_time, guests, room_type, 
                           price, status, 'resort' as type, created_at
                    FROM ResortBookings 
                    WHERE LOWER(TRIM(name)) = ? AND LOWER(TRIM(contact)) = ?
                    ORDER BY created_at DESC
                """
                resort_bookings = conn.execute(resort_query, (full_name, phone.lower())).fetchall()
            else:
                resort_query = """
                    SELECT id, name, email, contact, checkin, checkout, checkin_time, checkout_time, guests, room_type, 
                           price, status, 'resort' as type, created_at
                    FROM ResortBookings 
                    WHERE LOWER(TRIM(name)) = ?
                    ORDER BY created_at DESC
                """
                resort_bookings = conn.execute(resort_query, (full_name,)).fetchall()
            
            bookings = list(bus_bookings) + list(resort_bookings)
            bookings.sort(key=lambda x: x['created_at'], reverse=True)
            conn.close()
    
    return render_template('index.html', bookings=bookings, full_name=full_name, phone=phone)


def _finalize_status_message(current_status: str, action: str, booking_type: str) -> str:
    """Return a user-friendly message when a booking can't be acted on."""
    if current_status == "Cancelled":
        return f"This {booking_type} booking has already been cancelled."
    if current_status == "Confirmed":
        return f"This {booking_type} booking is already confirmed."
    return f"This {booking_type} booking is already finalized."


@app.route("/bus/respond/<int:booking_id>", methods=["POST"])
def bus_respond(booking_id: int):
    decision = (request.form.get("decision", "") or "").strip().lower()
    if decision not in ("confirm", "cancel"):
        flash("Invalid booking action.", "error")
        return redirect(url_for("home"))

    full_name = (request.form.get("full_name", "") or "").strip().lower()
    phone = (request.form.get("phone", "") or "").strip().lower()
    if not full_name:
        flash("Missing customer name for booking confirmation.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT id, name, contact, status, price, datetime FROM BusBookings WHERE id = ?",
            (booking_id,),
        ).fetchone()
        if not booking:
            flash("Bus booking not found.", "error")
            return redirect(url_for("home"))

        booking_name = (booking["name"] or "").strip().lower()
        booking_contact = (booking["contact"] or "").strip().lower()
        if booking_name != full_name or (phone and booking_contact != phone):
            flash("Booking verification failed. Please search using the correct name/contact.", "error")
            return redirect(url_for("home"))

        try:
            price_val = float(booking["price"] or 0)
        except (ValueError, TypeError):
            price_val = 0.0
        if price_val <= 0:
            flash("This booking is still waiting for admin price update.", "error")
            return redirect(url_for("home"))
        if booking["status"] != "Pending":
            flash(_finalize_status_message(booking["status"], decision, "bus"), "error")
            return redirect(url_for("home"))

        new_status = "Confirmed" if decision == "confirm" else "Cancelled"
        conn.execute("UPDATE BusBookings SET status = ? WHERE id = ?", (new_status, booking_id))
        if new_status == "Cancelled":
            # Centralized cancellation workflow (audit + admin notification) to ensure consistency.
            cancel_booking(conn, 'bus', booking_id, 'customer')
        conn.commit()
        flash(f"Bus booking {new_status.lower()} successfully.", "success")

    except Exception as exc:
        conn.rollback()

        logger.error("Database error in bus_respond for booking %s: %s", booking_id, exc, exc_info=True)
        flash("A database error occurred. Please try again in a moment.", "error")
    except Exception as exc:
        conn.rollback()
        logger.error("Unexpected error in bus_respond for booking %s: %s", booking_id, exc, exc_info=True)
        flash("An unexpected error occurred while processing your request. Please try again.", "error")
    finally:
        conn.close()
    return redirect(url_for("home"))


@app.route("/resort/respond/<int:booking_id>", methods=["POST"])
def resort_respond(booking_id: int):
    decision = (request.form.get("decision", "") or "").strip().lower()
    if decision not in ("confirm", "cancel"):
        flash("Invalid booking action.", "error")
        return redirect(url_for("home"))

    full_name = (request.form.get("full_name", "") or "").strip().lower()
    phone = (request.form.get("phone", "") or "").strip().lower()
    if not full_name:
        flash("Missing customer name for booking confirmation.", "error")
        return redirect(url_for("home"))

    conn = get_db_connection()
    try:
        booking = conn.execute(
            "SELECT id, name, contact, status, price, checkin FROM ResortBookings WHERE id = ?",
            (booking_id,),
        ).fetchone()
        if not booking:
            flash("Resort booking not found.", "error")
            return redirect(url_for("home"))

        booking_name = (booking["name"] or "").strip().lower()
        booking_contact = (booking["contact"] or "").strip().lower()
        if booking_name != full_name or (phone and booking_contact != phone):
            flash("Booking verification failed. Please search using the correct name/contact.", "error")
            return redirect(url_for("home"))

        try:
            price_val = float(booking["price"] or 0)
        except (ValueError, TypeError):
            price_val = 0.0
        if price_val <= 0:
            flash("This booking is still waiting for admin price update.", "error")
            return redirect(url_for("home"))
        if booking["status"] != "Pending":
            flash(_finalize_status_message(booking["status"], decision, "resort"), "error")
            return redirect(url_for("home"))

        new_status = "Confirmed" if decision == "confirm" else "Cancelled"
        conn.execute("UPDATE ResortBookings SET status = ? WHERE id = ?", (new_status, booking_id))
        if new_status == "Cancelled":
            # Centralized cancellation workflow (audit + admin notification) to ensure consistency.
            cancel_booking(conn, 'resort', booking_id, 'customer')
        conn.commit()
        flash(f"Resort booking {new_status.lower()} successfully.", "success")

    except Exception as exc:

        conn.rollback()
        logger.error("Database error in resort_respond for booking %s: %s", booking_id, exc, exc_info=True)
        flash("A database error occurred. Please try again in a moment.", "error")
    except Exception as exc:
        conn.rollback()
        logger.error("Unexpected error in resort_respond for booking %s: %s", booking_id, exc, exc_info=True)
        flash("An unexpected error occurred while processing your request. Please try again.", "error")
    finally:
        conn.close()
    return redirect(url_for("home"))



@app.route("/bus", methods=["GET", "POST"])
def bus():
    if request.method == "POST":
        form = request.form
        passengers = int(form.get("passengers", "0") or 0)
        destination = form.get("destination", "").strip()
        checkin_raw = form.get("datetime", "").strip()
        checkout_raw = form.get("checkout", "").strip()
        checkin_dt = _parse_datetime(checkin_raw)
        checkout_dt = _parse_datetime(checkout_raw)
        if not checkin_dt or not checkout_dt or checkout_dt <= checkin_dt:
            flash("Invalid bus schedule. Check-out must be after check-in.", "error")
            return redirect(url_for("bus"))
        checkin_text = checkin_dt.strftime("%Y-%m-%d %H:%M:%S")
        checkout_text = checkout_dt.strftime("%Y-%m-%d %H:%M:%S")
        created_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        overlap = conn.execute(
            """
            SELECT 1 FROM BusBookings
            WHERE status IN ('Pending','Confirmed')
              AND NOT (? <= COALESCE(checkin, datetime) OR ? >= COALESCE(checkout, COALESCE(checkin, datetime)))
            LIMIT 1
            """,
            (checkout_text, checkin_text),
        ).fetchone()
        if overlap:
            conn.close()
            flash("Selected bus date/time is unavailable. Please choose another schedule.", "error")
            return redirect(url_for("bus"))
        price_row = conn.execute(
            "SELECT price FROM BusPricing WHERE destination = ?",
            (destination,),
        ).fetchone()
        price = float(price_row["price"]) if price_row else 0.0
        cursor = conn.execute(
            """
            INSERT INTO BusBookings (name, contact, email, pickup, destination, datetime, checkin, checkout, passengers, price, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                form.get("name", "").strip(),
                form.get("contact", "").strip(),
                form.get("email", "").strip(),
                form.get("pickup", "").strip(),
                destination,
                checkin_text,
                checkin_text,
                checkout_text,
                passengers,
                float(price),
                created_at,
            ),
        )
        booking_id = cursor.lastrowid
        conn.commit()
        notif_msg = f"New bus booking from {form.get('name', '').strip()}: {destination} on {created_at}"

        safe_create_notification(conn, notif_msg, 'booking_bus')
        conn.commit()
        conn.close()
        _send_admin_email("New Bus Booking", notif_msg)
        return redirect(url_for("booking_success", booking_type="bus", booking_id=booking_id))


    return render_template("bus.html")


@app.route("/resort", methods=["GET", "POST"])
def resort():
    from shared.db_connection import get_db_connection as _ggc
    import logging
    logging.getLogger(__name__).info("[ROUTE ENTRY] /resort got_connection=%s get_db_connection_from=%s", type(_ggc()).__name__, _ggc.__module__)
    if request.method == "POST":
        form = request.form
        conn = get_db_connection()

        checkin = (form.get("checkin", "") or "").strip()
        checkout = (form.get("checkout", "") or "").strip()
        checkin_time = _normalize_time(form.get("checkin_time", "14:00"), "14:00")
        checkout_time = _normalize_time(form.get("checkout_time", "12:00"), "12:00")
        d1 = _parse_date(checkin)
        d2 = _parse_date(checkout)
        if not d1 or not d2 or d2 <= d1:
            conn.close()
            flash("Invalid dates (check-out must be after check-in).", "error")
            return redirect(url_for("resort"))

        room_types = request.form.getlist("room_types[]")
        is_exclusive = form.get("is_exclusive") == "on"
        available_rooms = get_available_rooms_for_dates(conn, checkin, checkout)
        avail_ids = {str(r["id"]) for r in available_rooms}
        room_name_map = {str(r["id"]): f"{r['name']} ({r['room_type']})" for r in available_rooms}

        if is_exclusive:
            overlap = conn.execute(
                """
                SELECT 1 FROM ResortBookings
                WHERE status IN ('Pending','Confirmed')
                  AND NOT (? <= checkin OR ? >= checkout)
                LIMIT 1
                """,
                (checkout, checkin),
            ).fetchone()
            if overlap:
                conn.close()
                flash("Dates not available for exclusive booking.", "error")
                return redirect(url_for("resort"))
            exclusive_room_types = sorted(avail_ids)
            if not exclusive_room_types:
                conn.close()
                flash("No rooms are available for exclusive booking on the selected dates.", "error")
                return redirect(url_for("resort"))
            selected_room_labels = [room_name_map[rid] for rid in exclusive_room_types if rid in room_name_map]
            price_per_night = 0.0
            room_instances = json.dumps(exclusive_room_types)
            room_type = "Exclusive Resort - " + ", ".join(selected_room_labels)
        else:
            if not room_types:
                conn.close()
                flash("Please select at least one room.", "error")
                return redirect(url_for("resort"))
            if not set(room_types) <= avail_ids:
                conn.close()
                flash("One or more selected rooms are not available for your dates.", "error")
                return redirect(url_for("resort"))
            selected_prices = [r["price"] for r in available_rooms if str(r["id"]) in room_types]
            selected_room_labels = [room_name_map[rid] for rid in room_types if rid in room_name_map]
            price_per_night = sum(selected_prices)
            room_instances = json.dumps(room_types)
            room_type = ", ".join(selected_room_labels)

        nights = (d2 - d1).days
        room_total = float(price_per_night) * float(nights)
        created_at = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payment_method = (form.get("payment_method", "Cash") or "Cash").strip()
        if payment_method not in ("Cash", "GCash", "Bank Transfer"):
            payment_method = "Cash"

        is_exclusive = 1 if form.get("is_exclusive") == "on" else 0
        daily_exclusive_price = _get_exclusive_price(conn) if is_exclusive else 0.0
        exclusive_price = daily_exclusive_price * nights  # Per-day calculation

        appliances = _get_rentable_appliances(conn)
        selected_appliances = []
        appliances_cost = 0.0
        for a in appliances:
            selected = form.get(f"appliance_selected_{a['id']}") == "on"
            qty_raw = form.get(f"appliance_qty_{a['id']}", "")
            legacy_qty = 0
            if qty_raw:
                try:
                    legacy_qty = int(qty_raw or 0)
                except ValueError:
                    legacy_qty = 0
            qty = 1 if selected else max(legacy_qty, 0)
            if qty > 0:
                item_total = float(a["price"]) * qty
                appliances_cost += item_total
                selected_appliances.append(
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "qty": qty,
                        "price": float(a["price"]),
                        "total": item_total,
                    }
                )

        total_cost = room_total + exclusive_price + appliances_cost

        cursor = conn.execute(
            """
            INSERT INTO ResortBookings (
                name, contact, email, checkin, checkout, guests, room_type, payment_method,
                checkin_time, checkout_time, is_exclusive, exclusive_price, appliances_json, appliances_cost,
                price_per_night, room_instances, total_cost, price, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                form.get("name", "").strip(),
                form.get("contact", "").strip(),
                form.get("email", "").strip(),
                checkin,
                checkout,
                int(form.get("guests", "0") or 0),
                room_type,
                payment_method,
                checkin_time,
                checkout_time,
                is_exclusive,
                exclusive_price,
                json.dumps(selected_appliances),
                appliances_cost,
                price_per_night,
                room_instances,
                total_cost,
                total_cost,
                created_at,
            ),
        )
        booking_id = cursor.lastrowid
        conn.commit()
        notif_msg = f"New resort booking from {form.get('name', '').strip()} {checkin}-{checkout}"

        safe_create_notification(conn, notif_msg, 'booking_resort')
        conn.commit()
        conn.close()
        _send_admin_email("New Resort Booking", notif_msg)
        return redirect(url_for("booking_success", booking_type="resort", booking_id=booking_id))


    conn = get_db_connection()
    pricing_rows = _get_room_pricing_rows(conn)
    resort_rooms = _get_resort_rooms(conn)
    resort_rooms_list = []
    for room in resort_rooms:
        room_dict = dict(room)

        # Prefer multi-photo gallery (new system)
        photos_rows = _get_resort_room_photos(conn, room_dict["id"])
        photos = [r["image_path"] for r in photos_rows if r["image_path"]]

        # Backwards-compatible fallback to legacy single image_path
        if not photos and room_dict.get("image_path"):
            photos = [room_dict["image_path"]]

        room_dict["photos"] = photos

        price_row = conn.execute(
            "SELECT price_per_night FROM RoomPricing WHERE room_type = ?",
            (room['room_type'],),
        ).fetchone()
        room_dict['price'] = float(price_row['price_per_night']) if price_row else 0

        resort_rooms_list.append(room_dict)

    pricing = {r["room_type"]: float(r["price_per_night"]) for r in pricing_rows}
    pricing_rows_list = [dict(r) for r in pricing_rows]
    exclusive_price = _get_exclusive_price(conn)
    appliances = _get_rentable_appliances(conn)
    conn.close()
    return render_template(
        "resort.html",
        pricing=pricing,
        pricing_rows=pricing_rows_list,
        resort_rooms=resort_rooms_list,
        exclusive_price=exclusive_price,
        appliances=appliances,
    )


@app.route("/api/availability/bus")
def bus_availability():
    import logging
    conn = get_db_connection()
    logging.getLogger(__name__).info("[ROUTE ENTRY] /api/availability/bus conn_type=%s get_db_connection_from=%s", type(conn).__name__, get_db_connection.__module__)

    rows = conn.execute(
        "SELECT name, datetime, checkin, checkout, status FROM BusBookings WHERE status IN ('Pending','Confirmed')"
    ).fetchall()
    conn.close()

    events = []
    unavailable_dates: set[str] = set()
    for r in rows:
        start_raw = (r["checkin"] or r["datetime"] or "").strip()
        end_raw = (r["checkout"] or start_raw).strip()
        start_date = _parse_date(start_raw[:10])
        end_date = _parse_date(end_raw[:10])
        if not start_date:
            continue
        if not end_date or end_date < start_date:
            end_date = start_date

        # Build unavailable dates set for client-side conflict checking
        day = start_date
        while day <= end_date:
            unavailable_dates.add(day.isoformat())
            day += dt.timedelta(days=1)

        events.append({
            "title": f"{r['name']} ({r['status']})",
            "start": start_raw,
            "end": end_raw,
            "allDay": False,
            "display": "block",
            "backgroundColor": "#bbf7d0" if r["status"] == "Confirmed" else "#fde68a",
            "borderColor": "#22c55e" if r["status"] == "Confirmed" else "#f59e0b",
            "textColor": "#000000"
        })

    return jsonify({"events": events, "unavailable_dates": sorted(unavailable_dates)})



@app.route("/booking/success")
def booking_success():
    booking_type = request.args.get("booking_type", "").strip().lower()
    booking_id = request.args.get("booking_id", "").strip()

    # Load popup content dynamically from CMS_Homepage
    conn = get_db_connection()
    try:
        popup = conn.execute(
            """
            SELECT booking_success_popup_title,
                   booking_success_popup_message,
                   booking_success_popup_show_icon
            FROM CMS_Homepage
            WHERE id = 1
            """
        ).fetchone()
    finally:
        conn.close()

    # Fallbacks (in case DB row/columns are missing)
    popup_title = (popup["booking_success_popup_title"] if popup and popup["booking_success_popup_title"] else "Booking Submitted Successfully!")
    popup_message = (popup["booking_success_popup_message"] if popup and popup["booking_success_popup_message"] else "Thank you for choosing BusResort!\nYour booking has been successfully submitted and is now awaiting confirmation from our administrator. We appreciate your trust in our service and look forward to serving you. Please keep your booking reference number for future inquiries.")
    popup_ok_text = "Okay"
    popup_view_text = "View Booking"
    popup_show_icon = bool(int(popup["booking_success_popup_show_icon"])) if popup and popup["booking_success_popup_show_icon"] is not None else True

    return render_template(
        "success.html",
        type=booking_type,
        id=booking_id,
        booking_success_popup_title=popup_title,
        booking_success_popup_message=popup_message,
        booking_success_popup_ok_text=popup_ok_text,
        booking_success_popup_view_text=popup_view_text,
        booking_success_popup_show_icon=popup_show_icon,
    )


@app.route("/feedback", methods=["GET", "POST"])

def feedback():
    import logging
    conn = get_db_connection()
    logging.getLogger(__name__).info("[ROUTE ENTRY] /feedback conn_type=%s get_db_connection_from=%s", type(conn).__name__, get_db_connection.__module__)
    conn.close()
    feedback_list = []
    
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        raw_service_type = request.form.get("service_type", "").strip()
        service_type_map = {
            "bus": "Bus Rental",
            "bus rental": "Bus Rental",
            "resort": "Resort Booking",
            "resort booking": "Resort Booking",
        }
        service_type = service_type_map.get(raw_service_type.lower(), raw_service_type)
        rating_str = request.form.get("rating", "").strip()
        comment = request.form.get("comment", "").strip()

        allowed_service_types = {"Bus Rental", "Resort Booking"}
        if not all([name, email, service_type, rating_str, comment]):
            flash("Please fill all fields.", "error")
        elif service_type not in allowed_service_types:
            flash("Please choose a valid service type.", "error")
        elif len(comment) < 10:
            flash("Comment must be at least 10 characters.", "error")
        elif "@" not in email:
            flash("Please enter a valid email address.", "error")
        else:
            try:
                rating = int(rating_str)
                if 1 <= rating <= 5:
                    conn = get_db_connection()
                    conn.execute(
                        """
                        INSERT INTO Feedback (name, email, service_type, rating, comment)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (name, email, service_type, rating, comment)
                    )
                    conn.commit()
                    notif_msg = f"New review from {name} ({service_type}): {rating}/5"
                    safe_create_notification(conn, notif_msg, 'review')
                    conn.commit()
                    conn.close()
                    _send_admin_email("New Feedback/Review", notif_msg)
                    flash("Thank you for your feedback!", "success")
                else:
                    flash("Rating must be between 1 and 5.", "error")
            except ValueError:
                flash("Invalid rating value.", "error")
    
    conn = get_db_connection()
    feedback_list = conn.execute(
        "SELECT * FROM Feedback ORDER BY date_created DESC LIMIT 10"
    ).fetchall()
    conn.close()
    
    return render_template("feedback.html", feedback=feedback_list)


@app.route("/api/availability/resort")
def resort_availability():
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT name, checkin, checkout, checkin_time, checkout_time, status, room_instances FROM ResortBookings WHERE status IN ('Pending','Confirmed')"
    ).fetchall()
    conn.close()

    events = []
    unavailable_dates: set[str] = set()
    for r in rows:
        rooms = []
        if r["room_instances"]:
            try:
                rooms = json.loads(r["room_instances"])
            except Exception:
                rooms = []

        checkin_date = (r["checkin"] or "").strip()
        checkout_date = (r["checkout"] or "").strip()
        start_date = _parse_date(checkin_date)
        end_date = _parse_date(checkout_date)
        if not start_date:
            continue
        if not end_date or end_date < start_date:
            end_date = start_date

        # Build unavailable date set (inclusive), same API behavior pattern as bus.
        day = start_date
        while day <= end_date:
            unavailable_dates.add(day.isoformat())
            day += dt.timedelta(days=1)

        checkin_time = (r["checkin_time"] or "14:00").strip()
        checkout_time = (r["checkout_time"] or "12:00").strip()
        start = f"{start_date.isoformat()}T{checkin_time}"
        end = f"{end_date.isoformat()}T{checkout_time}"

        events.append({
            "title": f"{r['name']} ({r['status']})",
            "start": start,
            "end": end,
            "allDay": False,
            "display": "block",
            "backgroundColor": "#bbf7d0" if r["status"] == "Confirmed" else "#fde68a",
            "borderColor": "#22c55e" if r["status"] == "Confirmed" else "#f59e0b",
            "textColor": "#000000",
            "extendedProps": {
                "rooms": rooms
            }
        })

    return jsonify({"events": events, "unavailable_dates": sorted(unavailable_dates)})


@app.route("/api/available_rooms")
def available_rooms():
    checkin = request.args.get('checkin')
    checkout = request.args.get('checkout')
    if not checkin or not checkout:
        return jsonify({'rooms': []})
    conn = get_db_connection()
    rooms = get_available_rooms_for_dates(conn, checkin, checkout)
    conn.close()
    return jsonify({'rooms': rooms})


# Serve uploads from unified static/uploads folder (project root)
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files from project's static/uploads folder."""
    from flask import send_from_directory
    upload_folder = app.config.get("UPLOAD_FOLDER")
    if not upload_folder:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upload_folder = os.path.join(project_root, "static", "uploads")
    return send_from_directory(upload_folder, filename)


# Legacy route - redirect to unified uploads
@app.route('/main_uploads/<path:filename>')
def serve_main_upload(filename):
    """Legacy route - redirect to unified uploads."""
    return redirect(url_for('serve_upload', filename=filename))


# Block any /admin access on the main site
@app.route("/admin")
@app.route("/admin/<path:subpath>")
def block_admin(subpath=None):
    return redirect(url_for("home"))


if __name__ == '__main__':
    # Initialize database and ensure WebsiteSettings table exists
    init_db()
    init_website_settings()
    app.run(debug=False, host="127.0.0.1", port=5000)

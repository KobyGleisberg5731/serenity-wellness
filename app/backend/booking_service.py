"""Booking creation, status updates, and messaging."""
import json

from .database import get_db, now_iso
from .device_service import get_device_context, is_device_blocked
from .email_service import send_booking_received, send_booking_status_update
from .helpers import generate_booking_id


def _booking_details(conn, booking: dict) -> dict:
    out = dict(booking)
    if booking.get("service_id"):
        row = conn.execute("SELECT name FROM services WHERE id = ?", (booking["service_id"],)).fetchone()
        out["service_name"] = row["name"] if row else ""
    else:
        out["service_name"] = ""
    if booking.get("pricing_id"):
        row = conn.execute(
            "SELECT label, duration_minutes, price FROM pricing_tiers WHERE id = ?",
            (booking["pricing_id"],),
        ).fetchone()
        if row:
            out["pricing_label"] = row["label"]
            out["pricing_duration"] = row["duration_minutes"]
            out["pricing_price"] = row["price"]
        else:
            out["pricing_label"] = ""
    else:
        out["pricing_label"] = ""
    if booking.get("masseuse_id"):
        row = conn.execute("SELECT name FROM masseuses WHERE id = ?", (booking["masseuse_id"],)).fetchone()
        out["masseuse_name"] = row["name"] if row else ""
    else:
        out["masseuse_name"] = ""
    return out


MAX_ACTIVE_BOOKINGS_PER_EMAIL = 3
ACTIVE_BOOKING_STATUSES = ("pending", "payment_pending", "payment_submitted")
SUSPENDED_STATUS = "suspended"


def count_active_bookings_for_email(email: str) -> int:
    with get_db() as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS c FROM bookings
               WHERE lower(email) = ? AND status IN (?, ?, ?)""",
            (email.strip().lower(), *ACTIVE_BOOKING_STATUSES),
        ).fetchone()
    return int(row["c"] or 0)


def create_booking(data: dict, device_ctx: dict | None = None) -> tuple[dict | None, str]:
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    phone = (data.get("phone") or "").strip()
    zip_code = (data.get("zip_code") or "").strip()
    preferred = (data.get("preferred_datetime") or "").strip()
    message = (data.get("message") or "").strip()
    service_id = data.get("service_id") or None
    pricing_id = data.get("pricing_id") or None
    masseuse_id = data.get("masseuse_id") or None
    ctx = device_ctx or get_device_context(data=data)

    if is_device_blocked(ctx.get("device_id", ""), ctx.get("client_ip", ""), email):
        return None, "Bookings from this device are not permitted. Please contact us for assistance."

    if not all([name, email, zip_code, preferred]):
        return None, "Please fill in all required fields."

    if count_active_bookings_for_email(email) >= MAX_ACTIVE_BOOKINGS_PER_EMAIL:
        return None, (
            "You already have 3 open bookings. Please wait until an existing booking "
            "is confirmed or completed before requesting another session."
        )

    if service_id:
        try:
            service_id = int(service_id)
        except (TypeError, ValueError):
            service_id = None
    if pricing_id:
        try:
            pricing_id = int(pricing_id)
        except (TypeError, ValueError):
            pricing_id = None
    if masseuse_id:
        try:
            masseuse_id = int(masseuse_id)
        except (TypeError, ValueError):
            masseuse_id = None

    booking_id = generate_booking_id()
    ts = now_iso()

    with get_db() as conn:
        while conn.execute("SELECT id FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone():
            booking_id = generate_booking_id()
        conn.execute(
            """INSERT INTO bookings
               (booking_id, name, email, phone, zip_code, service_id, pricing_id, masseuse_id,
                preferred_datetime, message, status, client_ip, user_agent, device_id, device_fingerprint,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)""",
            (
                booking_id, name, email, phone, zip_code, service_id, pricing_id, masseuse_id,
                preferred, message,
                ctx.get("client_ip", ""), ctx.get("user_agent", ""),
                ctx.get("device_id", ""), ctx.get("device_fingerprint", ""),
                ts, ts,
            ),
        )
        conn.execute(
            "INSERT INTO booking_status_log (booking_id, status, note, created_at) VALUES (?, 'pending', ?, ?)",
            (booking_id, "Booking submitted", ts),
        )
        conn.execute(
            """INSERT INTO booking_messages (booking_id, sender_type, sender_name, body, created_at)
               VALUES (?, 'system', 'System', ?, ?)""",
            (booking_id, "Your request is in. We'll confirm your session shortly.", ts),
        )
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        booking = _booking_details(conn, dict(row))

    send_booking_received(booking)
    try:
        from .telegram_service import notify_new_booking
        notify_new_booking(booking)
    except Exception:
        pass

    return booking, ""


def update_booking_status(booking_id: str, new_status: str, note: str = "", source: str = "admin") -> dict | None:
    ts = now_iso()
    status_label = new_status.replace("_", " ").title()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        old_status = row["status"]
        conn.execute(
            "UPDATE bookings SET status=?, updated_at=? WHERE booking_id=?",
            (new_status, ts, booking_id),
        )
        conn.execute(
            "INSERT INTO booking_status_log (booking_id, status, note, created_at) VALUES (?, ?, ?, ?)",
            (booking_id, new_status, (note or "").strip(), ts),
        )
        conn.execute(
            """INSERT INTO booking_messages (booking_id, sender_type, sender_name, body, created_at)
               VALUES (?, 'system', 'System', ?, ?)""",
            (booking_id, f"Status updated to {status_label}", ts),
        )
        booking = _booking_details(conn, dict(row))
        booking["status"] = new_status

    send_booking_status_update(booking, new_status, note=note)
    return booking


def resolve_booking_access(booking_id: str, email: str) -> tuple[dict | None, str | None]:
    """Return (booking, error_code) where error_code is 'not_found' or 'suspended'."""
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM bookings WHERE booking_id = ? AND lower(email) = ?",
            (booking_id, email.strip().lower()),
        ).fetchone()
        if not row:
            return None, "not_found"
        booking = dict(row)
        if booking.get("status") == SUSPENDED_STATUS:
            return None, "suspended"
        return _booking_details(conn, booking), None


def verify_booking_access(booking_id: str, email: str) -> dict | None:
    booking, _err = resolve_booking_access(booking_id, email)
    return booking


def get_booking_messages(booking_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM booking_messages WHERE booking_id = ? ORDER BY created_at",
            (booking_id,),
        ).fetchall()
    out = []
    for r in rows:
        msg = dict(r)
        try:
            msg["meta"] = json.loads(msg.get("meta_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            msg["meta"] = {}
        out.append(msg)
    return out


def add_booking_message(
    booking_id: str,
    sender_type: str,
    body: str,
    sender_name: str = "",
    *,
    message_type: str = "text",
    attachment_path: str = "",
    meta: dict | None = None,
) -> dict | None:
    body = (body or "").strip()
    if not body:
        return None
    ts = now_iso()
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        if dict(row).get("status") == SUSPENDED_STATUS and sender_type == "customer":
            return None
        cur = conn.execute(
            """INSERT INTO booking_messages
               (booking_id, sender_type, sender_name, body, message_type, attachment_path, meta_json, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                booking_id, sender_type, sender_name or sender_type.title(), body,
                message_type or "text", attachment_path or "", json.dumps(meta or {}), ts,
            ),
        )
        conn.execute("UPDATE bookings SET updated_at=? WHERE booking_id=?", (ts, booking_id))
        row = conn.execute("SELECT * FROM booking_messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    msg = dict(row)
    try:
        msg["meta"] = json.loads(msg.get("meta_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        msg["meta"] = {}
    booking = None
    with get_db() as conn:
        brow = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if brow:
            booking = _booking_details(conn, dict(brow))

    if sender_type == "customer" and booking:
        try:
            from .email_service import send_admin_customer_message
            send_admin_customer_message(booking, body, sender_name)
        except Exception:
            pass
    elif sender_type == "admin" and booking:
        try:
            from .email_service import send_booking_chat_message
            send_booking_chat_message(booking, body)
        except Exception:
            pass

    if sender_type == "customer":
        try:
            from .telegram_service import notify_new_message
            notify_new_message(booking_id, msg, booking)
        except Exception:
            pass
    return msg

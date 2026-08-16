"""Device identity capture, blocklist, and access checks."""
from __future__ import annotations

from flask import Request, request

from .database import get_db, now_iso


def get_client_ip(req: Request | None = None) -> str:
    req = req or request
    forwarded = (req.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    real_ip = (req.headers.get("X-Real-IP") or "").strip()
    if real_ip:
        return real_ip
    return (req.remote_addr or "").strip()


def get_device_id_from_request(req: Request | None = None) -> str:
    req = req or request
    device_id = (
        (req.headers.get("X-Device-Id") or "").strip()
        or (req.cookies.get("serenity_device_id") or "").strip()
        or (req.form.get("device_id") or "").strip()
    )
    if not device_id and req.is_json:
        payload = req.get_json(silent=True) or {}
        device_id = (payload.get("device_id") or "").strip()
    return device_id


def get_device_context(req: Request | None = None, data: dict | None = None) -> dict:
    req = req or request
    payload = data or (req.get_json(silent=True) if req else None) or {}
    if hasattr(req, "form"):
        payload = {**req.form.to_dict(), **payload}
    return {
        "client_ip": get_client_ip(req),
        "user_agent": (req.headers.get("User-Agent") or "")[:500],
        "device_id": (payload.get("device_id") or get_device_id_from_request(req)).strip(),
        "device_fingerprint": (payload.get("device_fingerprint") or "").strip()[:500],
    }


def is_device_blocked(device_id: str = "", ip_address: str = "", email: str = "") -> bool:
    device_id = (device_id or "").strip()
    ip_address = (ip_address or "").strip()
    email = (email or "").strip().lower()
    if not any([device_id, ip_address, email]):
        return False
    with get_db() as conn:
        row = conn.execute(
            """SELECT id FROM blocked_devices
               WHERE (device_id != '' AND device_id = ?)
                  OR (ip_address != '' AND ip_address = ?)
                  OR (email != '' AND lower(email) = ?)
               LIMIT 1""",
            (device_id, ip_address, email),
        ).fetchone()
    return bool(row)


def block_device(
    *,
    device_id: str = "",
    ip_address: str = "",
    email: str = "",
    reason: str = "",
    source_booking_id: str = "",
    blocked_by: str = "admin",
) -> tuple[bool, str]:
    device_id = (device_id or "").strip()
    ip_address = (ip_address or "").strip()
    email = (email or "").strip().lower()
    if not any([device_id, ip_address, email]):
        return False, "Device ID, IP address, or email is required."
    if is_device_blocked(device_id, ip_address, email):
        return True, "Already blocked"
    with get_db() as conn:
        conn.execute(
            """INSERT INTO blocked_devices
               (device_id, ip_address, email, reason, source_booking_id, blocked_by, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (device_id, ip_address, email, reason.strip(), source_booking_id, blocked_by, now_iso()),
        )
    return True, "blocked"


def unblock_device(block_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute("DELETE FROM blocked_devices WHERE id = ?", (block_id,))
    return cur.rowcount > 0


def list_blocked_devices() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM blocked_devices ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def device_block_message(req: Request | None = None) -> str | None:
    """Return a user-facing block message, or None if access is allowed."""
    req = req or request
    ctx = get_device_context(req)
    if is_device_blocked(ctx["device_id"], ctx["client_ip"]):
        return "Access from this device has been restricted. Please contact us if you believe this is a mistake."
    return None


def attach_device_to_booking(booking_id: str, ctx: dict):
    with get_db() as conn:
        conn.execute(
            """UPDATE bookings
               SET client_ip = ?, user_agent = ?, device_id = ?, device_fingerprint = ?, updated_at = ?
               WHERE booking_id = ?""",
            (
                ctx.get("client_ip", ""),
                ctx.get("user_agent", ""),
                ctx.get("device_id", ""),
                ctx.get("device_fingerprint", ""),
                now_iso(),
                booking_id,
            ),
        )

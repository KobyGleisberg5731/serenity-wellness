"""Payment reminder emails — manual hourly + crypto expiry countdown."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from .database import get_db, now_iso
from .payment_service import (
    ACTIVE_CRYPTO_STATUSES,
    set_payment_request_status,
)

logger = logging.getLogger(__name__)

CRYPTO_REMINDER_MINUTES = (60, 30, 15, 5)
MANUAL_REMINDER_INTERVAL_SECONDS = 3600


def _parse_expires_at(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime((value or "").strip()[:19], fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _reminder_was_sent(payment_id: int | None, reminder_key: str) -> bool:
    with get_db() as conn:
        if payment_id is not None:
            row = conn.execute(
                """SELECT id FROM payment_reminder_log
                   WHERE payment_id = ? AND reminder_key = ? LIMIT 1""",
                (payment_id, reminder_key),
            ).fetchone()
            return bool(row)
        return False


def _claim_reminder(booking_id: str, payment_id: int | None, reminder_key: str) -> bool:
    """Atomically record a reminder slot; returns False if already sent."""
    with get_db() as conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO payment_reminder_log
               (booking_id, payment_id, reminder_key, sent_at)
               VALUES (?, ?, ?, ?)""",
            (booking_id, payment_id, reminder_key, now_iso()),
        )
        return cur.rowcount > 0


def _last_manual_reminder_at(booking_id: str) -> datetime | None:
    with get_db() as conn:
        row = conn.execute(
            """SELECT sent_at FROM payment_reminder_log
               WHERE booking_id = ? AND reminder_key = 'manual_hourly'
               ORDER BY sent_at DESC LIMIT 1""",
            (booking_id,),
        ).fetchone()
    if not row:
        return None
    return _parse_expires_at(row["sent_at"])


def _load_booking(booking_id: str) -> dict | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        booking = dict(row)
        if booking.get("pricing_id"):
            pr = conn.execute(
                "SELECT label, price FROM pricing_tiers WHERE id=?",
                (booking["pricing_id"],),
            ).fetchone()
            if pr:
                booking["pricing_label"] = pr["label"]
                booking["pricing_price"] = pr["price"]
    return booking


def _active_crypto_payments() -> list[dict]:
    placeholders = ",".join("?" for _ in ACTIVE_CRYPTO_STATUSES)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT * FROM booking_payments
                WHERE provider = 'nowpayments'
                  AND status IN ({placeholders})
                  AND expires_at != ''
                ORDER BY created_at DESC""",
            tuple(ACTIVE_CRYPTO_STATUSES),
        ).fetchall()
    return [dict(r) for r in rows]


def _booking_has_active_crypto(booking_id: str) -> bool:
    placeholders = ",".join("?" for _ in ACTIVE_CRYPTO_STATUSES)
    with get_db() as conn:
        row = conn.execute(
            f"""SELECT id FROM booking_payments
                WHERE booking_id = ? AND provider = 'nowpayments'
                  AND status IN ({placeholders})
                LIMIT 1""",
            (booking_id, *ACTIVE_CRYPTO_STATUSES),
        ).fetchone()
    return bool(row)


def _manual_reminder_bookings() -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM bookings WHERE status = 'payment_pending' ORDER BY updated_at DESC"
        ).fetchall()
    due = []
    for row in rows:
        booking = dict(row)
        if _booking_has_active_crypto(booking["booking_id"]):
            continue
        due.append(booking)
    return due


def _handle_crypto_expired(payment: dict, booking: dict):
    from .email_service import send_payment_expired_admin, send_payment_expired_customer
    from .telegram_service import notify_payment_expired

    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            "UPDATE booking_payments SET status='expired', updated_at=? WHERE id=?",
            (ts, payment["id"]),
        )

    req_msg_id = payment.get("request_message_id")
    if req_msg_id:
        set_payment_request_status(booking["booking_id"], "open", message_id=int(req_msg_id))
    else:
        set_payment_request_status(booking["booking_id"], "open", amount=float(payment.get("amount") or 0))

    try:
        send_payment_expired_customer(booking, payment)
    except Exception as exc:
        logger.warning("Expired payment customer email failed: %s", exc)
    try:
        send_payment_expired_admin(booking, payment)
    except Exception as exc:
        logger.warning("Expired payment admin email failed: %s", exc)
    try:
        notify_payment_expired(booking["booking_id"], payment)
    except Exception as exc:
        logger.warning("Expired payment telegram failed: %s", exc)


def _send_crypto_countdown_reminder(booking: dict, payment: dict, minutes_left: int):
    from .email_service import send_crypto_payment_reminder_customer

    key = f"crypto_{minutes_left}"
    if not _claim_reminder(booking["booking_id"], payment["id"], key):
        return
    send_crypto_payment_reminder_customer(booking, payment, minutes_left)


def _send_manual_reminder(booking: dict):
    from .email_service import send_manual_payment_reminder_customer

    if not _claim_reminder(booking["booking_id"], None, "manual_hourly"):
        return
    send_manual_payment_reminder_customer(booking)


def process_crypto_reminders():
    now = _utcnow()
    for payment in _active_crypto_payments():
        if _reminder_was_sent(payment["id"], "crypto_expired"):
            continue

        expires = _parse_expires_at(payment.get("expires_at") or "")
        if not expires:
            continue

        minutes_left = (expires - now).total_seconds() / 60.0
        booking = _load_booking(payment["booking_id"])
        if not booking:
            continue

        if minutes_left <= 0:
            if _claim_reminder(booking["booking_id"], payment["id"], "crypto_expired"):
                _handle_crypto_expired(payment, booking)
            continue

        for threshold in (5, 15, 30, 60):
            key = f"crypto_{threshold}"
            if minutes_left <= threshold and not _reminder_was_sent(payment["id"], key):
                try:
                    _send_crypto_countdown_reminder(booking, payment, threshold)
                except Exception as exc:
                    logger.warning("Crypto reminder %s failed for %s: %s", key, booking["booking_id"], exc)
                break


def process_manual_reminders():
    now = _utcnow()
    for booking in _manual_reminder_bookings():
        last = _last_manual_reminder_at(booking["booking_id"])
        if last:
            if (now - last).total_seconds() < MANUAL_REMINDER_INTERVAL_SECONDS:
                continue
        else:
            anchor = _parse_expires_at(booking.get("updated_at") or booking.get("created_at") or "")
            if anchor and (now - anchor).total_seconds() < MANUAL_REMINDER_INTERVAL_SECONDS:
                continue
        try:
            _send_manual_reminder(booking)
        except Exception as exc:
            logger.warning("Manual reminder failed for %s: %s", booking["booking_id"], exc)


def process_payment_reminders():
    process_crypto_reminders()
    process_manual_reminders()

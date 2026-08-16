"""Payment methods, NowPayments crypto invoices, and booking payment flow."""
import base64
import hashlib
import hmac
import io
import json
import logging
import re

from .crypto_tokens import is_currency_available, list_networks, list_tokens
from .nowpayments_client import (
    get_crypto_min_amount,
    humanize_crypto_error,
    nowpayments_request,
)
from .database import get_all_settings, get_db, now_iso, rows_to_list

logger = logging.getLogger(__name__)

BOOKING_STATUSES = (
    "pending",
    "payment_pending",
    "payment_submitted",
    "confirmed",
    "completed",
    "cancelled",
    "no_show",
    "suspended",
)

ACTIVE_CRYPTO_STATUSES = {"waiting", "confirming", "partially_paid", "sending"}
PROCESSING_CRYPTO_STATUSES = {"confirming", "partially_paid", "sending"}


def _notify_safe(label: str, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:
        logger.warning("%s notification failed: %s", label, exc)


def _notify_crypto_payment_created(booking: dict, payment: dict):
    from .email_service import send_crypto_payment_created_admin, send_crypto_payment_created_customer
    from .telegram_service import notify_crypto_payment_created

    _notify_safe("customer crypto created email", send_crypto_payment_created_customer, booking, payment)
    _notify_safe("admin crypto created email", send_crypto_payment_created_admin, booking, payment)
    _notify_safe("admin crypto created telegram", notify_crypto_payment_created, booking["booking_id"], payment)


def _notify_crypto_payment_processing(booking: dict, payment: dict, status: str):
    from .email_service import send_crypto_payment_processing_admin, send_crypto_payment_processing_customer
    from .telegram_service import notify_crypto_payment_processing

    _notify_safe("customer crypto processing email", send_crypto_payment_processing_customer, booking, payment, status)
    _notify_safe("admin crypto processing email", send_crypto_payment_processing_admin, booking, payment, status)
    _notify_safe("admin crypto processing telegram", notify_crypto_payment_processing, booking["booking_id"], payment, status)


def _should_notify_crypto_processing(old_status: str, new_status: str) -> bool:
    old_status = (old_status or "").lower()
    new_status = (new_status or "").lower()
    return old_status == "waiting" and new_status in PROCESSING_CRYPTO_STATUSES


def np_fee_pct() -> float:
    try:
        return float(get_all_settings().get("np_fee_percentage", "0") or 0)
    except (TypeError, ValueError):
        return 0.0


def total_with_fee(amount: float) -> float:
    fee = np_fee_pct()
    if fee <= 0:
        return round(amount, 2)
    return round(amount * (1 + fee / 100), 2)


def get_active_payment_methods() -> list[dict]:
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT * FROM payment_methods WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())


def get_all_payment_methods() -> list[dict]:
    with get_db() as conn:
        return rows_to_list(conn.execute(
            "SELECT * FROM payment_methods ORDER BY sort_order, id"
        ).fetchall())


def resolve_payment_amount(booking: dict, amount: float | None = None) -> float:
    if amount is not None:
        try:
            parsed = float(amount)
            if parsed > 0:
                return round(parsed, 2)
        except (TypeError, ValueError):
            pass
    return booking_amount_due(booking)


def amount_label(amount: float) -> str:
    if amount <= 0:
        return "Contact us for pricing"
    if float(amount).is_integer():
        return f"${int(amount):,}"
    return f"${amount:,.2f}"


def booking_amount_due(booking: dict) -> float:
    price = booking.get("pricing_price")
    if price is not None and price != "":
        try:
            return float(price)
        except (TypeError, ValueError):
            pass
    return 0.0


def booking_amount_due(booking: dict) -> float:
    price = booking.get("pricing_price")
    if price is not None and price != "":
        try:
            return float(price)
        except (TypeError, ValueError):
            pass
    return 0.0


def _load_message_meta(row) -> dict:
    try:
        return json.loads(row["meta_json"] or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def parse_payment_request_message_id(note: str) -> int | None:
    match = re.search(r"\[payment_request:(\d+)\]", note or "")
    return int(match.group(1)) if match else None


def get_payment_request_messages(booking_id: str) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(
            """SELECT * FROM booking_messages
               WHERE booking_id = ? AND message_type = 'payment_request'
               ORDER BY created_at""",
            (booking_id,),
        ).fetchall()
    out = []
    for row in rows:
        msg = dict(row)
        msg["meta"] = _load_message_meta(row)
        out.append(msg)
    return out


def get_open_payment_requests(booking_id: str) -> list[dict]:
    return [
        m for m in get_payment_request_messages(booking_id)
        if m.get("meta", {}).get("pay_status", "open") in ("open", "pending")
    ]


def has_open_payment_requests(booking_id: str) -> bool:
    return bool(get_open_payment_requests(booking_id))


def is_payment_request_open(booking_id: str, message_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """SELECT meta_json FROM booking_messages
               WHERE id = ? AND booking_id = ? AND message_type = 'payment_request'""",
            (message_id, booking_id),
        ).fetchone()
    if not row:
        return False
    meta = _load_message_meta(row)
    return meta.get("pay_status", "open") in ("open", "pending")


def booking_allows_payment(booking: dict, message_id: int | None = None) -> bool:
    booking_id = booking["booking_id"]
    if booking.get("status") == "payment_pending":
        return True
    if message_id and is_payment_request_open(booking_id, message_id):
        return True
    return has_open_payment_requests(booking_id)


def set_payment_request_status(
    booking_id: str,
    pay_status: str,
    *,
    message_id: int | None = None,
    amount: float | None = None,
    submission_id: int | None = None,
    payment_id: int | None = None,
) -> bool:
    with get_db() as conn:
        if message_id:
            rows = conn.execute(
                """SELECT * FROM booking_messages
                   WHERE id = ? AND booking_id = ? AND message_type = 'payment_request'""",
                (message_id, booking_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM booking_messages
                   WHERE booking_id = ? AND message_type = 'payment_request'
                   ORDER BY created_at""",
                (booking_id,),
            ).fetchall()

    updated = False
    for row in rows:
        msg = dict(row)
        meta = _load_message_meta(row)
        if meta.get("pay_status") == "confirmed":
            continue
        if message_id and msg["id"] != message_id:
            continue
        if amount is not None and message_id is None:
            try:
                meta_amt = float(meta.get("amount") or 0)
                if abs(meta_amt - float(amount)) >= 0.01:
                    continue
            except (TypeError, ValueError):
                continue
        meta["pay_status"] = pay_status
        if submission_id:
            meta["submission_id"] = submission_id
        if payment_id:
            meta["payment_id"] = payment_id
        if pay_status == "confirmed":
            meta["confirmed_at"] = now_iso()
        with get_db() as conn:
            conn.execute(
                "UPDATE booking_messages SET meta_json = ? WHERE id = ?",
                (json.dumps(meta), msg["id"]),
            )
        updated = True
        if message_id:
            break
    return updated


def _payment_record(row) -> dict | None:
    return dict(row) if row else None


def get_active_crypto_payment(booking_id: str, message_id: int | None = None) -> dict | None:
    with get_db() as conn:
        if message_id:
            row = conn.execute(
                """SELECT * FROM booking_payments
                   WHERE booking_id = ? AND provider = 'nowpayments'
                     AND request_message_id = ?
                   ORDER BY created_at DESC LIMIT 1""",
                (booking_id, message_id),
            ).fetchone()
            if row:
                payment = dict(row)
                if payment.get("status") not in ("finished", "confirmed", "failed", "expired"):
                    return payment
        row = conn.execute(
            """SELECT * FROM booking_payments
               WHERE booking_id = ? AND provider = 'nowpayments'
               ORDER BY created_at DESC LIMIT 1""",
            (booking_id,),
        ).fetchone()
    if not row:
        return None
    payment = dict(row)
    if payment.get("status") in ("finished", "confirmed", "failed", "expired"):
        return None
    return payment


def get_all_active_crypto_payments(booking_id: str) -> list[dict]:
    placeholders = ",".join("?" for _ in ACTIVE_CRYPTO_STATUSES)
    with get_db() as conn:
        rows = conn.execute(
            f"""SELECT * FROM booking_payments
                WHERE booking_id = ? AND provider = 'nowpayments'
                  AND status IN ({placeholders})
                ORDER BY created_at DESC""",
            (booking_id, *ACTIVE_CRYPTO_STATUSES),
        ).fetchall()
    return [dict(r) for r in rows]


def _match_crypto_payment_to_request(msg: dict, payments: list[dict]) -> dict | None:
    meta = msg.get("meta") or {}
    msg_id = msg.get("id")
    meta_payment_id = meta.get("payment_id")

    if meta_payment_id:
        for payment in payments:
            if int(payment.get("id") or 0) == int(meta_payment_id):
                return payment

    if msg_id:
        for payment in payments:
            req_id = payment.get("request_message_id")
            if req_id and int(req_id) == int(msg_id):
                return payment

    try:
        meta_amount = float(meta.get("amount") or 0)
    except (TypeError, ValueError):
        meta_amount = 0
    if meta_amount > 0:
        for payment in payments:
            try:
                if abs(float(payment.get("amount") or 0) - meta_amount) < 0.01:
                    return payment
            except (TypeError, ValueError):
                continue
    return None


def get_booking_payment_info(booking: dict) -> dict:
    amount = booking_amount_due(booking)
    methods = get_active_payment_methods()
    settings = get_all_settings()
    crypto_enabled = (
        settings.get("payment_crypto_enabled", "1") == "1"
        and bool(settings.get("nowpayments_api_key", "").strip())
    )
    active_payment = get_active_crypto_payment(booking["booking_id"])
    fee = np_fee_pct()
    total = total_with_fee(amount) if amount else 0
    return {
        "amount_due": amount,
        "amount_label": amount_label(amount),
        "fee_percent": fee,
        "total_with_fee": total,
        "total_label": f"${total:,.2f}" if total else "",
        "methods": methods,
        "crypto_enabled": crypto_enabled,
        "crypto_tokens": list_tokens() if crypto_enabled else [],
        "active_crypto_payment": active_payment,
        "payment_pending": booking.get("status") == "payment_pending",
        "has_open_payments": bool(get_open_payment_requests(booking["booking_id"]))
            or booking.get("status") == "payment_pending",
        "open_payment_count": len(get_open_payment_requests(booking["booking_id"])),
    }


def generate_qr_data_url(text: str) -> str:
    if not text:
        return ""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=8, border=3)
        qr.add_data(text)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/png;base64,{encoded}"
    except Exception as exc:
        logger.warning("QR generation failed: %s", exc)
        return ""


def payment_is_verified(data: dict) -> bool:
    try:
        paid_crypto = float(data.get("actually_paid") or 0)
        required_crypto = float(data.get("pay_amount") or 0)
        outcome_amt = float(data.get("outcome_amount") or 0)
        price_amt = float(data.get("price_amount") or 0)
        if required_crypto > 0 and paid_crypto >= required_crypto:
            return True
        if price_amt > 0 and outcome_amt >= price_amt * 0.99:
            return True
    except (TypeError, ValueError):
        pass
    return False


def serialize_payment_response(record: dict, api_data: dict | None = None) -> dict:
    api_data = api_data or {}
    pay_address = api_data.get("pay_address") or record.get("pay_address") or ""
    pay_amount = api_data.get("pay_amount") or record.get("pay_amount") or ""
    pay_currency = (api_data.get("pay_currency") or record.get("pay_currency") or "").upper()
    payment_url = record.get("payment_url") or api_data.get("invoice_url") or ""
    qr_source = pay_address or payment_url
    status = api_data.get("payment_status") or record.get("status") or "waiting"
    expires = api_data.get("expiration_estimate_date") or record.get("expires_at") or ""
    return {
        **record,
        "status": status,
        "pay_address": pay_address,
        "pay_amount": str(pay_amount),
        "pay_currency": pay_currency,
        "payment_url": payment_url,
        "expires_at": expires[:16] if expires else "",
        "qr_code": generate_qr_data_url(qr_source),
        "actually_paid": api_data.get("actually_paid"),
        "outcome_amount": api_data.get("outcome_amount"),
        "verified": payment_is_verified(api_data) if api_data else False,
    }


def create_crypto_payment(
    booking: dict,
    pay_currency: str = "usdttrc20",
    amount: float | None = None,
    message_id: int | None = None,
) -> tuple[dict | None, str]:
    settings = get_all_settings()
    api_key = settings.get("nowpayments_api_key", "").strip()
    if not api_key:
        return None, "Crypto payments are not configured yet."

    pay_currency = (pay_currency or "usdttrc20").strip().lower()
    if not is_currency_available(pay_currency):
        return None, (
            f"{pay_currency.upper()} is not enabled on your NowPayments account. "
            "Please choose another network or payment method."
        )

    pay_amount = resolve_payment_amount(booking, amount)
    if pay_amount <= 0:
        return None, "No payment amount is set for this booking. Add a pricing tier or contact us."

    existing = get_active_crypto_payment(booking["booking_id"], message_id)
    if existing:
        existing_amt = float(existing.get("amount") or 0)
        if abs(existing_amt - pay_amount) < 0.01:
            data, status = nowpayments_request("GET", f"/payment/{existing['external_id']}")
            if status == 200 and data.get("payment_status") in ACTIVE_CRYPTO_STATUSES:
                return serialize_payment_response(existing, data), ""

    total = total_with_fee(pay_amount)
    min_amount = get_crypto_min_amount(pay_currency)
    if min_amount and total < min_amount:
        return None, (
            f"Minimum for {pay_currency.upper()} is ${min_amount:,.2f}. "
            f"Your total is ${total:,.2f}. Try another method or increase the payment amount."
        )

    order_id = f"{booking['booking_id']}:{now_iso()}"
    payload = {
        "price_amount": round(total, 2),
        "price_currency": "usd",
        "pay_currency": pay_currency,
        "order_id": order_id,
        "order_description": f"Session payment {booking['booking_id']}",
    }
    base_url = (settings.get("site_base_url") or "").strip().rstrip("/")
    if base_url:
        payload["ipn_callback_url"] = f"{base_url}/api/nowpayments/webhook"

    data, status = nowpayments_request("POST", "/payment", payload)
    payment_id = data.get("payment_id")
    if not payment_id:
        raw_msg = data.get("message") or data.get("status") or ""
        return None, humanize_crypto_error(raw_msg, pay_currency, total, status)

    ts = now_iso()
    payment_url = data.get("invoice_url") or f"https://nowpayments.io/payment/?iid={payment_id}"
    expires = data.get("expiration_estimate_date") or ""
    record = {
        "booking_id": booking["booking_id"],
        "provider": "nowpayments",
        "external_id": str(payment_id),
        "amount": pay_amount,
        "currency": "USD",
        "pay_currency": data.get("pay_currency") or pay_currency,
        "pay_address": data.get("pay_address") or "",
        "pay_amount": str(data.get("pay_amount") or ""),
        "payment_url": payment_url,
        "status": data.get("payment_status") or "waiting",
        "expires_at": expires,
        "created_at": ts,
        "updated_at": ts,
    }
    with get_db() as conn:
        conn.execute(
            """INSERT INTO booking_payments
               (booking_id, provider, external_id, amount, currency, pay_currency,
                pay_address, pay_amount, payment_url, status, expires_at, created_at, updated_at,
                request_message_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["booking_id"], record["provider"], record["external_id"],
                record["amount"], record["currency"], record["pay_currency"],
                record["pay_address"], record["pay_amount"], record["payment_url"],
                record["status"], record["expires_at"], record["created_at"], record["updated_at"],
                message_id,
            ),
        )
        record["id"] = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    if message_id:
        set_payment_request_status(
            booking["booking_id"], "pending", message_id=message_id, payment_id=record["id"]
        )
    elif booking.get("status") == "payment_pending":
        set_payment_request_status(
            booking["booking_id"], "pending", amount=pay_amount, payment_id=record["id"]
        )

    _notify_crypto_payment_created(booking, record)
    return serialize_payment_response(record, data), ""


def complete_crypto_payment(booking_id: str, payment_id: str = "", source: str = "auto") -> bool:
    with get_db() as conn:
        booking_row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not booking_row:
            return False
        booking = dict(booking_row)

    if payment_id:
        with get_db() as conn:
            pay_row = conn.execute(
                "SELECT * FROM booking_payments WHERE external_id = ? AND booking_id = ?",
                (payment_id, booking_id),
            ).fetchone()
    else:
        pay_row = None
        with get_db() as conn:
            pay_row = conn.execute(
                """SELECT * FROM booking_payments
                   WHERE booking_id = ? AND provider = 'nowpayments'
                   ORDER BY created_at DESC LIMIT 1""",
                (booking_id,),
            ).fetchone()

    if not pay_row:
        return False

    payment = dict(pay_row)
    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            "UPDATE booking_payments SET status='finished', updated_at=? WHERE id=?",
            (ts, payment["id"]),
        )

    from .booking_service import add_booking_message, update_booking_status

    currency = (payment.get("pay_currency") or "crypto").upper()
    amount = payment.get("amount") or booking_amount_due(booking)
    req_msg_id = payment.get("request_message_id")
    if req_msg_id:
        set_payment_request_status(booking_id, "confirmed", message_id=int(req_msg_id))
    else:
        set_payment_request_status(booking_id, "confirmed", amount=float(amount))

    if booking.get("status") == "payment_pending":
        update_booking_status(booking_id, "payment_submitted")
    add_booking_message(
        booking_id,
        "system",
        f"Crypto payment confirmed ({currency}). Thank you — we're reviewing your payment.",
        "System",
    )

    try:
        from .email_service import send_payment_confirmed_admin, send_payment_confirmed_customer
        send_payment_confirmed_customer(booking, amount, f"Crypto ({currency})")
        send_payment_confirmed_admin(booking, amount, f"Crypto ({currency})", source=source)
    except Exception as exc:
        logger.warning("Payment confirmed email failed: %s", exc)

    try:
        from .telegram_service import notify_payment_confirmed
        notify_payment_confirmed(booking_id, f"Crypto ({currency})", amount, source)
    except Exception as exc:
        logger.warning("Payment confirmed telegram failed: %s", exc)
    return True


def build_payment_ui_state(booking: dict, active_payment: dict | None = None) -> dict:
    """Snapshot for track page / chat payment card auto-updates."""
    booking_id = booking["booking_id"]
    active_rows = get_all_active_crypto_payments(booking_id)
    serialized_by_id: dict[int, dict] = {}
    for row in active_rows:
        serialized_by_id[int(row["id"])] = serialize_payment_response(row)

    if active_payment and active_payment.get("id"):
        serialized_by_id[int(active_payment["id"])] = active_payment
    elif active_payment and active_payment.get("external_id"):
        for row in active_rows:
            if str(row.get("external_id")) == str(active_payment.get("external_id")):
                serialized_by_id[int(row["id"])] = active_payment
                break

    latest_active = active_payment
    if not latest_active and serialized_by_id:
        latest_active = next(iter(serialized_by_id.values()))

    payment_requests = []
    for msg in get_payment_request_messages(booking_id):
        meta = msg.get("meta") or {}
        pay_status = meta.get("pay_status", "open")
        if pay_status == "confirmed":
            continue
        matched = _match_crypto_payment_to_request(msg, active_rows)
        entry = {
            "message_id": msg["id"],
            "body": msg["body"],
            "pay_status": pay_status,
            "amount": meta.get("amount"),
            "amount_label": meta.get("amount_label"),
        }
        if matched:
            entry["active_payment"] = serialized_by_id.get(int(matched["id"]), serialize_payment_response(matched))
            if pay_status == "open":
                entry["pay_status"] = "pending"
        payment_requests.append(entry)

    info = get_booking_payment_info(booking)
    return {
        "booking_status": booking.get("status"),
        "active_crypto_payment": latest_active,
        "active_crypto_payments": list(serialized_by_id.values()),
        "payment_requests": payment_requests,
        "amount_due": info["amount_due"],
        "amount_label": info["amount_label"],
        "has_open_payments": info["has_open_payments"],
    }


def refresh_crypto_payment_status(booking_id: str, payment_id: int | None = None) -> dict:
    if payment_id:
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM booking_payments WHERE id = ? AND booking_id = ?",
                (payment_id, booking_id),
            ).fetchone()
        payments = [dict(row)] if row else []
    else:
        payments = get_all_active_crypto_payments(booking_id)
        if not payments:
            with get_db() as conn:
                row = conn.execute(
                    """SELECT * FROM booking_payments
                       WHERE booking_id = ? AND provider = 'nowpayments'
                       ORDER BY created_at DESC LIMIT 1""",
                    (booking_id,),
                ).fetchone()
            if row:
                payments = [dict(row)]

    if not payments:
        with get_db() as conn:
            booking_row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        booking = dict(booking_row) if booking_row else None
        ui_state = build_payment_ui_state(booking) if booking else {}
        return {"payment": None, "completed": False, **ui_state}

    completed = False
    latest_payload = None
    booking = None

    for payment in payments:
        if payment.get("status") in ("finished", "confirmed", "failed", "expired"):
            continue
        old_status = (payment.get("status") or "waiting").lower()
        data, status = nowpayments_request("GET", f"/payment/{payment['external_id']}")
        if status != 200 or not data:
            latest_payload = serialize_payment_response(payment)
            continue

        new_status = (data.get("payment_status") or payment["status"] or "waiting").lower()
        ts = now_iso()
        with get_db() as conn:
            conn.execute(
                "UPDATE booking_payments SET status=?, updated_at=?, pay_address=?, pay_amount=? WHERE id=?",
                (
                    new_status,
                    ts,
                    data.get("pay_address") or payment.get("pay_address") or "",
                    str(data.get("pay_amount") or payment.get("pay_amount") or ""),
                    payment["id"],
                ),
            )

        if not booking:
            with get_db() as conn:
                booking_row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
            booking = dict(booking_row) if booking_row else None

        if booking and _should_notify_crypto_processing(old_status, new_status):
            payment.update({
                "status": new_status,
                "pay_address": data.get("pay_address") or payment.get("pay_address") or "",
                "pay_amount": str(data.get("pay_amount") or payment.get("pay_amount") or ""),
            })
            _notify_crypto_payment_processing(booking, payment, new_status)

        if new_status in ("finished", "confirmed") or payment_is_verified(data):
            if complete_crypto_payment(booking_id, payment["external_id"], source="status check"):
                completed = True

        latest_payload = serialize_payment_response(payment, data)

    if not booking:
        with get_db() as conn:
            booking_row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        booking = dict(booking_row) if booking_row else None

    booking_status = booking.get("status", "") if booking else ""
    ui_state = build_payment_ui_state(booking, latest_payload) if booking else {}
    return {
        "payment": latest_payload,
        "completed": completed,
        "booking_status": booking_status,
        **ui_state,
    }


def verify_nowpayments_webhook(raw_body: bytes, signature: str) -> bool:
    secret = get_all_settings().get("nowpayments_ipn_secret", "").strip()
    if not secret or not signature:
        return False
    digest = hmac.new(secret.encode(), raw_body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(digest, signature)


def handle_nowpayments_webhook(payload: dict) -> bool:
    payment_id = str(payload.get("payment_id") or "")
    order_id = str(payload.get("order_id") or "")
    status = payload.get("payment_status") or ""
    if not payment_id:
        return False

    booking_id = order_id.split(":", 1)[0] if order_id else ""
    if not booking_id:
        with get_db() as conn:
            row = conn.execute(
                "SELECT booking_id FROM booking_payments WHERE external_id = ?",
                (payment_id,),
            ).fetchone()
            if row:
                booking_id = row["booking_id"]

    old_status = "waiting"
    with get_db() as conn:
        pay_row = conn.execute(
            "SELECT * FROM booking_payments WHERE external_id = ?",
            (payment_id,),
        ).fetchone()
        if pay_row:
            old_status = (pay_row["status"] or "waiting").lower()

    new_status = (status or "waiting").lower()
    ts = now_iso()
    with get_db() as conn:
        conn.execute(
            """UPDATE booking_payments SET status=?, updated_at=?
               WHERE external_id = ?""",
            (new_status, ts, payment_id),
        )

    if booking_id and _should_notify_crypto_processing(old_status, new_status):
        with get_db() as conn:
            booking_row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
            pay_row = conn.execute(
                "SELECT * FROM booking_payments WHERE external_id = ?",
                (payment_id,),
            ).fetchone()
        if booking_row and pay_row:
            payment = dict(pay_row)
            payment["status"] = new_status
            _notify_crypto_payment_processing(dict(booking_row), payment, new_status)

    if booking_id and (new_status in ("finished", "confirmed") or payment_is_verified(payload)):
        return complete_crypto_payment(booking_id, payment_id, source="webhook")
    return bool(booking_id)


def mark_payment_submitted(
    booking_id: str,
    method_name: str = "",
    note: str = "",
    method_id: int | None = None,
    proof_path: str = "",
    amount: float | None = None,
    message_id: int | None = None,
) -> dict | None:
    if not proof_path:
        return None
    return submit_manual_payment_with_proof(
        booking_id,
        method_name=method_name,
        method_id=method_id,
        note=note,
        proof_path=proof_path,
        amount=amount,
        message_id=message_id,
    )


def add_payment_request_message(booking_id: str, amount: float | None = None, note: str = "") -> dict | None:
    from .booking_service import add_booking_message

    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        booking = dict(row)
        if booking.get("pricing_id"):
            pr = conn.execute("SELECT price FROM pricing_tiers WHERE id=?", (booking["pricing_id"],)).fetchone()
            if pr:
                booking["pricing_price"] = pr["price"]

    amt = amount if amount is not None else booking_amount_due(booking)
    label = amount_label(amt)
    body = f"Payment of {label} is required to confirm your session."
    if note:
        body += f" {note}"
    body += " Tap Pay now below when ready."
    meta = {
        "amount": amt,
        "amount_label": label,
        "note": note,
        "pay_action": True,
        "pay_status": "open",
    }
    return add_booking_message(
        booking_id,
        "system",
        body,
        "System",
        message_type="payment_request",
        meta=meta,
    )


def request_followup_payment(booking_id: str, amount: float | None = None, note: str = "") -> dict | None:
    from .booking_service import update_booking_status

    with get_db() as conn:
        row = conn.execute("SELECT status FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        status = row["status"]

    if status in ("pending", "payment_submitted"):
        update_booking_status(booking_id, "payment_pending", note=note or "Payment requested")

    add_payment_request_message(booking_id, amount=amount, note=note or "Payment requested")
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    return dict(row) if row else None


def get_pending_payment_submissions(booking_id: str | None = None) -> list[dict]:
    with get_db() as conn:
        if booking_id:
            rows = conn.execute(
                """SELECT * FROM payment_submissions
                   WHERE booking_id = ? AND status = 'pending' ORDER BY created_at DESC""",
                (booking_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM payment_submissions WHERE status = 'pending' ORDER BY created_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]


def submit_manual_payment_with_proof(
    booking_id: str,
    method_name: str = "",
    method_id: int | None = None,
    note: str = "",
    proof_path: str = "",
    amount: float | None = None,
    message_id: int | None = None,
) -> dict | None:
    from .booking_service import add_booking_message, update_booking_status

    if not proof_path:
        return None

    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            return None
        booking = dict(row)
        if booking.get("pricing_id"):
            pr = conn.execute("SELECT price FROM pricing_tiers WHERE id=?", (booking["pricing_id"],)).fetchone()
            if pr:
                booking["pricing_price"] = pr["price"]

    pay_amount = resolve_payment_amount(booking, amount)
    label = method_name or "selected method"
    if message_id:
        note = f"{note} [payment_request:{message_id}]".strip()
    ts = now_iso()

    with get_db() as conn:
        cur = conn.execute(
            """INSERT INTO payment_submissions
               (booking_id, method_id, method_name, amount, note, proof_path, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (booking_id, method_id, label, pay_amount, note, proof_path, ts),
        )
        submission_id = cur.lastrowid

    if message_id:
        set_payment_request_status(
            booking_id, "submitted", message_id=message_id, submission_id=submission_id
        )
    else:
        set_payment_request_status(
            booking_id, "submitted", amount=pay_amount, submission_id=submission_id
        )

    if booking.get("status") == "payment_pending":
        update_booking_status(booking_id, "payment_submitted")
    add_booking_message(
        booking_id,
        "customer",
        f"Payment proof submitted via {label}. Pending confirmation.",
        booking.get("name", "Customer"),
        message_type="payment_proof",
        attachment_path=proof_path,
        meta={"method_name": label, "submission_id": submission_id, "amount": pay_amount},
    )
    add_booking_message(
        booking_id,
        "system",
        "Your payment is pending review. We'll confirm once verified. If you paid using a different method, select it above or choose another option.",
        "System",
        message_type="payment_status",
    )

    try:
        from .email_service import send_payment_pending_customer, send_admin_payment_proof
        send_payment_pending_customer(booking, pay_amount, label)
        send_admin_payment_proof(booking, submission_id, label, note, proof_path)
    except Exception:
        pass

    try:
        from .telegram_service import notify_payment_proof_submitted
        notify_payment_proof_submitted(booking_id, submission_id, label, note, proof_path)
    except Exception:
        pass

    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
    return dict(row) if row else None


def review_payment_submission(submission_id: int, approve: bool, review_note: str = "") -> dict | None:
    from .booking_service import add_booking_message, update_booking_status

    with get_db() as conn:
        row = conn.execute("SELECT * FROM payment_submissions WHERE id = ?", (submission_id,)).fetchone()
        if not row or row["status"] != "pending":
            return None
        submission = dict(row)
        booking_id = submission["booking_id"]
        ts = now_iso()
        status = "approved" if approve else "rejected"
        conn.execute(
            """UPDATE payment_submissions
               SET status=?, review_note=?, reviewed_at=? WHERE id=?""",
            (status, review_note, ts, submission_id),
        )
        brow = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not brow:
            return None
        booking = dict(brow)

    if approve:
        req_msg_id = parse_payment_request_message_id(submission.get("note", ""))
        if req_msg_id:
            set_payment_request_status(
                booking_id, "confirmed", message_id=req_msg_id, submission_id=submission_id
            )
        else:
            set_payment_request_status(
                booking_id,
                "confirmed",
                amount=float(submission.get("amount") or 0),
                submission_id=submission_id,
            )
        if booking.get("status") in ("payment_pending", "payment_submitted"):
            update_booking_status(booking_id, "confirmed", note=review_note or "Payment approved")
        add_booking_message(
            booking_id,
            "system",
            f"Payment approved. Your session is confirmed!",
            "System",
            message_type="payment_status",
        )
        try:
            from .email_service import send_payment_approved_customer, send_payment_approved_admin
            send_payment_approved_customer(booking, submission["amount"], submission["method_name"])
            send_payment_approved_admin(booking, submission["amount"], submission["method_name"])
        except Exception as exc:
            logger.warning("Payment approved email failed: %s", exc)
        try:
            from .telegram_service import notify_payment_approved
            notify_payment_approved(booking_id, submission["method_name"], submission["amount"])
        except Exception as exc:
            logger.warning("Payment approved telegram failed: %s", exc)
    else:
        req_msg_id = parse_payment_request_message_id(submission.get("note", ""))
        if req_msg_id:
            set_payment_request_status(booking_id, "open", message_id=req_msg_id)
        else:
            set_payment_request_status(booking_id, "open", amount=float(submission.get("amount") or 0))
        if booking.get("status") == "payment_submitted":
            update_booking_status(booking_id, "payment_pending", note=review_note or "Payment not verified")
        add_booking_message(
            booking_id,
            "system",
            f"Payment could not be verified. {review_note or 'Please try again or select another payment method.'}",
            "System",
            message_type="payment_status",
        )
        try:
            from .email_service import send_payment_rejected_customer
            send_payment_rejected_customer(booking, submission["method_name"], review_note)
        except Exception:
            pass

    with get_db() as conn:
        row = conn.execute("SELECT * FROM payment_submissions WHERE id = ?", (submission_id,)).fetchone()
    return dict(row) if row else None

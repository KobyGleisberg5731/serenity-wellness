"""Telegram bot — outbound notifications + long-polling for button presses (no webhook)."""
import json
import re
import urllib.request

from .booking_service import add_booking_message, update_booking_status
from .database import get_all_settings

_BOOKING_ID_RE = re.compile(r"(BK-\d{4})", re.I)


def _settings() -> dict:
    return get_all_settings()


def is_enabled() -> bool:
    s = _settings()
    return s.get("telegram_notifications_enabled", "0") == "1" and bool(s.get("telegram_bot_token", "").strip())


def _api(method: str, payload: dict | None = None, timeout: int = 15) -> dict:
    token = _settings().get("telegram_bot_token", "").strip()
    if not token:
        return {}
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload or {}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return {}


def clear_webhook() -> bool:
    """Remove webhook so getUpdates polling works."""
    return bool(_api("deleteWebhook", {"drop_pending_updates": False}).get("ok"))


def send_message(
    chat_id: str,
    text: str,
    reply_markup: dict | None = None,
    *,
    force_reply: bool = False,
) -> bool:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if force_reply:
        payload["reply_markup"] = {
            "force_reply": True,
            "input_field_placeholder": "Type your reply…",
        }
    elif reply_markup:
        payload["reply_markup"] = reply_markup
    result = _api("sendMessage", payload)
    return bool(result.get("ok"))


def _status_keyboard(booking_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Payment due", "callback_data": f"bk:{booking_id}:payment_pending"},
                {"text": "Confirm", "callback_data": f"bk:{booking_id}:confirmed"},
            ],
            [
                {"text": "Pending", "callback_data": f"bk:{booking_id}:pending"},
                {"text": "Complete", "callback_data": f"bk:{booking_id}:completed"},
            ],
            [
                {"text": "Cancel", "callback_data": f"bk:{booking_id}:cancelled"},
                {"text": "No Show", "callback_data": f"bk:{booking_id}:no_show"},
            ],
        ]
    }


def _message_keyboard(booking_id: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "↩ Reply to customer", "callback_data": f"reply:{booking_id}"},
            ],
            [
                {"text": "Payment due", "callback_data": f"bk:{booking_id}:payment_pending"},
                {"text": "Confirm", "callback_data": f"bk:{booking_id}:confirmed"},
            ],
            [
                {"text": "Pending", "callback_data": f"bk:{booking_id}:pending"},
                {"text": "Complete", "callback_data": f"bk:{booking_id}:completed"},
            ],
        ]
    }


def _extract_booking_id(text: str) -> str | None:
    match = _BOOKING_ID_RE.search(text or "")
    return match.group(1).upper() if match else None


def notify_new_booking(booking: dict):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return

    business = _settings().get("business_name", "Serenity Wellness")
    service = booking.get("service_name") or "Not specified"
    pricing = booking.get("pricing_label") or "Not specified"
    price = booking.get("pricing_price")
    price_line = f"\nPrice: <b>${int(price)}</b>" if price else ""

    text = (
        f"<b>New booking — {business}</b>\n\n"
        f"ID: <b>{booking['booking_id']}</b>\n"
        f"Name: {booking['name']}\n"
        f"Email: {booking['email']}\n"
        f"Phone: {booking.get('phone') or '—'}\n"
        f"Treatment: {service}\n"
        f"Session: {pricing}{price_line}\n"
        f"Therapist: {booking.get('masseuse_name') or 'No preference'}\n"
        f"When: {booking['preferred_datetime']}\n"
        f"Note: {booking.get('message') or '—'}\n\n"
        f"Tap a button to update status."
    )
    send_message(chat_id, text, _status_keyboard(booking["booking_id"]))


def notify_new_message(booking_id: str, message: dict, booking: dict | None = None):
    if not is_enabled() or message.get("sender_type") != "customer":
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return

    customer = message.get("sender_name") or (booking or {}).get("name") or "Customer"
    body = message.get("body", "")
    text = (
        f"<b>Session message — {booking_id}</b>\n"
        f"From: {customer}\n\n"
        f"{body}\n\n"
        f"<i>Tap Reply below, reply to this message, or send:</i>\n"
        f"<code>{booking_id}: your reply</code>"
    )
    send_message(chat_id, text, _message_keyboard(booking_id))


def notify_payment_submitted(booking_id: str, method_name: str = "", note: str = ""):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    text = (
        f"<b>Payment submitted — {booking_id}</b>\n"
        f"Method: {method_name or 'Not specified'}\n"
    )
    if note:
        text += f"Note: {note}\n"
    text += "\nReview and confirm the booking when ready."
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_crypto_payment_created(booking_id: str, payment: dict):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    currency = (payment.get("pay_currency") or "").upper()
    pay_amount = payment.get("pay_amount") or ""
    amount = payment.get("amount") or 0
    text = (
        f"<b>Crypto payment created — {booking_id}</b>\n"
        f"Session amount: <b>${float(amount):,.2f}</b>\n"
        f"Send: <b>{pay_amount} {currency}</b>\n"
        f"Status: Waiting for payment"
    )
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_crypto_payment_processing(booking_id: str, payment: dict, status: str = ""):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    currency = (payment.get("pay_currency") or "").upper()
    amount = payment.get("amount") or 0
    status_label = (status or payment.get("status") or "processing").replace("_", " ").title()
    text = (
        f"<b>Crypto payment detected — {booking_id}</b>\n"
        f"Amount: <b>${float(amount):,.2f}</b>\n"
        f"Currency: {currency}\n"
        f"Status: <b>{status_label}</b>"
    )
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_payment_confirmed(booking_id: str, method_name: str = "", amount: float = 0, source: str = ""):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    text = (
        f"<b>Payment confirmed — {booking_id}</b>\n"
        f"Method: {method_name or 'Not specified'}\n"
    )
    if amount:
        text += f"Amount: <b>${float(amount):,.2f}</b>\n"
    if source:
        text += f"Source: {source}\n"
    text += "\nBooking is ready for final confirmation."
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_payment_approved(booking_id: str, method_name: str = "", amount: float = 0):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    text = (
        f"<b>Payment approved — {booking_id}</b>\n"
        f"Method: {method_name or 'Manual payment'}\n"
    )
    if amount:
        text += f"Amount: <b>${float(amount):,.2f}</b>\n"
    text += "\nCustomer notified. Session confirmed."
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_payment_expired(booking_id: str, payment: dict | None = None):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    currency = ((payment or {}).get("pay_currency") or "").upper()
    amount = (payment or {}).get("amount") or 0
    text = (
        f"<b>Crypto payment expired — {booking_id}</b>\n"
        f"Amount: <b>${float(amount):,.2f}</b>\n"
    )
    if currency:
        text += f"Currency: {currency}\n"
    text += "\nCustomer was emailed. They can start a new payment from their session page."
    send_message(chat_id, text, _status_keyboard(booking_id))


def notify_payment_proof_submitted(
    booking_id: str,
    submission_id: int,
    method_name: str = "",
    note: str = "",
    proof_path: str = "",
):
    if not is_enabled():
        return
    chat_id = _settings().get("telegram_admin_chat_id", "").strip()
    if not chat_id:
        return
    settings = _settings()
    base = (settings.get("site_base_url") or "").strip().rstrip("/")
    proof_url = f"{base}/data/{proof_path}" if base and proof_path else ""
    admin_url = f"{base}/admin/bookings/{booking_id}" if base else f"/admin/bookings/{booking_id}"
    text = (
        f"<b>Payment proof — {booking_id}</b>\n"
        f"Method: {method_name or 'Not specified'}\n"
        f"Submission: #{submission_id}\n"
    )
    if note:
        text += f"Note: {note}\n"
    if proof_url:
        text += f"\n<a href=\"{proof_url}\">View proof</a>\n"
    text += f"\nApprove or reject in admin:\n{admin_url}"
    send_message(chat_id, text, _status_keyboard(booking_id))


def _handle_reply_callback(callback: dict, booking_id: str) -> bool:
    chat_id = callback["message"]["chat"]["id"]
    _api("answerCallbackQuery", {
        "callback_query_id": callback["id"],
        "text": f"Type your reply for {booking_id}",
    })
    send_message(
        str(chat_id),
        (
            f"💬 <b>Reply to {booking_id}</b>\n\n"
            f"Type your message below — it will be sent to the customer by email and shown in their session chat."
        ),
        force_reply=True,
    )
    return True


def _handle_status_callback(callback: dict, booking_id: str, new_status: str) -> bool:
    allowed = {"pending", "payment_pending", "payment_submitted", "confirmed", "completed", "cancelled", "no_show"}
    if new_status not in allowed:
        return False

    booking = update_booking_status(booking_id, new_status, source="telegram")
    if not booking:
        _api("answerCallbackQuery", {
            "callback_query_id": callback["id"],
            "text": "Booking not found",
            "show_alert": True,
        })
        return False

    _api("answerCallbackQuery", {
        "callback_query_id": callback["id"],
        "text": f"Status → {new_status.replace('_', ' ').title()}",
    })

    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]
    keyboard = _message_keyboard(booking_id) if "Session message" in (callback["message"].get("text") or "") else _status_keyboard(booking_id)
    _api("editMessageReplyMarkup", {
        "chat_id": chat_id,
        "message_id": message_id,
        "reply_markup": keyboard,
    })
    send_message(
        str(chat_id),
        f"<b>{booking_id}</b> updated to <b>{new_status.replace('_', ' ').title()}</b>",
    )
    return True


def _handle_callback(update: dict) -> bool:
    callback = update.get("callback_query")
    if not callback:
        return False

    data = callback.get("data", "")
    if data.startswith("reply:"):
        booking_id = data.split(":", 1)[1].strip().upper()
        if not _BOOKING_ID_RE.fullmatch(booking_id):
            return False
        return _handle_reply_callback(callback, booking_id)

    if not data.startswith("bk:"):
        return False

    parts = data.split(":", 2)
    if len(parts) != 3:
        return False

    _, booking_id, new_status = parts
    return _handle_status_callback(callback, booking_id, new_status)


def _handle_admin_text(update: dict) -> bool:
    msg = update.get("message")
    if not msg or not msg.get("text"):
        return False

    chat_id = str(msg["chat"]["id"])
    admin_chat = _settings().get("telegram_admin_chat_id", "").strip()
    if not admin_chat or chat_id != str(admin_chat):
        return False

    text = msg["text"].strip()
    if text.startswith("/"):
        return False

    booking_id = None
    reply_body = text

    reply_to = msg.get("reply_to_message")
    if reply_to and reply_to.get("text"):
        booking_id = _extract_booking_id(reply_to["text"])

    if not booking_id:
        match = re.match(r"^(BK-\d{4})\s*:\s*(.+)$", text, re.I | re.S)
        if match:
            booking_id = match.group(1).upper()
            reply_body = match.group(2).strip()

    if not booking_id or not reply_body:
        return False

    result = add_booking_message(booking_id, "admin", reply_body, "Admin")
    if result:
        preview = reply_body if len(reply_body) <= 200 else reply_body[:197] + "…"
        send_message(chat_id, f"Reply sent to <b>{booking_id}</b>\n\n« {preview} »")
        return True

    send_message(chat_id, f"Booking <b>{booking_id}</b> not found.")
    return True


def handle_update(update: dict) -> bool:
    if _handle_callback(update):
        return True
    return _handle_admin_text(update)


def poll_updates(offset: int = 0) -> tuple[list[dict], int]:
    """Long-poll Telegram for updates. Returns (updates, next_offset)."""
    result = _api("getUpdates", {"offset": offset, "timeout": 25}, timeout=35)
    if not result.get("ok"):
        return [], offset
    updates = result.get("result", [])
    next_offset = offset
    for u in updates:
        next_offset = max(next_offset, u["update_id"] + 1)
    return updates, next_offset

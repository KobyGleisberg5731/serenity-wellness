"""Email sending via configurable SMTP with active theme branding."""
import smtplib
from contextlib import contextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urlencode

from flask import has_app_context, has_request_context, render_template, request

from .database import get_all_settings
from .helpers import media_url
from .themes import resolve_site_theme


def _email_button_color(hex_color: str) -> str:
    """Slightly darken brand primary for reliable button contrast in email clients."""
    color = (hex_color or "#d4849a").strip().lstrip("#")
    if len(color) != 6:
        return "#b86b82"
    try:
        r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
    except ValueError:
        return "#b86b82"
    r, g, b = max(0, int(r * 0.82)), max(0, int(g * 0.82)), max(0, int(b * 0.82))
    return f"#{r:02x}{g:02x}{b:02x}"


@contextmanager
def _app_context():
    if has_app_context():
        yield
        return
    from .app import app
    with app.app_context():
        yield


def _site_base_url() -> str:
    settings = get_all_settings()
    for key in ("site_base_url", "telegram_webhook_base_url"):
        base = (settings.get(key) or "").strip().rstrip("/")
        if base:
            return base
    if has_request_context():
        return request.host_url.rstrip("/")
    return ""


def _absolute_url(path: str) -> str:
    path = (path or "").strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if not path.startswith("/"):
        path = f"/{path}"
    base = _site_base_url()
    return f"{base}{path}" if base else path


def _track_url(booking: dict) -> str:
    params = urlencode({
        "booking_id": booking["booking_id"],
        "email": booking["email"],
    })
    return _absolute_url(f"/track?{params}")


def _admin_booking_url(booking_id: str) -> str:
    return _absolute_url(f"/admin/bookings/{booking_id}")


def _brand_context() -> dict:
    settings = get_all_settings()
    theme = resolve_site_theme(settings)
    logo = settings.get("logo_path", "")
    logo_path = media_url(logo) if logo else ""
    logo_url = _absolute_url(logo_path) if logo_path else ""
    return {
        "business_name": settings.get("business_name", "Serenity Wellness"),
        "footer_tagline": settings.get("footer_tagline", ""),
        "primary": theme["primary"],
        "secondary": theme["secondary"],
        "accent": theme["accent"],
        "text": theme["text"],
        "muted": theme["muted"],
        "font_heading": theme["font_heading"],
        "font_body": theme["font_body"],
        "logo_url": logo_url,
        "button_bg": _email_button_color(theme["primary"]),
        "button_text": "#ffffff",
        "button_outline_bg": theme["secondary"],
    }


def send_email(to_email: str, subject: str, html_body: str, text_body: str = "") -> tuple[bool, str]:
    settings = get_all_settings()
    host = settings.get("smtp_host", "").strip()
    port = int(settings.get("smtp_port", "587") or 587)
    user = settings.get("smtp_user", "").strip()
    password = settings.get("smtp_password", "").strip()
    from_name = settings.get("smtp_from_name", settings.get("business_name", "Serenity"))
    from_email = settings.get("smtp_from_email", user).strip()

    if not host or not user or not password or not from_email:
        return False, "SMTP not configured"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    if text_body:
        msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        with smtplib.SMTP(host, port, timeout=20) as server:
            if settings.get("smtp_use_tls", "1") == "1":
                server.starttls()
            server.login(user, password)
            server.sendmail(from_email, [to_email], msg.as_string())
        return True, "sent"
    except Exception as exc:
        return False, str(exc)


def send_booking_received(booking: dict):
    settings = get_all_settings()
    if settings.get("email_on_booking", "1") != "1":
        return

    ctx = {**_brand_context(), "booking": booking, "track_url": _track_url(booking)}
    html = render_template("email/booking_received.html", **ctx)
    text = (
        f"Thank you, {booking['name']}!\n\n"
        f"Booking ID: {booking['booking_id']}\n"
        f"Preferred time: {booking['preferred_datetime']}\n"
        f"Track your session: {ctx['track_url']}\n"
    )
    send_email(booking["email"], f"Booking confirmed — {booking['booking_id']}", html, text)

    admin_email = settings.get("admin_notification_email", "").strip()
    if admin_email:
        admin_html = render_template("email/admin_booking.html", **ctx)
        send_email(admin_email, f"New booking — {booking['booking_id']}", admin_html)


def _pay_url(booking: dict) -> str:
    return f"{_track_url(booking)}#pay"


def send_booking_status_update(booking: dict, status: str, note: str = ""):
    with _app_context():
        settings = get_all_settings()
        if settings.get("email_on_status_change", "1") != "1":
            return

        ctx = {
            **_brand_context(),
            "booking": booking,
            "status": status,
            "status_label": status.replace("_", " ").title(),
            "status_note": note,
            "track_url": _track_url(booking),
            "pay_url": _pay_url(booking),
            "show_pay_now": status == "payment_pending",
        }
        html = render_template("email/booking_status.html", **ctx)
        text = (
            f"Hi {booking['name']}, your booking {booking['booking_id']} is now {ctx['status_label']}.\n"
            f"Track: {ctx['track_url']}\n"
        )
        if ctx["show_pay_now"]:
            text += f"Pay now: {ctx['pay_url']}\n"
        send_email(booking["email"], f"Booking {ctx['status_label']} — {booking['booking_id']}", html, text)


def send_booking_chat_message(booking: dict, message_body: str):
    with _app_context():
        settings = get_all_settings()
        if settings.get("email_on_chat_message", "1") != "1":
            return
        ctx = {
            **_brand_context(),
            "booking": booking,
            "message_body": message_body,
            "track_url": _track_url(booking),
            "pay_url": _pay_url(booking),
            "show_pay_now": booking.get("status") == "payment_pending",
        }
        html = render_template("email/booking_message.html", **ctx)
        text = (
            f"New message on booking {booking['booking_id']}:\n\n"
            f"{message_body}\n\nReply: {ctx['track_url']}\n"
        )
        send_email(booking["email"], f"New message — {booking['booking_id']}", html, text)


def send_admin_customer_message(booking: dict, message_body: str, customer_name: str = ""):
    settings = get_all_settings()
    if settings.get("email_on_customer_message", "1") != "1":
        return
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    ctx = {
        **_brand_context(),
        "booking": booking,
        "message_body": message_body,
        "customer_name": customer_name or booking.get("name", "Customer"),
        "admin_url": admin_url,
    }
    html = render_template("email/admin_customer_message.html", **ctx)
    text = (
        f"New message on {booking['booking_id']} from {ctx['customer_name']}:\n\n"
        f"{message_body}\n\nOpen: {admin_url}\n"
    )
    send_email(admin_email, f"Customer message — {booking['booking_id']}", html, text)


def send_admin_payment_submitted(booking: dict, method_name: str = "", note: str = ""):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    ctx = {
        **_brand_context(),
        "booking": booking,
        "method_name": method_name,
        "payment_note": note,
        "admin_url": admin_url,
    }
    with _app_context():
        html = render_template("email/admin_payment_submitted.html", **ctx)
    text = (
        f"Payment submitted for {booking['booking_id']} via {method_name or 'customer'}.\n"
        f"{note}\n\nReview: {admin_url}\n"
    )
    send_email(admin_email, f"Payment submitted — {booking['booking_id']}", html, text)


def send_payment_confirmed_customer(booking: dict, amount: float, method_name: str = ""):
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "amount_label": f"${amount:,.2f}" if amount else "",
            "method_name": method_name or "your selected method",
            "track_url": _track_url(booking),
        }
        html = render_template("email/payment_confirmed.html", **ctx)
        text = (
            f"Hi {booking['name']}, we received your payment for {booking['booking_id']}.\n"
            f"Amount: {ctx['amount_label']}\nMethod: {ctx['method_name']}\n"
            f"Track your session: {ctx['track_url']}\n"
        )
        send_email(booking["email"], f"Payment received — {booking['booking_id']}", html, text)


def send_payment_confirmed_admin(booking: dict, amount: float, method_name: str = "", source: str = ""):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "amount_label": f"${amount:,.2f}" if amount else "",
            "method_name": method_name or "Crypto",
            "source": source or "payment",
            "admin_url": admin_url,
        }
        html = render_template("email/admin_payment_confirmed.html", **ctx)
    text = (
        f"Payment confirmed for {booking['booking_id']} — {booking['name']}\n"
        f"Amount: {ctx['amount_label']}\nMethod: {ctx['method_name']}\n"
        f"Source: {source or 'payment'}\nReview: {admin_url}\n"
    )
    send_email(admin_email, f"Payment confirmed — {booking['booking_id']}", html, text)


def _crypto_payment_context(booking: dict, payment: dict) -> dict:
    pay_currency = (payment.get("pay_currency") or "").upper()
    pay_amount = payment.get("pay_amount") or ""
    return {
        **_brand_context(),
        "booking": booking,
        "payment": payment,
        "pay_currency": pay_currency,
        "pay_amount": pay_amount,
        "amount_label": f"${float(payment.get('amount') or 0):,.2f}",
        "payment_url": payment.get("payment_url") or "",
        "pay_address": payment.get("pay_address") or "",
        "track_url": _track_url(booking),
    }


def send_crypto_payment_created_customer(booking: dict, payment: dict):
    with _app_context():
        ctx = _crypto_payment_context(booking, payment)
        html = render_template("email/payment_crypto_created.html", **ctx)
        text = (
            f"Hi {booking['name']}, your crypto payment for {booking['booking_id']} is ready.\n"
            f"Send {ctx['pay_amount']} {ctx['pay_currency']} to complete payment.\n"
            f"Track: {ctx['track_url']}\n"
        )
        send_email(booking["email"], f"Complete your crypto payment — {booking['booking_id']}", html, text)


def send_crypto_payment_created_admin(booking: dict, payment: dict):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    with _app_context():
        ctx = {**_crypto_payment_context(booking, payment), "admin_url": admin_url}
        html = render_template("email/admin_crypto_payment_created.html", **ctx)
    text = (
        f"Crypto payment created for {booking['booking_id']} — {booking['name']}\n"
        f"Amount: {ctx['amount_label']}\n"
        f"Send: {ctx['pay_amount']} {ctx['pay_currency']}\n"
        f"Review: {admin_url}\n"
    )
    send_email(admin_email, f"Crypto payment started — {booking['booking_id']}", html, text)


def send_crypto_payment_processing_customer(booking: dict, payment: dict, status: str = ""):
    with _app_context():
        ctx = {
            **_crypto_payment_context(booking, payment),
            "status_label": (status or payment.get("status") or "processing").replace("_", " ").title(),
        }
        html = render_template("email/payment_crypto_processing.html", **ctx)
        text = (
            f"Hi {booking['name']}, we detected your crypto payment for {booking['booking_id']}.\n"
            f"Status: {ctx['status_label']}\n"
            f"Track: {ctx['track_url']}\n"
        )
        send_email(booking["email"], f"Payment detected — {booking['booking_id']}", html, text)


def send_crypto_payment_processing_admin(booking: dict, payment: dict, status: str = ""):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    with _app_context():
        ctx = {
            **_crypto_payment_context(booking, payment),
            "status_label": (status or payment.get("status") or "processing").replace("_", " ").title(),
            "admin_url": admin_url,
        }
        html = render_template("email/admin_crypto_payment_processing.html", **ctx)
    text = (
        f"Crypto payment detected for {booking['booking_id']} — {booking['name']}\n"
        f"Status: {ctx['status_label']}\n"
        f"Amount: {ctx['amount_label']}\n"
        f"Review: {admin_url}\n"
    )
    send_email(admin_email, f"Crypto payment detected — {booking['booking_id']}", html, text)


def send_payment_approved_admin(booking: dict, amount: float, method_name: str = ""):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "amount_label": f"${amount:,.2f}" if amount else "",
            "method_name": method_name or "Manual payment",
            "admin_url": admin_url,
        }
        html = render_template("email/admin_payment_approved.html", **ctx)
    text = (
        f"Payment approved for {booking['booking_id']} — {booking['name']}\n"
        f"Amount: {ctx['amount_label']}\nMethod: {ctx['method_name']}\n"
        f"Review: {admin_url}\n"
    )
    send_email(admin_email, f"Payment approved — {booking['booking_id']}", html, text)


def _attachment_url(path: str) -> str:
    if not path:
        return ""
    rel = path if path.startswith("/") else f"/data/{path.lstrip('/')}"
    return _absolute_url(rel)


def send_payment_pending_customer(booking: dict, amount: float, method_name: str = ""):
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "amount_label": f"${amount:,.2f}" if amount else "",
            "method_name": method_name or "your selected method",
            "track_url": _track_url(booking),
            "pay_url": _pay_url(booking),
        }
        html = render_template("email/payment_pending.html", **ctx)
        text = (
            f"Hi {booking['name']}, your payment for {booking['booking_id']} is pending confirmation.\n"
            f"Amount: {ctx['amount_label']}\nMethod: {ctx['method_name']}\n"
            f"We'll notify you once verified.\nTrack: {ctx['track_url']}\n"
        )
        send_email(booking["email"], f"Payment pending review — {booking['booking_id']}", html, text)


def send_admin_payment_proof(booking: dict, submission_id: int, method_name: str, note: str, proof_path: str):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    proof_url = _attachment_url(proof_path)
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "submission_id": submission_id,
            "method_name": method_name,
            "payment_note": note,
            "proof_url": proof_url,
            "admin_url": admin_url,
            "approve_url": f"{admin_url}?review_payment={submission_id}&action=approve",
            "reject_url": f"{admin_url}?review_payment={submission_id}&action=reject",
        }
        html = render_template("email/admin_payment_proof.html", **ctx)
    text = (
        f"Payment proof submitted for {booking['booking_id']} via {method_name}.\n"
        f"Note: {note}\nProof: {proof_url}\nReview: {admin_url}\n"
    )
    send_email(admin_email, f"Approve payment — {booking['booking_id']}", html, text)


def send_payment_approved_customer(booking: dict, amount: float, method_name: str = ""):
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "amount_label": f"${amount:,.2f}" if amount else "",
            "method_name": method_name,
            "track_url": _track_url(booking),
        }
        html = render_template("email/payment_approved.html", **ctx)
        text = f"Your payment for {booking['booking_id']} was approved. Session confirmed.\n{ctx['track_url']}\n"
        send_email(booking["email"], f"Payment approved — {booking['booking_id']}", html, text)


def send_payment_rejected_customer(booking: dict, method_name: str = "", review_note: str = ""):
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "method_name": method_name,
            "review_note": review_note,
            "track_url": _track_url(booking),
            "pay_url": _pay_url(booking),
        }
        html = render_template("email/payment_rejected.html", **ctx)
        text = (
            f"Your payment for {booking['booking_id']} could not be verified.\n"
            f"{review_note}\nPlease pay again: {ctx['pay_url']}\n"
        )
        send_email(booking["email"], f"Payment review update — {booking['booking_id']}", html, text)


def send_manual_payment_reminder_customer(booking: dict):
    with _app_context():
        ctx = {
            **_brand_context(),
            "booking": booking,
            "track_url": _track_url(booking),
            "pay_url": _pay_url(booking),
            "amount_label": (
                f"${float(booking.get('pricing_price')):,.2f}"
                if booking.get("pricing_price") not in (None, "")
                else ""
            ),
        }
        html = render_template("email/payment_reminder_manual.html", **ctx)
        text = (
            f"Hi {booking['name']}, this is a reminder to complete payment for {booking['booking_id']}.\n"
            f"Pay now: {ctx['pay_url']}\n"
        )
        send_email(booking["email"], f"Payment reminder — {booking['booking_id']}", html, text)


def send_crypto_payment_reminder_customer(booking: dict, payment: dict, minutes_left: int):
    with _app_context():
        ctx = {
            **_crypto_payment_context(booking, payment),
            "minutes_left": minutes_left,
            "pay_url": _pay_url(booking),
        }
        html = render_template("email/payment_reminder_crypto.html", **ctx)
        text = (
            f"Hi {booking['name']}, your crypto payment for {booking['booking_id']} expires in about {minutes_left} minutes.\n"
            f"Send {ctx['pay_amount']} {ctx['pay_currency']} to complete payment.\n"
            f"Continue: {ctx['pay_url']}\n"
        )
        send_email(
            booking["email"],
            f"Payment expires in {minutes_left} min — {booking['booking_id']}",
            html,
            text,
        )


def send_payment_expired_customer(booking: dict, payment: dict):
    with _app_context():
        ctx = {
            **_crypto_payment_context(booking, payment),
            "pay_url": _pay_url(booking),
        }
        html = render_template("email/payment_expired.html", **ctx)
        text = (
            f"Hi {booking['name']}, your crypto payment window for {booking['booking_id']} has expired.\n"
            f"You can start a new payment here: {ctx['pay_url']}\n"
        )
        send_email(booking["email"], f"Payment expired — {booking['booking_id']}", html, text)


def send_payment_expired_admin(booking: dict, payment: dict):
    settings = get_all_settings()
    admin_email = settings.get("admin_notification_email", "").strip()
    if not admin_email:
        return
    admin_url = _admin_booking_url(booking["booking_id"])
    with _app_context():
        ctx = {**_crypto_payment_context(booking, payment), "admin_url": admin_url}
        html = render_template("email/admin_payment_expired.html", **ctx)
    text = (
        f"Crypto payment expired for {booking['booking_id']} — {booking['name']}\n"
        f"Amount: {ctx['amount_label']}\nReview: {admin_url}\n"
    )
    send_email(admin_email, f"Payment expired — {booking['booking_id']}", html, text)

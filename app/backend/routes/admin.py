import json
import os
import uuid
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

from ..ai_service import generate_review
from ..database import UPLOAD_DIR, get_all_settings, get_db, now_iso, parse_json_field, set_settings
from ..themes import DEFAULT_THEME_ID, SITE_THEMES, theme_palette
from ..smtp_presets import SMTP_PRESETS
from ..booking_service import add_booking_message, get_booking_messages, update_booking_status
from ..device_service import block_device, list_blocked_devices, unblock_device
from ..payment_service import get_pending_payment_submissions, request_followup_payment, review_payment_submission
from ..email_service import send_email
from ..helpers import admin_required, verify_admin

admin_bp = Blueprint("admin", __name__)

ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".svg"}


@admin_bp.context_processor
def inject_admin_settings():
    if request.endpoint and request.endpoint != "admin.login":
        return {"admin_settings": get_all_settings()}
    return {}


def save_upload(file, subdir: str) -> str:
    if not file or not file.filename:
        return ""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        return ""
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / subdir
    dest.mkdir(parents=True, exist_ok=True)
    file.save(dest / filename)
    return f"uploads/{subdir}/{filename}"


@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_logged_in"):
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if verify_admin(email, password):
            session["admin_logged_in"] = True
            session["admin_email"] = email
            return redirect(url_for("admin.dashboard"))
        flash("Invalid credentials", "error")
    return render_template("admin/login.html")


@admin_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@admin_bp.route("/")
@admin_required
def dashboard():
    with get_db() as conn:
        stats = {
            "bookings_pending": conn.execute("SELECT COUNT(*) AS c FROM bookings WHERE status='pending'").fetchone()["c"],
            "bookings_total": conn.execute("SELECT COUNT(*) AS c FROM bookings").fetchone()["c"],
            "reviews_total": conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"],
            "services_total": conn.execute("SELECT COUNT(*) AS c FROM services WHERE active=1").fetchone()["c"],
        }
        recent = [dict(r) for r in conn.execute(
            "SELECT * FROM bookings ORDER BY created_at DESC LIMIT 8"
        ).fetchall()]
    return render_template("admin/dashboard.html", stats=stats, recent=recent)


@admin_bp.route("/branding", methods=["GET", "POST"])
@admin_required
def branding():
    if request.method == "POST":
        fields = [
            "business_name", "tagline", "footer_tagline", "hero_eyebrow", "hero_headline",
            "hero_subtext", "about_title", "about_text", "about_text_2", "footer_about",
            "footer_motto", "utility_bar_left", "utility_bar_right",
            "color_primary", "color_secondary", "color_accent", "color_text", "color_muted",
            "font_heading", "font_body", "site_theme", "site_base_url",
        ]
        data = {f: request.form.get(f, "") for f in fields}
        theme_id = data.get("site_theme") or DEFAULT_THEME_ID
        if theme_id != "custom" and theme_id in SITE_THEMES:
            data.update(theme_palette(theme_id))
            data["site_theme"] = theme_id
        else:
            data["site_theme"] = "custom"
        if "logo" in request.files:
            path = save_upload(request.files["logo"], "branding")
            if path:
                data["logo_path"] = path
        hero_upload = save_upload(request.files.get("hero_image_file"), "hero")
        if hero_upload:
            data["hero_image"] = hero_upload
        else:
            hero_url = request.form.get("hero_image", "").strip()
            if hero_url:
                data["hero_image"] = hero_url
        about_upload = save_upload(request.files.get("about_image_file"), "about")
        if about_upload:
            data["about_image"] = about_upload
        else:
            about_url = request.form.get("about_image", "").strip()
            if about_url:
                data["about_image"] = about_url
        set_settings(data)
        flash("Branding updated.", "success")
        return redirect(url_for("admin.branding"))
    settings = get_all_settings()
    return render_template(
        "admin/branding.html",
        settings=settings,
        themes=SITE_THEMES,
        current_theme=settings.get("site_theme", DEFAULT_THEME_ID),
    )


@admin_bp.route("/services", methods=["GET", "POST"])
@admin_required
def services():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                benefits = [b.strip() for b in request.form.get("benefits", "").split("\n") if b.strip()]
                conn.execute(
                    """INSERT INTO services (name, description, benefits, duration_min, duration_max, badge, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                    (
                        request.form.get("name"), request.form.get("description"),
                        json.dumps(benefits), int(request.form.get("duration_min", 60)),
                        int(request.form.get("duration_max", 90)), request.form.get("badge", ""),
                        int(request.form.get("sort_order", 0)), now_iso(),
                    ),
                )
                flash("Service added.", "success")
            elif action == "delete":
                conn.execute("DELETE FROM services WHERE id = ?", (request.form.get("id"),))
                flash("Service deleted.", "success")
            elif action == "update":
                benefits = [b.strip() for b in request.form.get("benefits", "").split("\n") if b.strip()]
                conn.execute(
                    """UPDATE services SET name=?, description=?, benefits=?, duration_min=?, duration_max=?,
                       badge=?, sort_order=?, active=? WHERE id=?""",
                    (
                        request.form.get("name"), request.form.get("description"), json.dumps(benefits),
                        int(request.form.get("duration_min", 60)), int(request.form.get("duration_max", 90)),
                        request.form.get("badge", ""), int(request.form.get("sort_order", 0)),
                        1 if request.form.get("active") else 0, request.form.get("id"),
                    ),
                )
                flash("Service updated.", "success")
        items = [dict(r) for r in conn.execute("SELECT * FROM services ORDER BY sort_order, id").fetchall()]
    for item in items:
        item["benefits"] = parse_json_field(item.get("benefits"))
    return render_template("admin/services.html", services=items)


@admin_bp.route("/pricing", methods=["GET", "POST"])
@admin_required
def pricing():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                conn.execute(
                    """INSERT INTO pricing_tiers (label, duration_minutes, price, description, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (request.form.get("label"), int(request.form.get("duration_minutes", 60)),
                     float(request.form.get("price", 0)), request.form.get("description", ""),
                     int(request.form.get("sort_order", 0)), now_iso()),
                )
            elif action == "delete":
                conn.execute("DELETE FROM pricing_tiers WHERE id = ?", (request.form.get("id"),))
            elif action == "update":
                conn.execute(
                    """UPDATE pricing_tiers SET label=?, duration_minutes=?, price=?, description=?, sort_order=?, active=? WHERE id=?""",
                    (request.form.get("label"), int(request.form.get("duration_minutes")),
                     float(request.form.get("price")), request.form.get("description"),
                     int(request.form.get("sort_order", 0)), 1 if request.form.get("active") else 0,
                     request.form.get("id")),
                )
            flash("Pricing updated.", "success")
        tiers = [dict(r) for r in conn.execute("SELECT * FROM pricing_tiers ORDER BY sort_order, id").fetchall()]
    return render_template("admin/pricing.html", tiers=tiers)


@admin_bp.route("/contacts", methods=["GET", "POST"])
@admin_required
def contacts():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                conn.execute(
                    """INSERT INTO contact_channels (channel_type, label, value, link_template, sort_order, active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    (request.form.get("channel_type"), request.form.get("label"),
                     request.form.get("value"), request.form.get("link_template", ""),
                     int(request.form.get("sort_order", 0))),
                )
            elif action == "delete":
                conn.execute("DELETE FROM contact_channels WHERE id = ?", (request.form.get("id"),))
            elif action == "update":
                conn.execute(
                    """UPDATE contact_channels SET channel_type=?, label=?, value=?, link_template=?, sort_order=?, active=? WHERE id=?""",
                    (request.form.get("channel_type"), request.form.get("label"), request.form.get("value"),
                     request.form.get("link_template"), int(request.form.get("sort_order", 0)),
                     1 if request.form.get("active") else 0, request.form.get("id")),
                )
            flash("Contact channels updated.", "success")
        channels = [dict(r) for r in conn.execute("SELECT * FROM contact_channels ORDER BY sort_order, id").fetchall()]
    return render_template("admin/contacts.html", channels=channels)


@admin_bp.route("/payments", methods=["GET", "POST"])
@admin_required
def payments():
    from ..payment_service import get_all_payment_methods

    if request.method == "POST":
        action = request.form.get("action")
        if action == "save_crypto":
            set_settings({
                "nowpayments_api_key": request.form.get("nowpayments_api_key", "").strip(),
                "nowpayments_ipn_secret": request.form.get("nowpayments_ipn_secret", "").strip(),
                "payment_crypto_enabled": "1" if request.form.get("payment_crypto_enabled") else "0",
                "np_fee_percentage": request.form.get("np_fee_percentage", "0").strip() or "0",
            }, preserve_secrets=True)
            flash("Crypto payment settings saved.", "success")
        else:
            with get_db() as conn:
                if action == "create":
                    conn.execute(
                        """INSERT INTO payment_methods
                           (name, method_type, instructions, pay_link, wallet_or_handle, sort_order, active, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                        (
                            request.form.get("name", "").strip(),
                            request.form.get("method_type", "other"),
                            request.form.get("instructions", "").strip(),
                            request.form.get("pay_link", "").strip(),
                            request.form.get("wallet_or_handle", "").strip(),
                            int(request.form.get("sort_order", 0)),
                            now_iso(),
                        ),
                    )
                elif action == "update":
                    conn.execute(
                        """UPDATE payment_methods
                           SET name=?, method_type=?, instructions=?, pay_link=?, wallet_or_handle=?, sort_order=?, active=?
                           WHERE id=?""",
                        (
                            request.form.get("name", "").strip(),
                            request.form.get("method_type", "other"),
                            request.form.get("instructions", "").strip(),
                            request.form.get("pay_link", "").strip(),
                            request.form.get("wallet_or_handle", "").strip(),
                            int(request.form.get("sort_order", 0)),
                            1 if request.form.get("active") else 0,
                            request.form.get("id"),
                        ),
                    )
                elif action == "delete":
                    conn.execute("DELETE FROM payment_methods WHERE id = ?", (request.form.get("id"),))
            flash("Payment methods updated.", "success")
        return redirect(url_for("admin.payments"))

    settings = get_all_settings()
    methods = get_all_payment_methods()
    return render_template("admin/payments.html", methods=methods, settings=settings)


@admin_bp.route("/bookings")
@admin_required
def bookings():
    status_filter = request.args.get("status", "")
    with get_db() as conn:
        if status_filter:
            rows = conn.execute("SELECT * FROM bookings WHERE status = ? ORDER BY created_at DESC", (status_filter,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
        items = [dict(r) for r in rows]
    return render_template("admin/bookings.html", bookings=items, status_filter=status_filter)


@admin_bp.route("/bookings/<booking_id>", methods=["GET", "POST"])
@admin_required
def booking_detail(booking_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
        if not row:
            flash("Booking not found.", "error")
            return redirect(url_for("admin.bookings"))
        booking = dict(row)
        if booking.get("service_id"):
            svc = conn.execute("SELECT name FROM services WHERE id=?", (booking["service_id"],)).fetchone()
            booking["service_name"] = svc["name"] if svc else ""
        if booking.get("pricing_id"):
            pr = conn.execute("SELECT label, price FROM pricing_tiers WHERE id=?", (booking["pricing_id"],)).fetchone()
            if pr:
                booking["pricing_label"] = pr["label"]
                booking["pricing_price"] = pr["price"]

        if request.method == "POST":
            action = request.form.get("action", "status")
            if action == "message":
                body = request.form.get("message_body", "").strip()
                if body:
                    add_booking_message(booking_id, "admin", body, "Admin")
                    flash("Message sent.", "success")
            elif action == "request_payment":
                note = request.form.get("payment_note", "").strip()
                amount_raw = request.form.get("payment_amount", "").strip()
                amount = float(amount_raw) if amount_raw else None
                request_followup_payment(booking_id, amount=amount, note=note or "Payment requested")
                with get_db() as conn:
                    brow = conn.execute("SELECT status FROM bookings WHERE booking_id = ?", (booking_id,)).fetchone()
                    if brow:
                        booking["status"] = brow["status"]
                flash("Payment request sent to customer chat.", "success")
            elif action == "review_payment":
                submission_id = int(request.form.get("submission_id", 0))
                approve = request.form.get("review_action") == "approve"
                review_note = request.form.get("review_note", "").strip()
                result = review_payment_submission(submission_id, approve, review_note=review_note)
                if result:
                    booking["status"] = "confirmed" if approve else "payment_pending"
                    flash("Payment approved." if approve else "Payment rejected — customer notified.", "success")
                else:
                    flash("Could not review payment.", "error")
            elif action == "block_device":
                reason = request.form.get("block_reason", "").strip() or "Blocked from admin booking detail"
                ok, msg = block_device(
                    device_id=booking.get("device_id", ""),
                    ip_address=booking.get("client_ip", ""),
                    email=booking.get("email", ""),
                    reason=reason,
                    source_booking_id=booking_id,
                )
                flash("Device blocked from visiting the site." if ok else msg, "success" if ok else "error")
            elif action == "suspend_booking":
                note = request.form.get("suspend_note", "").strip() or "Session suspended by admin"
                update_booking_status(booking_id, "suspended", note=note, source="admin")
                booking["status"] = "suspended"
                flash("Booking suspended. Customer can no longer track this session.", "success")
            else:
                new_status = request.form.get("status", booking["status"])
                note = request.form.get("note", "")
                update_booking_status(booking_id, new_status, note=note, source="admin")
                booking["status"] = new_status
                flash("Booking status updated.", "success")

        history = [dict(r) for r in conn.execute(
            "SELECT * FROM booking_status_log WHERE booking_id = ? ORDER BY created_at", (booking_id,)
        ).fetchall()]
    messages = get_booking_messages(booking_id)
    pending_payments = get_pending_payment_submissions(booking_id)
    return render_template(
        "admin/booking_detail.html",
        booking=booking,
        history=history,
        messages=messages,
        pending_payments=pending_payments,
    )


@admin_bp.route("/blocked-devices", methods=["GET", "POST"])
@admin_required
def blocked_devices():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "unblock":
            block_id = int(request.form.get("block_id", 0))
            if unblock_device(block_id):
                flash("Device unblocked.", "success")
            else:
                flash("Could not unblock device.", "error")
        elif action == "create":
            ok, msg = block_device(
                device_id=request.form.get("device_id", "").strip(),
                ip_address=request.form.get("ip_address", "").strip(),
                email=request.form.get("email", "").strip(),
                reason=request.form.get("reason", "").strip() or "Manually blocked",
            )
            flash("Device blocked." if ok else msg, "success" if ok else "error")
    items = list_blocked_devices()
    return render_template("admin/blocked_devices.html", blocked=items)


@admin_bp.route("/masseuses", methods=["GET", "POST"])
@admin_required
def masseuses():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                specs = [s.strip() for s in request.form.get("specialties", "").split("\n") if s.strip()]
                img = save_upload(request.files.get("image"), "masseuses")
                conn.execute(
                    """INSERT INTO masseuses (name, bio, specialties, image_path, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (request.form.get("name"), request.form.get("bio", ""), json.dumps(specs),
                     img, int(request.form.get("sort_order", 0)), now_iso()),
                )
            elif action == "delete":
                conn.execute("DELETE FROM masseuses WHERE id = ?", (request.form.get("id"),))
            elif action == "update":
                specs = [s.strip() for s in request.form.get("specialties", "").split("\n") if s.strip()]
                img = save_upload(request.files.get("image"), "masseuses")
                if img:
                    conn.execute(
                        "UPDATE masseuses SET name=?, bio=?, specialties=?, image_path=?, sort_order=?, active=? WHERE id=?",
                        (request.form.get("name"), request.form.get("bio"), json.dumps(specs), img,
                         int(request.form.get("sort_order", 0)), 1 if request.form.get("active") else 0,
                         request.form.get("id")),
                    )
                else:
                    conn.execute(
                        "UPDATE masseuses SET name=?, bio=?, specialties=?, sort_order=?, active=? WHERE id=?",
                        (request.form.get("name"), request.form.get("bio"), json.dumps(specs),
                         int(request.form.get("sort_order", 0)), 1 if request.form.get("active") else 0,
                         request.form.get("id")),
                    )
            flash("Masseuse updated.", "success")
        items = [dict(r) for r in conn.execute("SELECT * FROM masseuses ORDER BY sort_order, id").fetchall()]
    for item in items:
        item["specialties"] = parse_json_field(item.get("specialties"))
    return render_template("admin/masseuses.html", masseuses=items)


@admin_bp.route("/reviews", methods=["GET", "POST"])
@admin_required
def reviews():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "create":
                conn.execute(
                    """INSERT INTO reviews (author_name, title, body, rating, review_date, visible, ai_generated, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (request.form.get("author_name"), request.form.get("title"), request.form.get("body"),
                     int(request.form.get("rating", 5)), request.form.get("review_date", now_iso()[:10]),
                     1 if request.form.get("ai_generated") else 0, now_iso()),
                )
            elif action == "delete":
                conn.execute("DELETE FROM reviews WHERE id = ?", (request.form.get("id"),))
            elif action == "toggle":
                conn.execute("UPDATE reviews SET visible = CASE WHEN visible=1 THEN 0 ELSE 1 END WHERE id = ?", (request.form.get("id"),))
            elif action == "generate":
                ok, result = generate_review(
                    request.form.get("keywords", ""), request.form.get("service", ""),
                    int(request.form.get("rating", 5)),
                )
                if ok:
                    conn.execute(
                        """INSERT INTO reviews (author_name, title, body, rating, review_date, visible, ai_generated, created_at)
                           VALUES (?, ?, ?, ?, ?, 1, 1, ?)""",
                        (result["author_name"], result["title"], result["body"], result["rating"],
                         now_iso()[:10], now_iso()),
                    )
                    flash("AI review generated and published.", "success")
                else:
                    flash(f"AI error: {result}", "error")
            else:
                flash("Review saved.", "success")
        items = [dict(r) for r in conn.execute("SELECT * FROM reviews ORDER BY review_date DESC").fetchall()]
    return render_template("admin/reviews.html", reviews=items)


@admin_bp.route("/gallery", methods=["GET", "POST"])
@admin_required
def gallery():
    with get_db() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action == "upload":
                path = save_upload(request.files.get("image"), "gallery")
                if path:
                    conn.execute(
                        "INSERT INTO gallery_images (filename, alt_text, sort_order, active, created_at) VALUES (?, ?, ?, 1, ?)",
                        (path, request.form.get("alt_text", ""), int(request.form.get("sort_order", 0)), now_iso()),
                    )
            elif action == "delete":
                conn.execute("DELETE FROM gallery_images WHERE id = ?", (request.form.get("id"),))
            flash("Gallery updated.", "success")
        images = [dict(r) for r in conn.execute("SELECT * FROM gallery_images ORDER BY sort_order, id").fetchall()]
    return render_template("admin/gallery.html", images=images)


@admin_bp.route("/email", methods=["GET", "POST"])
@admin_required
def email_settings():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "save":
            preset_id = request.form.get("smtp_preset", "custom")
            preset = SMTP_PRESETS.get(preset_id, SMTP_PRESETS["custom"])
            user = request.form.get("smtp_user", "").strip()
            from_email = request.form.get("smtp_from_email", "").strip() or user
            set_settings({
                "smtp_preset": preset_id,
                "smtp_host": request.form.get("smtp_host", "") or preset.get("host", ""),
                "smtp_port": request.form.get("smtp_port", "") or preset.get("port", "587"),
                "smtp_user": user,
                "smtp_password": request.form.get("smtp_password", ""),
                "smtp_from_name": request.form.get("smtp_from_name", ""),
                "smtp_from_email": from_email,
                "smtp_use_tls": "1" if request.form.get("smtp_use_tls") else "0",
                "admin_notification_email": request.form.get("admin_notification_email", "").strip() or from_email,
                "email_on_booking": "1" if request.form.get("email_on_booking") else "0",
                "email_on_status_change": "1" if request.form.get("email_on_status_change") else "0",
                "email_on_chat_message": "1" if request.form.get("email_on_chat_message") else "0",
                "email_on_customer_message": "1" if request.form.get("email_on_customer_message") else "0",
            }, preserve_secrets=True)
            flash("Email settings saved.", "success")
        elif action == "test":
            ok, msg = send_email(
                request.form.get("test_email", ""),
                "Test email from Serenity",
                "<p>If you received this, SMTP is working.</p>",
            )
            flash("Test email sent!" if ok else f"Test failed: {msg}", "success" if ok else "error")
        return redirect(url_for("admin.email_settings"))
    settings = get_all_settings()
    return render_template(
        "admin/email.html",
        settings=settings,
        smtp_presets=SMTP_PRESETS,
        current_smtp_preset=settings.get("smtp_preset", "gmail"),
    )


@admin_bp.route("/ai", methods=["GET", "POST"], endpoint="ai")
@admin_required
def ai_settings():
    if request.method == "POST":
        set_settings({
            "openrouter_api_key": request.form.get("openrouter_api_key", ""),
            "openrouter_model": request.form.get("openrouter_model", "openai/gpt-4o-mini"),
            "openrouter_tone": request.form.get("openrouter_tone", ""),
        }, preserve_secrets=True)
        flash("AI settings saved.", "success")
        return redirect(url_for("admin.ai"))
    return render_template("admin/ai.html", settings=get_all_settings())


@admin_bp.route("/account", methods=["GET", "POST"])
@admin_required
def account():
    if request.method == "POST":
        with get_db() as conn:
            if request.form.get("new_password"):
                conn.execute(
                    "UPDATE admin_users SET password_hash = ? WHERE email = ?",
                    (generate_password_hash(request.form.get("new_password")), session.get("admin_email")),
                )
                flash("Password updated.", "success")
    return render_template("admin/account.html")


@admin_bp.route("/telegram", methods=["GET", "POST"])
@admin_required
def telegram_settings():
    from ..telegram_poller import is_polling, restart_telegram_poller

    if request.method == "POST":
        action = request.form.get("action", "save")
        if action == "save":
            set_settings({
                "telegram_bot_token": request.form.get("telegram_bot_token", ""),
                "telegram_admin_chat_id": request.form.get("telegram_admin_chat_id", ""),
                "telegram_notifications_enabled": "1" if request.form.get("telegram_notifications_enabled") else "0",
            }, preserve_secrets=True)
            restart_telegram_poller()
            flash("Telegram settings saved. Polling restarted.", "success")
        elif action == "test":
            from ..telegram_service import send_message
            chat_id = request.form.get("telegram_admin_chat_id", "").strip()
            ok = send_message(chat_id, "✅ Test notification from your wellness admin panel.")
            flash("Test message sent!" if ok else "Failed to send test message.", "success" if ok else "error")
        return redirect(url_for("admin.telegram_settings"))

    return render_template(
        "admin/telegram.html",
        settings=get_all_settings(),
        polling_active=is_polling(),
    )

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..booking_service import create_booking, get_booking_messages, resolve_booking_access
from ..database import get_db
from ..device_service import device_block_message, get_device_context
from ..helpers import build_contact_link, site_context
from ..payment_service import get_booking_payment_info

public_bp = Blueprint("public", __name__)


@public_bp.before_request
def enforce_device_access():
    if request.endpoint and request.endpoint.startswith("admin."):
        return None
    if request.path.startswith("/data/"):
        return None
    blocked = device_block_message()
    if not blocked:
        return None
    if request.path.startswith("/api/"):
        from flask import jsonify
        return jsonify({"error": blocked, "code": "device_blocked"}), 403
    return render_template("public/blocked.html", message=blocked), 403


@public_bp.route("/")
def home():
    return render_template("public/home.html", page="home")


@public_bp.route("/services")
def services():
    return render_template("public/services.html", page="services")


@public_bp.route("/prices")
def prices():
    return render_template("public/prices.html", page="pricing")


@public_bp.route("/gallery")
def gallery():
    return render_template("public/gallery.html", page="gallery")


@public_bp.route("/review")
def reviews():
    with get_db() as conn:
        all_reviews = [dict(r) for r in conn.execute(
            "SELECT * FROM reviews WHERE visible = 1 ORDER BY review_date DESC"
        ).fetchall()]
    ctx = site_context()
    ctx["all_reviews"] = all_reviews
    return render_template("public/reviews.html", page="reviews", **ctx)


@public_bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        device_ctx = get_device_context()
        booking, error = create_booking(request.form.to_dict(), device_ctx=device_ctx)
        if error:
            flash(error, "error")
            return redirect(url_for("public.contact"))
        flash(
            f"Booking confirmed! Your ID is {booking['booking_id']}. "
            "Check your inbox for confirmation — if you don't see it, check spam, junk, or trash.",
            "success",
        )
        return redirect(url_for("public.track", booking_id=booking["booking_id"], email=booking["email"]))
    return render_template("public/contact.html", page="contact")


@public_bp.route("/track", methods=["GET", "POST"])
def track():
    booking = None
    history = []
    messages = []
    access_error = None
    if request.method == "POST" or request.args.get("booking_id"):
        booking_id = (request.form.get("booking_id") or request.args.get("booking_id", "")).strip()
        email = (request.form.get("email") or request.args.get("email", "")).strip().lower()
        booking, err = resolve_booking_access(booking_id, email)
        if err == "suspended":
            access_error = "suspended"
            flash("This session has been suspended and is no longer available to track.", "error")
        elif not booking:
            flash("No booking found with that ID and email.", "error")
        else:
            with get_db() as conn:
                history = [dict(r) for r in conn.execute(
                    "SELECT * FROM booking_status_log WHERE booking_id = ? ORDER BY created_at",
                    (booking_id,),
                ).fetchall()]
                svc = conn.execute("SELECT name FROM services WHERE id=?", (booking.get("service_id"),)).fetchone()
                pr = conn.execute("SELECT label, price FROM pricing_tiers WHERE id=?", (booking.get("pricing_id"),)).fetchone()
                if svc:
                    booking["service_name"] = svc["name"]
                if pr:
                    booking["pricing_label"] = pr["label"]
                    booking["pricing_price"] = pr["price"]
            messages = get_booking_messages(booking_id)

    payment_info = None
    if booking:
        from ..payment_service import build_payment_ui_state
        payment_info = get_booking_payment_info(booking)
        ui_state = build_payment_ui_state(booking)
        payment_info["payment_requests"] = ui_state.get("payment_requests", [])
        payment_info["active_crypto_payments"] = ui_state.get("active_crypto_payments", [])

    return render_template(
        "public/track.html",
        page="track",
        booking=booking,
        history=history,
        messages=messages,
        payment_info=payment_info,
        access_error=access_error,
    )


@public_bp.app_template_filter("contact_link")
def contact_link_filter(channel):
    return build_contact_link(channel)

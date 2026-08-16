"""Shared helpers for templates and API responses."""
import re
from functools import wraps

from flask import jsonify, redirect, session, url_for
from werkzeug.security import check_password_hash

from .database import get_all_settings, get_db, parse_json_field, rows_to_list
from .stock_images import STOCK_ABOUT, STOCK_HERO
from .support_faqs import get_support_faqs
from .themes import resolve_site_theme


def admin_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return redirect(url_for("admin.login"))
        return f(*args, **kwargs)
    return wrap


def admin_api_required(f):
    @wraps(f)
    def wrap(*args, **kwargs):
        if not session.get("admin_logged_in"):
            return jsonify({"error": "Unauthorized"}), 401
        return f(*args, **kwargs)
    return wrap


def verify_admin(email: str, password: str) -> bool:
    with get_db() as conn:
        row = conn.execute("SELECT password_hash FROM admin_users WHERE email = ?", (email,)).fetchone()
        if not row:
            return False
        return check_password_hash(row["password_hash"], password)


def site_context() -> dict:
    settings = get_all_settings()
    with get_db() as conn:
        services = rows_to_list(conn.execute(
            "SELECT * FROM services WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())
        pricing = rows_to_list(conn.execute(
            "SELECT * FROM pricing_tiers WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())
        contacts = rows_to_list(conn.execute(
            "SELECT * FROM contact_channels WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())
        reviews = rows_to_list(conn.execute(
            "SELECT * FROM reviews WHERE visible = 1 ORDER BY review_date DESC LIMIT 8"
        ).fetchall())
        masseuses = rows_to_list(conn.execute(
            "SELECT * FROM masseuses WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())
        gallery = rows_to_list(conn.execute(
            "SELECT * FROM gallery_images WHERE active = 1 ORDER BY sort_order, id"
        ).fetchall())

    for svc in services:
        svc["benefits"] = parse_json_field(svc.get("benefits"))
    for m in masseuses:
        m["specialties"] = parse_json_field(m.get("specialties"))

    review_count = len(reviews)
    avg_rating = round(sum(r["rating"] for r in reviews) / review_count, 1) if review_count else 5.0

    return {
        "settings": settings,
        "business_name": settings.get("business_name", "Serenity Wellness"),
        "tagline": settings.get("tagline", "Luxury Wellness & Massage"),
        "services": services,
        "pricing": pricing,
        "contacts": contacts,
        "reviews": reviews,
        "masseuses": masseuses,
        "gallery": gallery,
        "review_count": review_count,
        "avg_rating": avg_rating,
        "theme": resolve_site_theme(settings),
        "hero_image": media_url(settings.get("hero_image") or STOCK_HERO),
        "about_image": media_url(settings.get("about_image") or STOCK_ABOUT),
        "support_faqs": get_support_faqs(settings),
    }


def generate_booking_id() -> str:
    import random
    import string
    suffix = "".join(random.choices(string.digits, k=4))
    return f"BK-{suffix}"


def build_contact_link(channel: dict) -> str:
    template = channel.get("link_template") or ""
    value = channel.get("value") or ""
    if not template:
        return value
    clean = re.sub(r"[^0-9+]", "", value) if channel["channel_type"] in ("phone", "imessage", "signal") else value
    return template.replace("{value}", clean)


def media_url(path: str) -> str:
    if not path:
        return ""
    path = str(path).strip()
    if path.startswith("http://") or path.startswith("https://"):
        return path
    if path.startswith("/data/"):
        return path
    if path.startswith("/static/"):
        return path
    if path.startswith("/uploads/"):
        return f"/data{path}"
    if path.startswith("uploads/"):
        return f"/data/{path}"
    if path.startswith("img/"):
        return f"/static/{path}"
    if path.startswith("/img/"):
        return f"/static{path}"
    return f"/data/{path.lstrip('/')}"


def stars_html(rating: int) -> str:
    rating = max(1, min(5, int(rating or 5)))
    return "★" * rating + "☆" * (5 - rating)

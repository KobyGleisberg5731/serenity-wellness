"""Seed default data from MassageSanctuary reference site."""
import json

from werkzeug.security import generate_password_hash

from .database import get_all_settings, get_db, init_db, now_iso, seed_settings_defaults, set_settings
from .stock_images import STOCK_ABOUT, STOCK_GALLERY, STOCK_HERO, STOCK_MASSEUSES
from .stock_image_factory import ensure_stock_images


def seed_database(admin_email: str = "admin@serenity.local", admin_password: str = "admin123"):
    init_db()
    ensure_stock_images()

    defaults = {
        "business_name": "MassageSanctuary",
        "tagline": "Luxury Wellness & Massage",
        "footer_tagline": "Massage • Wellness • Renewal",
        "hero_eyebrow": "Feminine Wellness • By Appointment",
        "hero_headline": "A softer space to relax, restore, and glow.",
        "hero_subtext": "Step into a calm private sanctuary designed for comfort, renewal, and deeply soothing care. Every session is shaped to ease tension, quiet the mind, and leave you feeling beautifully reset.",
        "about_title": "A gentle sanctuary for relaxation, renewal, and care.",
        "about_text": "At MassageSanctuary, every session is designed with softness and intention. The ambiance, the pace, and the care all come together to help you exhale, unwind, and feel beautifully restored.",
        "about_text_2": "From soothing full-body treatments to deeper restorative massage, each experience is tailored to your comfort and wellness needs. Privacy, professionalism, and a calming feminine touch stay at the heart of every visit.",
        "footer_about": "An intimate wellness experience centered on softness, peace, and premium care. Thoughtful treatments, calming ambiance, and gentle restoration by appointment.",
        "footer_motto": "Soft. Private. Premium.",
        "utility_bar_left": "Private wellness appointments",
        "utility_bar_right": "Soft care • Calm rituals • Luxury touch",
        "color_primary": "#d4849a",
        "color_secondary": "#fff9fc",
        "color_accent": "#e8a0bf",
        "color_text": "#2d2a2e",
        "color_muted": "#7a6f74",
        "site_theme": "rose_sanctuary",
        "font_heading": "'Cormorant Garamond', Georgia, serif",
        "font_body": "'DM Sans', system-ui, sans-serif",
        "hero_image": STOCK_HERO,
        "about_image": STOCK_ABOUT,
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_preset": "gmail",
        "smtp_user": "",
        "smtp_password": "",
        "smtp_from_name": "MassageSanctuary",
        "smtp_from_email": "",
        "smtp_use_tls": "1",
        "admin_notification_email": "",
        "email_on_booking": "1",
        "email_on_status_change": "1",
        "telegram_bot_token": "",
        "telegram_admin_chat_id": "",
        "telegram_notifications_enabled": "0",
        "telegram_webhook_secret": "",
        "telegram_webhook_base_url": "",
        "site_base_url": "",
        "email_on_chat_message": "1",
        "email_on_customer_message": "1",
        "nowpayments_api_key": "",
        "nowpayments_ipn_secret": "",
        "payment_crypto_enabled": "1",
        "np_fee_percentage": "0",
        "openrouter_api_key": "",
        "openrouter_model": "openai/gpt-4o-mini",
        "openrouter_tone": "warm, professional spa review",
        "welcome_modal_enabled": "1",
        "welcome_modal_title": "A soft note before your visit",
        "welcome_modal_body": "We're dedicated to creating a calm, private, and premium wellness experience from your first message to your final moment of relaxation.",
    }
    seed_settings_defaults(defaults)

    with get_db() as conn:
        if conn.execute("SELECT COUNT(*) AS c FROM admin_users").fetchone()["c"] == 0:
            conn.execute(
                "INSERT INTO admin_users (email, password_hash, created_at) VALUES (?, ?, ?)",
                (admin_email, generate_password_hash(admin_password), now_iso()),
            )

        if conn.execute("SELECT COUNT(*) AS c FROM services").fetchone()["c"] == 0:
            services = [
                ("Swedish", "A soothing full-body massage designed to quiet tension, calm the mind, and leave you feeling deeply restored.",
                 '["Deep relaxation","Stress relief","Improved circulation","Full body reset"]', 60, 90, "Signature", 1),
                ("Deep Tissue Renewal", "Targeted therapeutic work focused on relieving muscle tension, easing tight areas, and restoring comfortable movement.",
                 '["Relieves muscle tension","Supports mobility","Reduces stiffness","Encourages recovery"]', 60, 120, "Restorative", 2),
                ("Full Body Serenity", "A balanced head-to-toe treatment blending flowing relaxation techniques with restorative care for complete calm.",
                 '["Complete body relaxation","Stress reduction","Improved sleep","Mental clarity"]', 90, 120, "Wellness", 3),
                ("Private Escape", "A soft luxury session centered on comfort, privacy, and intentional care in a calming feminine setting.",
                 '["Peaceful atmosphere","Personalized pacing","Relaxation support","Tailored experience"]', 60, 90, "Private", 4),
            ]
            for s in services:
                conn.execute(
                    """INSERT INTO services (name, description, benefits, duration_min, duration_max, badge, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                    (*s, now_iso()),
                )

        if conn.execute("SELECT COUNT(*) AS c FROM pricing_tiers").fetchone()["c"] == 0:
            tiers = [
                ("40 Minutes", 40, 200, "A short focused session for quick relief and relaxation.", 1),
                ("60 Minutes", 60, 250, "A balanced full session for calm, comfort, and reset.", 2),
                ("90 Minutes", 90, 300, "Extended time for deeper restoration and full-body care.", 3),
                ("120 Minutes", 120, 400, "A longer premium treatment for a more complete experience.", 4),
                ("150 Minutes", 150, 450, "A shared wellness experience designed for comfort and calm.", 5),
                ("180 Minutes", 180, 500, "Tailored treatment options based on your needs and goals.", 6),
                ("240 Minutes", 240, 700, "Tailored treatment options based on your needs and goals.", 7),
                ("Full Nights", 480, 1000, "Tailored treatment options based on your needs and goals.", 8),
            ]
            for t in tiers:
                conn.execute(
                    """INSERT INTO pricing_tiers (label, duration_minutes, price, description, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (*t, now_iso()),
                )

        if conn.execute("SELECT COUNT(*) AS c FROM contact_channels").fetchone()["c"] == 0:
            channels = [
                ("phone", "Phone", "+1 (945) 394-0542", "tel:{value}", 1),
                ("email", "Email", "massagesanctuary9@gmail.com", "mailto:{value}", 2),
                ("telegram", "Telegram", "massagesanctuary", "https://t.me/{value}", 3),
                ("discord", "Discord", "@massage_sanctuary", "https://discord.com/users/{value}", 4),
                ("imessage", "iMessage", "+1 (945) 394-0542", "sms:{value}", 5),
                ("signal", "Signal", "+1 (945) 394-0542", "sms:{value}", 6),
            ]
            for c in channels:
                conn.execute(
                    """INSERT INTO contact_channels (channel_type, label, value, link_template, sort_order, active)
                       VALUES (?, ?, ?, ?, ?, 1)""",
                    c,
                )

        if conn.execute("SELECT COUNT(*) AS c FROM reviews").fetchone()["c"] == 0:
            reviews = [
                ("Amanda R.", "Absolutely amazing", "I felt lighter, calmer, and deeply relaxed after my session.", 5, "2026-07-24"),
                ("James K.", "Premium experience", "Very professional, peaceful, and welcoming. The whole experience felt premium from start to finish.", 5, "2026-07-20"),
                ("Sophia M.", "Most soothing session", "One of the most soothing wellness sessions I've had in years.", 5, "2026-07-11"),
                ("Chris B.", "Exceptional hands", "Every knot and tight muscle was expertly worked out. Outstanding experience.", 5, "2026-06-20"),
                ("Emily T.", "Muscle magician", "Worked miracles on my shoulders. She knows exactly what to do.", 5, "2026-06-07"),
            ]
            for r in reviews:
                conn.execute(
                    """INSERT INTO reviews (author_name, title, body, rating, review_date, visible, ai_generated, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, 0, ?)""",
                    (*r, now_iso()),
                )

        if conn.execute("SELECT COUNT(*) AS c FROM gallery_images").fetchone()["c"] == 0:
            for i, (url, alt) in enumerate(STOCK_GALLERY, start=1):
                conn.execute(
                    "INSERT INTO gallery_images (filename, alt_text, sort_order, active, created_at) VALUES (?, ?, ?, 1, ?)",
                    (url, alt, i, now_iso()),
                )

        if conn.execute("SELECT COUNT(*) AS c FROM masseuses").fetchone()["c"] == 0:
            for i, m in enumerate(STOCK_MASSEUSES, start=1):
                conn.execute(
                    """INSERT INTO masseuses (name, bio, specialties, image_path, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, 1, ?)""",
                    (m["name"], m["bio"], json.dumps(m["specialties"]), m["image"], i, now_iso()),
                )

        if conn.execute("SELECT COUNT(*) AS c FROM payment_methods").fetchone()["c"] == 0:
            defaults_methods = [
                ("Venmo", "venmo", "Send payment to @YourVenmo and include your booking ID in the note.", "", "@YourVenmo", 1),
                ("Zelle", "zelle", "Send via Zelle to the email or phone below. Use your booking ID as the memo.", "", "you@email.com", 2),
                ("Cash App", "cashapp", "Send to $YourCashTag with your booking ID in the note.", "https://cash.app/", "$YourCashTag", 3),
            ]
            for name, mtype, instructions, link, handle, sort_order in defaults_methods:
                conn.execute(
                    """INSERT INTO payment_methods
                       (name, method_type, instructions, pay_link, wallet_or_handle, sort_order, active, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
                    (name, mtype, instructions, link, handle, sort_order, now_iso()),
                )

    settings = get_all_settings()
    updates = {}
    if not settings.get("hero_image"):
        updates["hero_image"] = STOCK_HERO
    if not settings.get("about_image"):
        updates["about_image"] = STOCK_ABOUT
    if updates:
        set_settings(updates)

    settings = get_all_settings()
    if not settings.get("site_theme"):
        set_settings({"site_theme": "rose_sanctuary"})

    repair_external_media()


def repair_external_media():
    """Replace broken remote stock URLs with bundled local images."""
    settings = get_all_settings()
    updates = {}
    for key in ("hero_image", "about_image"):
        val = settings.get(key, "")
        if val.startswith("http://") or val.startswith("https://"):
            updates[key] = STOCK_HERO if key == "hero_image" else STOCK_ABOUT
    if updates:
        set_settings(updates)

    with get_db() as conn:
        for row in conn.execute("SELECT id, filename FROM gallery_images").fetchall():
            if row["filename"].startswith("http://") or row["filename"].startswith("https://"):
                idx = (row["id"] - 1) % len(STOCK_GALLERY)
                conn.execute(
                    "UPDATE gallery_images SET filename = ? WHERE id = ?",
                    (STOCK_GALLERY[idx][0], row["id"]),
                )
        for row in conn.execute("SELECT id, image_path FROM masseuses").fetchall():
            if row["image_path"].startswith("http://") or row["image_path"].startswith("https://"):
                idx = (row["id"] - 1) % len(STOCK_MASSEUSES)
                conn.execute(
                    "UPDATE masseuses SET image_path = ? WHERE id = ?",
                    (STOCK_MASSEUSES[idx]["image"], row["id"]),
                )

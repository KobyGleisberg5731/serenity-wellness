"""SQLite database layer for Serenity Wellness platform."""
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
UPLOAD_DIR = DATA_DIR / "uploads"
DB_PATH = DATA_DIR / "serenity.db"


def ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (UPLOAD_DIR / "gallery").mkdir(exist_ok=True)
    (UPLOAD_DIR / "masseuses").mkdir(exist_ok=True)
    (UPLOAD_DIR / "branding").mkdir(exist_ok=True)
    (UPLOAD_DIR / "hero").mkdir(exist_ok=True)
    (UPLOAD_DIR / "about").mkdir(exist_ok=True)
    (UPLOAD_DIR / "payment_proofs").mkdir(exist_ok=True)


@contextmanager
def get_db():
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    ensure_dirs()
    with get_db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS site_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            benefits TEXT NOT NULL DEFAULT '[]',
            duration_min INTEGER NOT NULL DEFAULT 60,
            duration_max INTEGER NOT NULL DEFAULT 90,
            badge TEXT DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pricing_tiers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            label TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            price REAL NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS contact_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_type TEXT NOT NULL,
            label TEXT NOT NULL,
            value TEXT NOT NULL,
            link_template TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT DEFAULT '',
            zip_code TEXT DEFAULT '',
            service_id INTEGER,
            pricing_id INTEGER,
            preferred_datetime TEXT NOT NULL,
            message TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS booking_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            status TEXT NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS booking_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            sender_type TEXT NOT NULL,
            sender_name TEXT DEFAULT '',
            body TEXT NOT NULL,
            message_type TEXT NOT NULL DEFAULT 'text',
            attachment_path TEXT DEFAULT '',
            meta_json TEXT DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            method_id INTEGER,
            method_name TEXT NOT NULL DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            note TEXT DEFAULT '',
            proof_path TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            review_note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            reviewed_at TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS masseuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            bio TEXT NOT NULL DEFAULT '',
            specialties TEXT NOT NULL DEFAULT '[]',
            image_path TEXT DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            author_name TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            rating INTEGER NOT NULL DEFAULT 5,
            review_date TEXT NOT NULL,
            visible INTEGER NOT NULL DEFAULT 1,
            ai_generated INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS gallery_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            alt_text TEXT NOT NULL DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_methods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            method_type TEXT NOT NULL DEFAULT 'other',
            instructions TEXT NOT NULL DEFAULT '',
            pay_link TEXT DEFAULT '',
            wallet_or_handle TEXT DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS booking_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            provider TEXT NOT NULL DEFAULT 'nowpayments',
            external_id TEXT DEFAULT '',
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            pay_currency TEXT DEFAULT '',
            pay_address TEXT DEFAULT '',
            pay_amount TEXT DEFAULT '',
            payment_url TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'waiting',
            expires_at TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS payment_reminder_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            payment_id INTEGER,
            reminder_key TEXT NOT NULL,
            sent_at TEXT NOT NULL
        );
        """)
        _migrate(conn)


def _migrate(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    if "masseuse_id" not in cols:
        conn.execute("ALTER TABLE bookings ADD COLUMN masseuse_id INTEGER")

    pay_cols = {r[1] for r in conn.execute("PRAGMA table_info(booking_payments)").fetchall()}
    if pay_cols and "expires_at" not in pay_cols:
        conn.execute("ALTER TABLE booking_payments ADD COLUMN expires_at TEXT DEFAULT ''")
    if pay_cols and "request_message_id" not in pay_cols:
        conn.execute("ALTER TABLE booking_payments ADD COLUMN request_message_id INTEGER")

    msg_cols = {r[1] for r in conn.execute("PRAGMA table_info(booking_messages)").fetchall()}
    if msg_cols:
        if "message_type" not in msg_cols:
            conn.execute("ALTER TABLE booking_messages ADD COLUMN message_type TEXT NOT NULL DEFAULT 'text'")
        if "attachment_path" not in msg_cols:
            conn.execute("ALTER TABLE booking_messages ADD COLUMN attachment_path TEXT DEFAULT ''")
        if "meta_json" not in msg_cols:
            conn.execute("ALTER TABLE booking_messages ADD COLUMN meta_json TEXT DEFAULT '{}'")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS payment_reminder_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id TEXT NOT NULL,
            payment_id INTEGER,
            reminder_key TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE UNIQUE INDEX IF NOT EXISTS idx_payment_reminder_once
           ON payment_reminder_log(payment_id, reminder_key)
           WHERE payment_id IS NOT NULL"""
    )

    booking_cols = {r[1] for r in conn.execute("PRAGMA table_info(bookings)").fetchall()}
    for col, typedef in [
        ("client_ip", "TEXT DEFAULT ''"),
        ("user_agent", "TEXT DEFAULT ''"),
        ("device_id", "TEXT DEFAULT ''"),
        ("device_fingerprint", "TEXT DEFAULT ''"),
    ]:
        if col not in booking_cols:
            conn.execute(f"ALTER TABLE bookings ADD COLUMN {col} {typedef}")

    conn.execute(
        """CREATE TABLE IF NOT EXISTS blocked_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT DEFAULT '',
            ip_address TEXT DEFAULT '',
            email TEXT DEFAULT '',
            reason TEXT DEFAULT '',
            source_booking_id TEXT DEFAULT '',
            blocked_by TEXT DEFAULT 'admin',
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocked_device_id ON blocked_devices(device_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_blocked_ip ON blocked_devices(ip_address)")


def now_iso() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def get_setting(key: str, default: str = "") -> str:
    with get_db() as conn:
        row = conn.execute("SELECT value FROM site_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_all_settings() -> dict:
    with get_db() as conn:
        rows = conn.execute("SELECT key, value FROM site_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


SECRET_SETTING_KEYS = frozenset({
    "smtp_password",
    "telegram_bot_token",
    "openrouter_api_key",
    "nowpayments_api_key",
    "nowpayments_ipn_secret",
})


def set_settings(data: dict, preserve_secrets: bool = False):
    """Persist settings. When preserve_secrets=True, blank secret fields keep existing values."""
    if preserve_secrets:
        existing = get_all_settings()
        data = dict(data)
        for key in SECRET_SETTING_KEYS:
            if key in data and not str(data.get(key, "")).strip():
                if existing.get(key):
                    data[key] = existing[key]
    with get_db() as conn:
        for key, value in data.items():
            conn.execute(
                "INSERT INTO site_settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )


def seed_settings_defaults(defaults: dict):
    """Only insert default values for keys not already saved — never wipe user settings on restart."""
    existing = get_all_settings()
    missing = {k: v for k, v in defaults.items() if k not in existing}
    if missing:
        set_settings(missing)


def row_to_dict(row) -> dict:
    if row is None:
        return {}
    return dict(row)


def rows_to_list(rows) -> list:
    return [dict(r) for r in rows]


def parse_json_field(value, default=None):
    if default is None:
        default = []
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default

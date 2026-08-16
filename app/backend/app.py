"""Main Flask application."""
import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS

from .database import init_db
from .routes.admin import admin_bp
from .routes.api import api_bp
from .routes.public import public_bp
from .seed import seed_database

BASE_DIR = Path(__file__).resolve().parent.parent


def create_app():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "templates"),
        static_folder=str(BASE_DIR / "static"),
    )
    app.secret_key = os.environ.get("SECRET_KEY", "serenity-change-me-in-production")
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024
    CORS(app)

    init_db()
    seed_database(
        admin_email=os.environ.get("ADMIN_EMAIL", "admin@serenity.local"),
        admin_password=os.environ.get("ADMIN_PASSWORD", "admin123"),
    )

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(api_bp, url_prefix="/api")

    # Trust X-Forwarded-* from nginx / Cloudflare tunnel in production.
    from werkzeug.middleware.proxy_fix import ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.route("/data/<path:filename>")
    def serve_data(filename):
        from flask import send_from_directory
        from .database import DATA_DIR
        return send_from_directory(DATA_DIR, filename)

    @app.template_filter("media_url")
    def media_url_filter(path):
        from .helpers import media_url
        return media_url(path)

    @app.context_processor
    def inject_globals():
        from .helpers import site_context
        return {"site": site_context()}

    from .telegram_poller import start_telegram_poller
    start_telegram_poller(app)

    from .payment_reminder_poller import start_payment_reminder_poller
    start_payment_reminder_poller(app)

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 18871))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")

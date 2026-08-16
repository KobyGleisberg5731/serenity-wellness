"""Background long-polling for Telegram bot updates (no webhook required)."""
import os
import threading
import time

_poller_thread: threading.Thread | None = None
_poller_stop = threading.Event()
_poller_running = False
_update_offset = 0
_flask_app = None


def is_polling() -> bool:
    return _poller_running and _poller_thread is not None and _poller_thread.is_alive()


def stop_telegram_poller():
    global _poller_running
    _poller_stop.set()
    _poller_running = False


def _poll_loop():
    global _poller_running, _update_offset
    from .telegram_service import clear_webhook, handle_update, is_enabled, poll_updates

    clear_webhook()
    _poller_running = True
    _update_offset = 0

    while not _poller_stop.is_set():
        if not is_enabled():
            time.sleep(3)
            continue
        try:
            updates, _update_offset = poll_updates(_update_offset)
            for update in updates:
                try:
                    if _flask_app is not None:
                        with _flask_app.app_context():
                            handle_update(update)
                    else:
                        handle_update(update)
                except Exception:
                    pass
        except Exception:
            time.sleep(5)


def start_telegram_poller(flask_app=None):
    """Start background polling thread (safe to call multiple times — restarts)."""
    global _poller_thread, _flask_app

    if flask_app is not None:
        _flask_app = flask_app

    stop_telegram_poller()
    _poller_stop.clear()

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG", "0") == "1":
        return

    _poller_thread = threading.Thread(target=_poll_loop, daemon=True, name="telegram-poller")
    _poller_thread.start()


def restart_telegram_poller():
    start_telegram_poller()

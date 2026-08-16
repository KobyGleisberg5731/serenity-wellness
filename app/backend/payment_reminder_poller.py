"""Background poller for payment reminder emails."""
import os
import threading
import time

_poller_thread: threading.Thread | None = None
_poller_stop = threading.Event()
_poller_running = False
_flask_app = None
POLL_INTERVAL_SECONDS = 60


def is_running() -> bool:
    return _poller_running and _poller_thread is not None and _poller_thread.is_alive()


def stop_payment_reminder_poller():
    global _poller_running
    _poller_stop.set()
    _poller_running = False


def _poll_loop():
    global _poller_running
    from .payment_reminder_service import process_payment_reminders

    _poller_running = True
    while not _poller_stop.is_set():
        try:
            if _flask_app is not None:
                with _flask_app.app_context():
                    process_payment_reminders()
            else:
                process_payment_reminders()
        except Exception:
            pass
        _poller_stop.wait(POLL_INTERVAL_SECONDS)


def start_payment_reminder_poller(flask_app=None):
    global _poller_thread, _flask_app

    if flask_app is not None:
        _flask_app = flask_app

    stop_payment_reminder_poller()
    _poller_stop.clear()

    if os.environ.get("WERKZEUG_RUN_MAIN") != "true" and os.environ.get("FLASK_DEBUG", "0") == "1":
        return

    _poller_thread = threading.Thread(
        target=_poll_loop,
        daemon=True,
        name="payment-reminder-poller",
    )
    _poller_thread.start()

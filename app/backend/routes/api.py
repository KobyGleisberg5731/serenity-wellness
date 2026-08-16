from flask import Blueprint, jsonify, request

from ..booking_service import (
    add_booking_message,
    create_booking,
    get_booking_messages,
    resolve_booking_access,
)
from ..database import UPLOAD_DIR, get_db, now_iso
from ..device_service import device_block_message, get_device_context
from ..helpers import admin_api_required, site_context
from ..nowpayments_client import get_crypto_min_amount
from ..payment_service import (
    booking_amount_due,
    booking_allows_payment,
    build_payment_ui_state,
    create_crypto_payment,
    get_booking_payment_info,
    handle_nowpayments_webhook,
    mark_payment_submitted,
    np_fee_pct,
    refresh_crypto_payment_status,
    resolve_payment_amount,
    total_with_fee,
    verify_nowpayments_webhook,
)
from ..crypto_tokens import list_networks, list_tokens

api_bp = Blueprint("api", __name__)

ALLOWED_PROOF_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".pdf"}


@api_bp.before_request
def api_device_guard():
    if request.path.startswith("/api/admin/"):
        return None
    if request.path in ("/api/health", "/api/nowpayments/webhook"):
        return None
    blocked = device_block_message()
    if blocked:
        return jsonify({"error": blocked, "code": "device_blocked"}), 403
    return None


def _access_booking(booking_id: str, email: str):
    blocked = device_block_message()
    if blocked:
        return None, ({"error": blocked, "code": "device_blocked"}, 403)
    booking, err = resolve_booking_access(booking_id, email)
    if err == "suspended":
        return None, ({
            "error": "This session has been suspended and is no longer available.",
            "code": "suspended",
        }, 403)
    if not booking:
        return None, ({"error": "Unauthorized"}, 403)
    return booking, None


def _save_payment_proof(file) -> str:
    import uuid
    from pathlib import Path
    if not file or not file.filename:
        return ""
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_PROOF_EXT:
        return ""
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = UPLOAD_DIR / "payment_proofs"
    dest.mkdir(parents=True, exist_ok=True)
    file.save(dest / filename)
    return f"uploads/payment_proofs/{filename}"


@api_bp.route("/health")
def health():
    return jsonify({"status": "ok"})


@api_bp.route("/site")
def site():
    ctx = site_context()
    return jsonify({
        "business_name": ctx["business_name"],
        "services": ctx["services"],
        "pricing": ctx["pricing"],
    })


@api_bp.route("/bookings", methods=["POST"])
def create_booking_api():
    blocked = device_block_message()
    if blocked:
        return jsonify({"error": blocked, "code": "device_blocked"}), 403
    data = request.get_json(silent=True) or request.form.to_dict()
    device_ctx = get_device_context(data=data)
    booking, error = create_booking(data, device_ctx=device_ctx)
    if error:
        return jsonify({"error": error}), 400
    return jsonify({
        "ok": True,
        "booking": {
            "booking_id": booking["booking_id"],
            "name": booking["name"],
            "email": booking["email"],
            "status": booking["status"],
            "preferred_datetime": booking["preferred_datetime"],
            "service_name": booking.get("service_name", ""),
            "pricing_label": booking.get("pricing_label", ""),
        },
        "track_url": f"/track?booking_id={booking['booking_id']}&email={booking['email']}",
    })


@api_bp.route("/bookings/track", methods=["POST"])
def track_booking():
    blocked = device_block_message()
    if blocked:
        return jsonify({"error": blocked, "code": "device_blocked"}), 403
    data = request.get_json(silent=True) or {}
    booking_id = (data.get("booking_id") or "").strip()
    email = (data.get("email") or "").strip().lower()
    if not booking_id or not email:
        return jsonify({"error": "booking_id and email required"}), 400
    booking, err = resolve_booking_access(booking_id, email)
    if err == "suspended":
        return jsonify({"error": "This session has been suspended and is no longer available to track.", "code": "suspended"}), 403
    if not booking:
        return jsonify({"error": "Not found"}), 404
    history = []
    with get_db() as conn:
        history = [dict(r) for r in conn.execute(
            "SELECT status, note, created_at FROM booking_status_log WHERE booking_id = ? ORDER BY created_at",
            (booking_id,),
        ).fetchall()]
    messages = get_booking_messages(booking_id)
    return jsonify({"booking": booking, "history": history, "messages": messages})


@api_bp.route("/bookings/<booking_id>/messages", methods=["GET", "POST"])
def booking_messages(booking_id):
    if request.method == "GET":
        email = (request.args.get("email") or "").strip().lower()
        booking, denied = _access_booking(booking_id, email)
        if denied:
            return jsonify(denied[0]), denied[1]
        messages = get_booking_messages(booking_id)
        ui_state = build_payment_ui_state(booking)
        pr_map = {int(p["message_id"]): p for p in ui_state.get("payment_requests", [])}
        for msg in messages:
            if msg.get("message_type") != "payment_request":
                continue
            pr = pr_map.get(int(msg.get("id") or 0))
            if not pr:
                continue
            meta = dict(msg.get("meta") or {})
            meta["pay_status"] = pr.get("pay_status", meta.get("pay_status", "open"))
            if pr.get("active_payment"):
                meta["active_payment"] = pr["active_payment"]
            msg["meta"] = meta
        return jsonify({"messages": messages, "payment_state": ui_state})

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    body = (data.get("body") or "").strip()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]
    if not body:
        return jsonify({"error": "Message required"}), 400
    msg = add_booking_message(booking_id, "customer", body, booking["name"])
    return jsonify({"ok": True, "message": msg})


@api_bp.route("/admin/bookings/<booking_id>/messages", methods=["POST"])
@admin_api_required
def admin_booking_message(booking_id):
    data = request.get_json(silent=True) or request.form.to_dict()
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "Message required"}), 400
    msg = add_booking_message(booking_id, "admin", body, "Admin")
    if not msg:
        return jsonify({"error": "Booking not found"}), 404
    return jsonify({"ok": True, "message": msg})


@api_bp.route("/payments/crypto/tokens")
def crypto_tokens():
    from ..nowpayments_client import fetch_available_currencies

    _, api_ok = fetch_available_currencies()
    tokens = list_tokens()
    return jsonify({"tokens": tokens, "api_connected": api_ok, "count": len(tokens)})


@api_bp.route("/payments/crypto/networks")
def crypto_networks():
    token = (request.args.get("token") or "").strip()
    if not token:
        return jsonify({"error": "token required"}), 400
    networks = list_networks(token)
    if not networks:
        return jsonify({
            "error": f"No {token.upper()} networks are enabled on your NowPayments account.",
            "networks": [],
        }), 404
    for network in networks:
        network["min_amount"] = get_crypto_min_amount(network["code"])
    networks.sort(key=lambda item: item.get("min_amount") if item.get("min_amount") is not None else 9999)
    return jsonify({"networks": networks})


@api_bp.route("/bookings/<booking_id>/payment/crypto/quote", methods=["GET"])
def booking_crypto_quote(booking_id):
    email = (request.args.get("email") or "").strip().lower()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]
    amount_raw = request.args.get("amount")
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    base_amount = resolve_payment_amount(booking, amount)
    fee = np_fee_pct()
    total = total_with_fee(base_amount)
    pay_currency = (request.args.get("pay_currency") or "").strip().lower()
    min_amount = get_crypto_min_amount(pay_currency) if pay_currency else None
    return jsonify({
        "amount": base_amount,
        "fee_percent": fee,
        "fee_amount": round(total - base_amount, 2),
        "total": total,
        "pay_currency": pay_currency,
        "min_amount": min_amount,
        "below_minimum": bool(min_amount and total < min_amount),
    })


@api_bp.route("/bookings/<booking_id>/payment", methods=["GET"])
def booking_payment_info(booking_id):
    email = (request.args.get("email") or "").strip().lower()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]
    return jsonify(get_booking_payment_info(booking))


@api_bp.route("/bookings/<booking_id>/payment/crypto", methods=["POST"])
def booking_payment_crypto(booking_id):
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]
    message_id_raw = data.get("message_id")
    try:
        message_id = int(message_id_raw) if message_id_raw not in (None, "") else None
    except (TypeError, ValueError):
        message_id = None
    if not booking_allows_payment(booking, message_id):
        return jsonify({"error": "Payment is not required for this booking."}), 400
    pay_currency = (data.get("pay_currency") or "usdttrc20").strip().lower()
    amount_raw = data.get("amount")
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None
    payment, error = create_crypto_payment(
        booking, pay_currency, amount=amount, message_id=message_id
    )
    if error:
        return jsonify({"error": error}), 400
    resolved_amount = payment.get("amount") or resolve_payment_amount(booking, amount)
    ui_state = build_payment_ui_state(booking, payment)
    return jsonify({
        "ok": True,
        "payment": payment,
        "payment_state": ui_state,
        "quote": {
            "amount": resolved_amount,
            "fee_percent": np_fee_pct(),
            "total": total_with_fee(resolved_amount),
        },
    })


@api_bp.route("/bookings/<booking_id>/payment/submitted", methods=["POST"])
def booking_payment_submitted(booking_id):
    email = (request.form.get("email") or (request.get_json(silent=True) or {}).get("email") or "").strip().lower()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]

    data = request.get_json(silent=True) or request.form.to_dict()
    message_id_raw = data.get("message_id")
    try:
        message_id = int(message_id_raw) if message_id_raw not in (None, "") else None
    except (TypeError, ValueError):
        message_id = None
    if not booking_allows_payment(booking, message_id):
        return jsonify({"error": "Payment has already been submitted or is not required."}), 400

    proof_file = request.files.get("proof")
    proof_path = _save_payment_proof(proof_file) if proof_file else ""
    if not proof_path:
        return jsonify({"error": "Please upload a payment proof image or screenshot."}), 400

    method_id = data.get("method_id")
    try:
        method_id = int(method_id) if method_id else None
    except (TypeError, ValueError):
        method_id = None
    amount_raw = data.get("amount")
    try:
        amount = float(amount_raw) if amount_raw not in (None, "") else None
    except (TypeError, ValueError):
        amount = None

    updated = mark_payment_submitted(
        booking_id,
        method_name=(data.get("method_name") or "").strip(),
        note=(data.get("note") or "").strip(),
        method_id=method_id,
        proof_path=proof_path,
        amount=amount,
        message_id=message_id,
    )
    if not updated:
        return jsonify({"error": "Could not submit payment."}), 400
    return jsonify({"ok": True, "booking": {"booking_id": updated["booking_id"], "status": updated["status"]}})


@api_bp.route("/bookings/<booking_id>/payment/status", methods=["GET"])
def booking_payment_status(booking_id):
    email = (request.args.get("email") or "").strip().lower()
    booking, denied = _access_booking(booking_id, email)
    if denied:
        return jsonify(denied[0]), denied[1]
    result = refresh_crypto_payment_status(booking_id)
    if "payment_requests" not in result:
        result.update(build_payment_ui_state(booking, result.get("payment")))
    return jsonify(result)


@api_bp.route("/nowpayments/webhook", methods=["POST"])
def nowpayments_webhook():
    signature = request.headers.get("x-nowpayments-sig", "")
    raw = request.get_data()
    if not verify_nowpayments_webhook(raw, signature):
        return jsonify({"error": "Invalid signature"}), 403
    payload = request.get_json(silent=True) or {}
    handle_nowpayments_webhook(payload)
    return jsonify({"ok": True})


@api_bp.route("/reviews", methods=["POST"])
def submit_review():
    data = request.get_json(silent=True) or request.form
    title = (data.get("title") or "").strip()
    body = (data.get("body") or "").strip()
    if not title or not body:
        return jsonify({"error": "title and body required"}), 400
    with get_db() as conn:
        conn.execute(
            """INSERT INTO reviews (author_name, title, body, rating, review_date, visible, ai_generated, created_at)
               VALUES (?, ?, ?, ?, ?, 0, 0, ?)""",
            (
                (data.get("author_name") or "Guest").strip(), title, body,
                int(data.get("rating", 5)), now_iso()[:10], now_iso(),
            ),
        )
    return jsonify({"ok": True, "message": "Review submitted for approval"})

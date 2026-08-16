"""NowPayments API client — matches v20 flow (requests + live currencies)."""
import json
import logging
import time

import requests

from .database import get_all_settings

logger = logging.getLogger(__name__)

API_BASE = "https://api.nowpayments.io/v1"
REQUEST_TIMEOUT = 20
CURRENCY_CACHE_TTL = 300

_currency_cache: dict = {"codes": None, "fetched_at": 0.0, "ok": False}

_DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "SerenityWellness/1.0 (NowPayments)",
    "Accept": "application/json",
}


def _api_key() -> str:
    return (get_all_settings().get("nowpayments_api_key") or "").strip()


def _headers() -> dict:
    headers = dict(_DEFAULT_HEADERS)
    key = _api_key()
    if key:
        headers["x-api-key"] = key
    return headers


def nowpayments_request(method: str, path: str, payload: dict | None = None) -> tuple[dict, int]:
    """Call NowPayments API. Returns (body_dict, http_status)."""
    if not _api_key():
        return {"message": "Crypto payments are not configured yet."}, 0

    url = f"{API_BASE}{path if path.startswith('/') else '/' + path}"
    try:
        if method.upper() == "GET":
            resp = requests.get(url, headers=_headers(), timeout=REQUEST_TIMEOUT)
        else:
            resp = requests.post(url, headers=_headers(), json=payload or {}, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as exc:
        logger.warning("NowPayments request failed: %s", exc)
        return {"message": str(exc)}, 0

    text = (resp.text or "").strip()
    try:
        body = resp.json() if text else {}
    except json.JSONDecodeError:
        body = {"message": text or resp.reason}

    if not isinstance(body, dict):
        body = {"message": str(body)}

    if resp.status_code >= 400 and not body.get("message"):
        body["message"] = text or resp.reason or f"NowPayments error ({resp.status_code})"

    if resp.status_code >= 400:
        logger.warning("NowPayments %s %s -> %s: %s", method, path, resp.status_code, body)

    return body, resp.status_code


def _parse_currency_codes(data: dict) -> set[str]:
    raw = data.get("currencies", [])
    codes: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, str):
                codes.add(item.lower())
            elif isinstance(item, dict):
                code = (item.get("code") or item.get("ticker") or "").strip().lower()
                if code:
                    codes.add(code)
    return codes


def fetch_available_currencies(force: bool = False) -> tuple[set[str] | None, bool]:
    """Return (currency_codes, api_ok). None codes = use static fallback list."""
    global _currency_cache
    now = time.time()
    if (
        not force
        and _currency_cache["codes"] is not None
        and (now - _currency_cache["fetched_at"]) < CURRENCY_CACHE_TTL
    ):
        return _currency_cache["codes"], _currency_cache["ok"]

    body, status = nowpayments_request("GET", "/currencies")
    if status == 200 and body.get("currencies"):
        codes = _parse_currency_codes(body)
        _currency_cache = {"codes": codes, "fetched_at": now, "ok": True}
        return codes, True

    _currency_cache = {"codes": None, "fetched_at": now, "ok": False}
    return None, False


def get_crypto_min_amount(pay_currency: str) -> float | None:
    """Minimum USD total for a pay currency (mono-currency pair, not usd→crypto)."""
    currency = (pay_currency or "").strip().lower()
    if not currency:
        return None
    body, status = nowpayments_request(
        "GET",
        f"/min-amount?currency_from={currency}&currency_to={currency}&fiat_equivalent=usd",
    )
    if status != 200:
        return None
    try:
        # fiat_equivalent is the USD floor; min_amount is in crypto units.
        value = float(body.get("fiat_equivalent") or body.get("min_amount") or 0)
        return value if value > 0 else None
    except (TypeError, ValueError):
        return None


def humanize_crypto_error(message: str, pay_currency: str = "", total: float = 0, status: int = 0) -> str:
    msg = (message or "").strip()
    lower = msg.lower()
    if status == 0 and ("cloudflare" in lower or "1010" in lower or "access denied" in lower):
        return (
            "Crypto payments are temporarily blocked from this server. "
            "Please use Venmo, Zelle, Cash App, or another manual payment method."
        )
    if "less than minimal" in lower or "minimum" in lower or "too small" in lower:
        return (
            f"The payment total (${total:,.2f}) is below the minimum for "
            f"{pay_currency.upper()}. Try a higher amount or choose another payment method."
        )
    if status in (401, 403) or "api key" in lower or "unauthorized" in lower or "invalid api" in lower:
        return "Crypto payments are not configured correctly. Please use another payment method."
    if "currency" in lower and ("not found" in lower or "invalid" in lower or "disabled" in lower or "not available" in lower):
        return f"{pay_currency.upper()} is not available on your account. Please pick another network."
    if "1010" in msg:
        return (
            "Crypto payment gateway blocked this request (error 1010). "
            "Use a manual payment method or contact support."
        )
    return msg or "Could not create crypto payment. Try again or use another method."

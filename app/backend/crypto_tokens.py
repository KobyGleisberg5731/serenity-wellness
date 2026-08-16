"""Crypto token and network options — matches v20 flow with current NowPayments codes."""

# API codes must match exactly what NowPayments expects (see GET /v1/currencies).
TOKEN_NETWORKS = {
    "BTC": [("BTC (Native)", "btc")],
    "ETH": [("ERC-20 (Ethereum)", "eth")],
    "USDT": [
        ("TRC-20 (Tron)", "usdttrc20"),
        ("ERC-20 (Ethereum)", "usdterc20"),
        ("BEP-20 (BSC)", "usdtbsc"),
        ("Polygon", "usdtmatic"),
        ("Arbitrum", "usdtarb"),
        ("Solana", "usdtsol"),
        ("Optimism", "usdtop"),
        ("Avalanche C-Chain", "usdtarc20"),
        ("CELO", "usdtcelo"),
        ("TON", "usdtton"),
    ],
    "USDC": [
        ("ERC-20 (Ethereum)", "usdc"),
        ("Polygon", "usdcmatic"),
        ("Base", "usdcbase"),
        ("Arbitrum", "usdcarb"),
        ("Solana", "usdcsol"),
        ("Optimism", "usdcop"),
        ("BEP-20 (BSC)", "usdcbsc"),
        ("Algorand", "usdcalgo"),
        ("Avalanche C-Chain", "usdcarc20"),
    ],
    "LTC": [("LTC (Native)", "ltc")],
    "XRP": [("XRP (Native)", "xrp")],
    "BNB": [("BEP-20 (BSC)", "bnbbsc")],
    "SOL": [("Solana", "sol")],
    "TRX": [("TRX (Tron)", "trx")],
    "DOGE": [("DOGE (Native)", "doge")],
    "TON": [("TON (Native)", "ton")],
    "MATIC": [("Polygon", "matic")],
    "ADA": [("ADA (Native)", "ada")],
    "BCH": [("BCH (Native)", "bch")],
    "DASH": [("DASH (Native)", "dash")],
    "XMR": [("XMR (Native)", "xmr")],
    "DOT": [("DOT (Native)", "dot")],
    "AVAX": [("AVAX (Native)", "avax")],
    "LINK": [("ERC-20 (Ethereum)", "link")],
    "SHIB": [
        ("ERC-20 (Ethereum)", "shib"),
        ("BEP-20 (BSC)", "shibbsc"),
    ],
}

# Display order (matches v20 bot)
TOKEN_ORDER = [
    "BTC", "ETH", "USDT", "USDC", "LTC", "XRP", "BNB", "SOL", "TRX",
    "DOGE", "TON", "MATIC", "ADA", "BCH", "DASH", "XMR", "DOT", "AVAX", "LINK", "SHIB",
]


def _available_codes() -> set[str] | None:
    from .nowpayments_client import fetch_available_currencies

    codes, ok = fetch_available_currencies()
    return codes if ok else None


def list_tokens() -> list[dict]:
    """Return full token list (v20 shows all tokens; availability checked at payment time)."""
    return [
        {"code": code, "label": code}
        for code in TOKEN_ORDER
        if code in TOKEN_NETWORKS
    ]


def list_networks(token: str) -> list[dict]:
    """Return all networks for a token (v20 shows full network list per token)."""
    token = (token or "").upper()
    options = TOKEN_NETWORKS.get(token, [])
    if not options:
        code = (token or "").lower()
        return [{"label": token, "code": code}]
    return [{"label": label, "code": code} for label, code in options]


def is_currency_available(pay_currency: str) -> bool:
    code = (pay_currency or "").strip().lower()
    if not code:
        return False
    available = _available_codes()
    if available is None:
        return True
    return code in available

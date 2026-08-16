"""Preset support questions and answers for the public chat widget."""
import json

DEFAULT_SUPPORT_FAQS = [
    {
        "question": "How do I book a session?",
        "answer": "Tap Book a Session on any page to request an appointment, or use our Contact page. We'll confirm your time by email.",
    },
    {
        "question": "What are your prices?",
        "answer": "Visit our Pricing page for current session rates. Final pricing may depend on treatment length and therapist selection.",
    },
    {
        "question": "How do I track my booking?",
        "answer": "Open Track Booking from the menu and enter your booking ID and email. You can view status updates and message our team there.",
    },
    {
        "question": "What payment methods do you accept?",
        "answer": "We accept the payment options shown when your booking is ready for payment — such as Venmo, Zelle, Cash App, or crypto if enabled.",
    },
    {
        "question": "Can I reschedule my session?",
        "answer": "Yes. Message us through your booking track page or contact us directly and we'll help find a new time.",
    },
    {
        "question": "Is my visit private?",
        "answer": "Absolutely. All sessions are by appointment in a calm, private wellness space focused on your comfort.",
    },
]


def get_support_faqs(settings: dict | None = None) -> list[dict]:
    settings = settings or {}
    raw = settings.get("support_faqs", "")
    if raw:
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list):
                faqs = [
                    {"question": (item.get("question") or "").strip(), "answer": (item.get("answer") or "").strip()}
                    for item in data
                    if (item.get("question") or "").strip()
                ]
                if faqs:
                    return faqs
        except (json.JSONDecodeError, TypeError, AttributeError):
            pass
    return DEFAULT_SUPPORT_FAQS

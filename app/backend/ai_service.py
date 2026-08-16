"""AI review generation via OpenRouter."""
import requests

from .database import get_all_settings


def generate_review(keywords: str = "", service: str = "", rating: int = 5) -> tuple[bool, dict | str]:
    settings = get_all_settings()
    api_key = settings.get("openrouter_api_key", "").strip()
    model = settings.get("openrouter_model", "openai/gpt-4o-mini")
    tone = settings.get("openrouter_tone", "warm, professional spa review")

    if not api_key:
        return False, "OpenRouter API key not configured"

    prompt = f"""Write a short, authentic spa/massage guest review.
Tone: {tone}
Star rating: {rating}/5
Service type: {service or 'wellness massage'}
Keywords/mood: {keywords or 'relaxing, professional, calm'}

Return JSON only with keys: author_name (first name + last initial), title (short), body (2-3 sentences)."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://serenity-wellness.local",
                "X-Title": settings.get("business_name", "Serenity Wellness"),
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
            },
            timeout=45,
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"].strip()
        import json
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        data = json.loads(content)
        return True, {
            "author_name": data.get("author_name", "Guest"),
            "title": data.get("title", "Wonderful experience"),
            "body": data.get("body", ""),
            "rating": rating,
        }
    except Exception as exc:
        return False, str(exc)

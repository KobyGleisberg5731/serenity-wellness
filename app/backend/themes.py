"""Predefined site theme presets for the public storefront."""

SITE_THEMES = {
    "rose_sanctuary": {
        "name": "Rose Sanctuary",
        "description": "Soft pink luxury — warm, feminine, and calming.",
        "swatch": ["#d4849a", "#fff9fc", "#e8a0bf"],
        "colors": {
            "color_primary": "#d4849a",
            "color_secondary": "#fff9fc",
            "color_accent": "#e8a0bf",
            "color_text": "#2d2a2e",
            "color_muted": "#7a6f74",
        },
        "fonts": {
            "font_heading": "'Cormorant Garamond', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
    "sage_serenity": {
        "name": "Sage Serenity",
        "description": "Earthy greens for a natural, grounded spa feel.",
        "swatch": ["#6b8f71", "#f6f8f4", "#a8c5a0"],
        "colors": {
            "color_primary": "#6b8f71",
            "color_secondary": "#f6f8f4",
            "color_accent": "#a8c5a0",
            "color_text": "#1f2a22",
            "color_muted": "#5c6b5f",
        },
        "fonts": {
            "font_heading": "'Cormorant Garamond', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
    "ocean_calm": {
        "name": "Ocean Calm",
        "description": "Cool blues and teals for a refreshing, tranquil mood.",
        "swatch": ["#5b8fa8", "#f4f9fb", "#8ecae6"],
        "colors": {
            "color_primary": "#5b8fa8",
            "color_secondary": "#f4f9fb",
            "color_accent": "#8ecae6",
            "color_text": "#1a2a32",
            "color_muted": "#5a6f78",
        },
        "fonts": {
            "font_heading": "'Cormorant Garamond', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
    "lavender_dream": {
        "name": "Lavender Dream",
        "description": "Soft purple tones for a dreamy, restorative atmosphere.",
        "swatch": ["#9b7bb8", "#faf8fc", "#c4a8d8"],
        "colors": {
            "color_primary": "#9b7bb8",
            "color_secondary": "#faf8fc",
            "color_accent": "#c4a8d8",
            "color_text": "#2a2430",
            "color_muted": "#756a80",
        },
        "fonts": {
            "font_heading": "'Cormorant Garamond', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
    "golden_warmth": {
        "name": "Golden Warmth",
        "description": "Warm amber and cream for a sunlit, premium retreat.",
        "swatch": ["#c4956a", "#fdf9f3", "#e8c9a0"],
        "colors": {
            "color_primary": "#c4956a",
            "color_secondary": "#fdf9f3",
            "color_accent": "#e8c9a0",
            "color_text": "#2e261f",
            "color_muted": "#7a6f63",
        },
        "fonts": {
            "font_heading": "'Playfair Display', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
    "midnight_luxe": {
        "name": "Midnight Luxe",
        "description": "Dark elegance with gold accents for a boutique spa.",
        "swatch": ["#c9a962", "#1a181b", "#e8d5a3"],
        "colors": {
            "color_primary": "#c9a962",
            "color_secondary": "#1a181b",
            "color_accent": "#e8d5a3",
            "color_text": "#f5f3f0",
            "color_muted": "#9a9590",
        },
        "fonts": {
            "font_heading": "'Cormorant Garamond', Georgia, serif",
            "font_body": "'DM Sans', system-ui, sans-serif",
        },
    },
}

DEFAULT_THEME_ID = "rose_sanctuary"


def get_theme(theme_id: str) -> dict | None:
    return SITE_THEMES.get(theme_id)


def list_themes() -> list[dict]:
    return [
        {"id": tid, **{k: v for k, v in meta.items() if k != "colors" and k != "fonts"}}
        for tid, meta in SITE_THEMES.items()
    ]


def theme_palette(theme_id: str) -> dict:
    """Return resolved colors + fonts for a theme id, or empty dict if custom/unknown."""
    preset = get_theme(theme_id)
    if not preset:
        return {}
    return {**preset["colors"], **preset["fonts"]}


def resolve_site_theme(settings: dict) -> dict:
    """Build the public theme dict from settings + optional preset."""
    theme_id = settings.get("site_theme", DEFAULT_THEME_ID)
    if theme_id != "custom" and theme_id in SITE_THEMES:
        preset = SITE_THEMES[theme_id]
        colors = preset["colors"]
        fonts = preset["fonts"]
    else:
        colors = {
            "color_primary": settings.get("color_primary", "#d4849a"),
            "color_secondary": settings.get("color_secondary", "#fff9fc"),
            "color_accent": settings.get("color_accent", "#e8a0bf"),
            "color_text": settings.get("color_text", "#2d2a2e"),
            "color_muted": settings.get("color_muted", "#7a6f74"),
        }
        fonts = {
            "font_heading": settings.get("font_heading", "'Cormorant Garamond', Georgia, serif"),
            "font_body": settings.get("font_body", "'DM Sans', system-ui, sans-serif"),
        }

    return {
        "id": theme_id,
        "name": SITE_THEMES[theme_id]["name"] if theme_id in SITE_THEMES else "Custom",
        "primary": colors["color_primary"],
        "secondary": colors["color_secondary"],
        "accent": colors["color_accent"],
        "text": colors["color_text"],
        "muted": colors["color_muted"],
        "font_heading": fonts["font_heading"],
        "font_body": fonts["font_body"],
    }

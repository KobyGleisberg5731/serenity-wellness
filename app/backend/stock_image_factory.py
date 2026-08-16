"""Create bundled stock images on disk when missing (local + Docker/VPS)."""
from pathlib import Path

from PIL import Image, ImageDraw

from .stock_images import STOCK_ABOUT, STOCK_GALLERY, STOCK_HERO, STOCK_MASSEUSES, STOCK_DIR

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


def _stock_file(relative_path: str) -> Path:
    return STATIC_DIR / relative_path


def _blend(c1: tuple[int, int, int], c2: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def _draw_gradient(img: Image.Image, top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    width, height = img.size
    draw = ImageDraw.Draw(img)
    for y in range(height):
        color = _blend(top, bottom, y / max(height - 1, 1))
        draw.line([(0, y), (width, y)], fill=color)


def _save_jpeg(path: Path, size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    img = Image.new("RGB", size, top)
    _draw_gradient(img, top, bottom)
    draw = ImageDraw.Draw(img)
    w, h = size
    draw.ellipse((w * 0.08, h * 0.12, w * 0.42, h * 0.55), fill=_blend(top, bottom, 0.35))
    draw.ellipse((w * 0.55, h * 0.45, w * 0.92, h * 0.88), fill=_blend(bottom, top, 0.4))
    img.save(path, "JPEG", quality=90, optimize=True)


def ensure_stock_images() -> None:
    """Generate placeholder spa-style stock photos if files are missing."""
    _save_jpeg(_stock_file(STOCK_HERO), (1600, 1000), (212, 132, 154), (255, 249, 252))
    _save_jpeg(_stock_file(STOCK_ABOUT), (1200, 900), (232, 160, 191), (255, 245, 250))

    gallery_palette = [
        ((212, 132, 154), (255, 249, 252)),
        ((232, 160, 191), (255, 240, 247)),
        ((196, 168, 188), (250, 244, 248)),
        ((210, 145, 165), (255, 236, 244)),
        ((188, 140, 160), (248, 236, 242)),
        ((220, 170, 190), (255, 248, 252)),
        ((200, 150, 170), (252, 242, 247)),
        ((225, 175, 195), (255, 250, 253)),
        ((205, 155, 175), (250, 240, 246)),
        ((215, 165, 185), (255, 245, 250)),
        ((198, 148, 168), (249, 238, 244)),
        ((228, 180, 198), (255, 251, 254)),
    ]
    for i, (filename, _) in enumerate(STOCK_GALLERY):
        top, bottom = gallery_palette[i % len(gallery_palette)]
        _save_jpeg(_stock_file(filename), (1200, 900), top, bottom)

    team_palette = [
        ((205, 150, 170), (240, 210, 220)),
        ((190, 145, 165), (235, 205, 215)),
        ((215, 165, 185), (245, 215, 225)),
    ]
    for i, member in enumerate(STOCK_MASSEUSES):
        top, bottom = team_palette[i % len(team_palette)]
        _save_jpeg(_stock_file(member["image"]), (800, 800), top, bottom)


if __name__ == "__main__":
    ensure_stock_images()
    print(f"Stock images ready under {STATIC_DIR / STOCK_DIR}")

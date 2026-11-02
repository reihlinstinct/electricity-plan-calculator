"""Generate the web share/favicon assets from the synthetic sample data only.

Writes web/og-image.png (1200x630), web/favicon.png (64x64) and
web/apple-touch-icon.png (180x180). Hebrew strings below are pure Hebrew and
stored logically; PIL renders LTR, so they are reversed for drawing.
Requires Pillow (dev tool only; the generated PNGs are committed).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, features

ROOT = Path(__file__).resolve().parents[1]
NOTO = "/usr/share/fonts/truetype/noto"
BG = (11, 18, 32)        # deep navy
BOLT = (251, 191, 36)    # amber
INK = (248, 250, 252)
MUTED = (148, 163, 184)


RAQM = features.check("raqm")


def draw_rtl(d: ImageDraw.ImageDraw, pos, text: str, font, fill) -> None:
    """Right-aligned Hebrew text. With raqm, Pillow does the bidi layout itself
    (direction="rtl"); without it, fall back to a manual single reversal."""
    if RAQM:
        d.text(pos, text, font=font, fill=fill, anchor="ra", direction="rtl", language="he")
    else:
        d.text(pos, text[::-1], font=font, fill=fill, anchor="ra")


def rtl_width(d: ImageDraw.ImageDraw, text: str, font) -> float:
    if RAQM:
        return d.textlength(text, font=font, direction="rtl", language="he")
    return d.textlength(text[::-1], font=font)


def bolt_poly(cx: float, cy: float, h: float) -> list[tuple[float, float]]:
    """Lightning bolt centered on (cx, cy) with total height h."""
    pts = [(0.10, -0.50), (-0.28, 0.08), (-0.02, 0.08), (-0.12, 0.50), (0.30, -0.06), (0.02, -0.06)]
    return [(cx + px * h, cy + py * h) for px, py in pts]


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def synthetic_hourly() -> list[float]:
    """Hourly average kWh from the committed synthetic sample CSV."""
    sys.path.insert(0, str(ROOT / "src"))
    from iec_calc.parser import parse

    totals = [0.0] * 24
    counts = [0] * 24
    for iv in parse(ROOT / "data" / "sample_consumption.csv"):
        totals[iv.start.hour] += iv.kwh
        counts[iv.start.hour] += 1
    return [t / c if c else 0.0 for t, c in zip(totals, counts, strict=False)]


def make_og() -> None:
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), BG)
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # bar strip from synthetic data (decorative, bottom)
    hourly = synthetic_hourly()
    peak = max(hourly) or 1.0
    bw, gap, base_y = 36, 14, h - 30
    x0 = (w - 24 * (bw + gap)) // 2
    for i, v in enumerate(hourly):
        bh = int(95 * v / peak) + 4
        od.rounded_rectangle([x0 + i * (bw + gap), base_y - bh, x0 + i * (bw + gap) + bw, base_y],
                             radius=6, fill=(56, 130, 246, 90))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    d = ImageDraw.Draw(img)
    # bolt badge, left side
    rounded(d, [70, 200, 250, 380], 36, BOLT)
    d.polygon(bolt_poly(160, 290, 130), fill=BG)

    # Noto Sans Hebrew covers Hebrew letters, "-" and gershayim only: keep the
    # strings pure Hebrew (digits and Latin punctuation render as boxes).
    right = w - 70
    left_limit = 290  # clear of the bolt badge
    size = 96
    while size > 40:
        title_f = ImageFont.truetype(f"{NOTO}/NotoSansHebrew-Black.ttf", size)
        if right - rtl_width(d, "מחשבון חיסכון בחשמל", title_f) >= left_limit:
            break
        size -= 4
    sub_f = ImageFont.truetype(f"{NOTO}/NotoSansHebrew-Regular.ttf", 44)
    foot_f = ImageFont.truetype(f"{NOTO}/NotoSansHebrew-Regular.ttf", 34)
    draw_rtl(d, (right, 190), "מחשבון חיסכון בחשמל", title_f, INK)
    draw_rtl(d, (right, 330), "איזה מסלול הכי משתלם לכם", sub_f, BOLT)
    draw_rtl(d, (right, 390), "מהנתונים שלכם מחברת החשמל - בדפדפן בלי שרת", foot_f, MUTED)
    img.save(ROOT / "web" / "og-image.png", optimize=True)


def make_icon(size: int, path: str) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rounded(d, [0, 0, size - 1, size - 1], int(size * 0.22), BG + (255,) if len(BG) == 3 else BG)
    d.polygon(bolt_poly(size / 2, size / 2, size * 0.62), fill=BOLT)
    img.save(ROOT / "web" / path, optimize=True)


if __name__ == "__main__":
    make_og()
    make_icon(64, "favicon.png")
    make_icon(180, "apple-touch-icon.png")
    print("wrote web/og-image.png, web/favicon.png, web/apple-touch-icon.png")

"""Shared dark-glass artwork renderer for the radio collections.

Produces dark, legible, station-specific tiles. Does not copy official marks.
The 36 existing hand-finished U.S. station covers are never modified here.
"""
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

SIZE = 512
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

PALETTES = (
    ((7, 15, 38), (23, 28, 71), (76, 112, 221), (213, 49, 112)),
    ((5, 24, 44), (21, 44, 74), (35, 165, 184), (114, 72, 165)),
    ((14, 16, 42), (43, 25, 80), (112, 86, 206), (230, 62, 121)),
    ((7, 18, 47), (37, 25, 62), (63, 114, 191), (164, 63, 150)),
    ((7, 28, 45), (23, 47, 73), (45, 141, 165), (211, 74, 129)),
)


def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)
    except OSError:
        return ImageFont.load_default()


def mix(a, b, portion):
    return tuple(round(x + (y - x) * portion) for x, y in zip(a, b))


def width(draw, text, face):
    return draw.textbbox((0, 0), text, font=face)[2]


def line_breaks(draw, name, face, maximum=376):
    words = name.replace("\r", " ").replace("\n", " ").split()
    lines = []
    for word in words:
        if width(draw, word, face) > maximum:
            return None
        candidate = (lines[-1] + " " + word) if lines else word
        if lines and width(draw, candidate, face) <= maximum:
            lines[-1] = candidate
        else:
            lines.append(word)
    return lines


def fitted_title(draw, title):
    title = str(title).strip() or "Live Radio"
    for size in range(66, 25, -2):
        face = font(size)
        lines = line_breaks(draw, title, face)
        if lines and len(lines) <= 3:
            return lines, face, size
    # Even extremely long names must never overflow onto the glass edge.
    face = font(25)
    truncated = title
    while truncated and width(draw, truncated + "…", face) > 368:
        truncated = truncated[:-1]
    return [truncated.rstrip() + "…"], face, 25


def fitted_subtitle(draw, subtitle):
    subtitle = str(subtitle or "Live Radio").strip()
    face = font(21, bold=False)
    while subtitle and width(draw, subtitle, face) > 362:
        subtitle = subtitle[:-1]
    return (subtitle.rstrip() + "…") if len(subtitle) < len(str(subtitle or "")) else subtitle, face


def cover(station):
    """A 512px square deep-blue glass card with luminous text and accent orbs."""
    digest = hashlib.sha256(station["id"].encode("utf-8")).digest()
    start, end, accent, secondary = PALETTES[digest[0] % len(PALETTES)]

    base = Image.new("RGB", (SIZE, SIZE), start)
    bg = ImageDraw.Draw(base)
    for y in range(SIZE):
        fraction = (y / (SIZE - 1)) ** 1.05
        bg.line((0, y, SIZE, y), fill=mix(start, end, fraction), width=1)

    # Layered diffused glows are behind the translucent dark glass, never above it.
    glows = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glows, "RGBA")
    gd.ellipse((270, -290, 810, 240), fill=(*accent, 145))
    gd.ellipse((-290, 320, 265, 790), fill=(*secondary, 147))
    gd.ellipse((-110, -90, 250, 275), fill=(*accent, 65))
    glows = glows.filter(ImageFilter.GaussianBlur(64))
    image = Image.alpha_composite(base.convert("RGBA"), glows)

    # Dark, high-contrast glass: explicit alpha_composite avoids pale opaque fills.
    shadow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow, "RGBA")
    sd.rounded_rectangle((34, 67, 478, 459), radius=64, fill=(0, 3, 16, 115))
    image = Image.alpha_composite(image, shadow.filter(ImageFilter.GaussianBlur(19)))
    glass = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(glass, "RGBA")
    d.rounded_rectangle((32, 61, 480, 453), radius=63,
                        fill=(6, 16, 43, 161),
                        outline=(211, 233, 255, 206), width=3)
    d.arc((39, 65, 472, 445), 195, 318, fill=(255, 255, 255, 110), width=2)
    d.rounded_rectangle((43, 72, 469, 441), radius=56,
                        outline=(186, 214, 255, 39), width=1)
    image = Image.alpha_composite(image, glass)

    # All text lives on the dark surface. No pastel panel behind white labels.
    draw = ImageDraw.Draw(image, "RGBA")
    collection = station.get("language") or "World"
    tag = str(collection).upper() + "  /  LIVE RADIO"
    draw.text((256, 123), tag, font=font(17), anchor="mm",
              fill=(225, 236, 255, 220))
    draw.line((199, 144, 313, 144), fill=(210, 229, 255, 145), width=2)

    title = station.get("artwork_title") or station["name"]
    lines, face, font_size = fitted_title(draw, title)
    line_height = round(font_size * 1.18)
    middle = 238
    top = middle - ((len(lines) - 1) * line_height / 2)
    for i, line in enumerate(lines):
        draw.text((256, round(top + i * line_height)), line,
                  font=face, anchor="mm", fill=(255, 255, 255, 255))

    subtitle = station.get("genre", "Live Radio")
    subtitle_face = font(20, bold=False)
    while subtitle and width(draw, subtitle, subtitle_face) > 355:
        subtitle = subtitle[:-1]
    draw.text((256, 341), subtitle.rstrip(), anchor="mm",
              font=subtitle_face, fill=(224, 236, 255, 242))
    code = str(station.get("country_code", "")).upper() or "RADIO"
    draw.line((184, 396, 227, 396), fill=(221, 234, 255, 175), width=2)
    draw.text((256, 396), code, font=font(21), anchor="mm",
              fill=(237, 243, 255, 245))
    draw.line((285, 396, 328, 396), fill=(221, 234, 255, 175), width=2)
    return image.convert("RGB")

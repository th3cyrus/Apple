#!/usr/bin/env python3
"""Build reproducible, project-style World Radio Select cover images.

Generated artwork is station-specific but does not imitate broadcaster trademarks.
Existing images are preserved so manually optimized art is never overwritten.
"""
import argparse
import hashlib
from pathlib import Path
import json
import math

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
SIZE = 512
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REGULAR_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
PREFIX = "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/logos/"


def font(size, bold=True):
    try:
        return ImageFont.truetype(FONT if bold else REGULAR_FONT, size)
    except OSError:
        return ImageFont.load_default()


def mix(a, b, fraction):
    return tuple(round(x + (y-x) * fraction) for x, y in zip(a, b))


def wrapped_title(name, max_width=380):
    words = name.split()
    for size in range(48, 23, -2):
        face = font(size)
        lines = []
        for word in words:
            if not lines:
                lines.append(word)
            elif ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox(
                    (0, 0), lines[-1] + " " + word, font=face)[2] <= max_width:
                lines[-1] += " " + word
            else:
                lines.append(word)
        if len(lines) <= 3 and all(
                ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox(
                    (0, 0), line, font=face)[2] <= max_width for line in lines):
            return lines, face, size
    # Fallback is deliberately legible, never an overflow out of the glass card.
    face = font(23)
    return [name[:28], name[28:55]], face, 23


def cover(station):
    """Render a square RGB station cover with deterministic soft-glow styling."""
    digest = hashlib.sha256(station["id"].encode("utf-8")).digest()
    themes = [
        ((8, 23, 52), (43, 20, 73), (52, 134, 222)),
        ((12, 29, 49), (30, 23, 70), (94, 102, 211)),
        ((12, 22, 37), (62, 23, 65), (160, 76, 156)),
        ((8, 34, 48), (24, 45, 70), (31, 161, 166)),
        ((25, 23, 49), (55, 28, 57), (155, 96, 134)),
        ((13, 28, 49), (44, 31, 68), (102, 111, 178)),
    ]
    top, bottom, accent = themes[digest[0] % len(themes)]
    base = Image.new("RGB", (SIZE, SIZE), top)
    brush = ImageDraw.Draw(base)
    for y in range(SIZE):
        ratio = y / (SIZE - 1)
        c = mix(top, bottom, ratio)
        brush.line([(0, y), (SIZE, y)], fill=c)
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    ax = 80 + digest[1] % 130
    ay = 65 + digest[2] % 90
    g.ellipse((ax-160, ay-150, ax+190, ay+185), fill=(*accent, 138))
    g.ellipse((210, 250, 620, 640), fill=(128, 50, 124, 75))
    glow = glow.filter(ImageFilter.GaussianBlur(70))
    image = Image.alpha_composite(base.convert("RGBA"), glow)
    d = ImageDraw.Draw(image, "RGBA")
    d.rounded_rectangle((38, 122, 474, 393), radius=44,
                        fill=(236, 243, 255, 31), outline=(255, 255, 255, 110),
                        width=2)
    d.rounded_rectangle((51, 136, 461, 379), radius=36,
                        outline=(255, 255, 255, 42), width=1)

    d.text((256, 80), "WORLD  /  LIVE RADIO", anchor="mm",
           font=font(19), fill=(226, 238, 247, 228))
    d.line((183, 101, 329, 101), fill=(224, 236, 255, 120), width=2)

    lines, face, size = wrapped_title(station["name"])
    height = size * 1.20
    top_text = 258 - (len(lines) - 1) * height / 2
    for number, line in enumerate(lines):
        d.text((256, round(top_text + number*height)), line, font=face,
               anchor="mm", fill=(255, 255, 255, 255),
               stroke_width=0)
    # Country is a visual reference, not a separate station trademark.
    country = station["country_code"].upper()
    d.text((256, 347), country, anchor="mm", font=font(22),
           fill=(226, 238, 255, 242))
    d.text((256, 442), "APPLE RADIO  •  WORLD SELECT", anchor="mm",
           font=font(15, bold=False), fill=(202, 216, 232, 230))
    return image.convert("RGB")


def targets(stations, root=WORLD):
    for s in stations:
        if s.get("logo") == PREFIX + s["id"] + ".png":
            yield s, Path(root) / "logos" / (s["id"] + ".png")


def generate(stations, root=WORLD, *, force=False):
    made = 0
    for station, path in targets(stations, root):
        if path.is_file() and not force:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name("." + path.name + ".tmp")
        try:
            cover(station).save(temporary, format="PNG", optimize=True)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
        made += 1
    print(f"World radio covers generated: {made}", flush=True)
    return made


def verify(stations, root=WORLD):
    count = 0
    for station, path in targets(stations, root):
        if not path.is_file():
            raise ValueError(f"Missing station artwork: {path}")
        with Image.open(path) as image:
            if image.format != "PNG" or image.size != (SIZE, SIZE):
                raise ValueError(f"Invalid station artwork: {path}")
            image.verify()
        count += 1
    if count < 60:
        raise ValueError(f"Only {count} world-station artwork URLs were configured")
    print(f"Verified {count} world station covers", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Overwrite generated tiles")
    parser.add_argument("--verify", action="store_true", help="Validate cover PNG files")
    parser.add_argument("--directory", type=Path, default=WORLD)
    args = parser.parse_args()
    stations = json.loads((WORLD / "stations.json").read_text(encoding="utf-8"))
    if args.verify:
        verify(stations, args.directory)
    else:
        generate(stations, args.directory, force=args.force)
        verify(stations, args.directory)


if __name__ == "__main__":
    main()

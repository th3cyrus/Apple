"""Station-specific cover rendering with high-quality 1254px JPEG outputs.

Vector templates are rendered to 1254x1254 JPEG cover files; no SVG
assets are published in the repository.
"""
import html
from itertools import combinations
from pathlib import Path
import re
import xml.etree.ElementTree as ET

SIZE = 1254
VIEWBOX = "0 0 512 512"
SVG_NAMESPACE = "http://www.w3.org/2000/svg"

PALETTES = (
    ("#050e2a", "#233e88", "#2a89ff", "#ee3c94"),
    ("#07142b", "#144d70", "#31c6dc", "#a956c7"),
    ("#100e2a", "#4a276d", "#a388e4", "#f44885"),
    ("#061429", "#2c3162", "#6aa9f7", "#d95cb2"),
    ("#081528", "#135c64", "#42b4af", "#e55c94"),
)


def _palette(identifier):
    number = 2166136261
    for char in str(identifier):
        number = ((number ^ ord(char)) * 16777619) & 0xffffffff
    return PALETTES[number % len(PALETTES)]


def _width(text, size):
    """Conservative width estimate for the normal Arial/Helvetica font stack."""
    total = 0.0
    for char in str(text):
        if char in "W@%M":
            total += .92
        elif char in "ilI1!'.,:|":
            total += .30
        elif char == " ":
            total += .32
        elif char in "mwbQO":
            total += .73
        elif "A" <= char <= "Z" or "0" <= char <= "9":
            total += .66
        else:
            total += .57
    return total * size * 1.06


# Reserve genuinely separate areas for the header, title and subtitle.
# Measured in the 512-unit SVG viewBox, not in output image pixels.
TITLE_TOP = 172
TITLE_BOTTOM = 324
TITLE_MAX_WIDTH = 346
TITLE_ASCENT = 0.86
TITLE_DESCENT = 0.21
TITLE_LINE_SPACING = 1.14


def fitted_title(text):
    """Choose the largest readable, balanced 1–3 line arrangement that fits.

    Enforce *vertical* limits while choosing font sizes, not afterwards: a title
    that fits horizontally can still overlap the fixed LIVE RADIO heading.
    """
    words = str(text).split() or ["Live", "Radio"]
    available_height = TITLE_BOTTOM - TITLE_TOP
    for size in range(70, 17, -1):
        choices = []
        for count in range(1, min(3, len(words)) + 1):
            advance = round(size * TITLE_LINE_SPACING)
            visible_height = size * (TITLE_ASCENT + TITLE_DESCENT)
            block_height = visible_height + (count - 1) * advance
            if block_height > available_height:
                continue
            for breaks in combinations(range(1, len(words)), count - 1):
                points = (0, *breaks, len(words))
                lines = [" ".join(words[points[i]:points[i + 1]])
                         for i in range(count)]
                widths = [_width(line, size) for line in lines]
                if max(widths) <= TITLE_MAX_WIDTH:
                    # Favor shorter/balanced lines within the maximum font size.
                    imbalance = max(widths) - min(widths)
                    choices.append((count, imbalance, lines))
        if choices:
            count, _, lines = min(choices, key=lambda item: (item[0], item[1]))
            return lines, size

    # Exceptionally long unbroken titles still fit in the title area, rather
    # than escaping the frame or sitting over the header.
    full = " ".join(words)
    size = min(17, max(6, int(TITLE_MAX_WIDTH / max(_width(full, 1), 0.01))))
    while size > 6 and _width(full, size) > TITLE_MAX_WIDTH:
        size -= 1
    return [full], size


def title_layout(text):
    """Return title lines, font size, first baseline and line advance."""
    lines, size = fitted_title(text)
    advance = round(size * TITLE_LINE_SPACING)
    height = size * (TITLE_ASCENT + TITLE_DESCENT) + (len(lines) - 1) * advance
    first_baseline = (TITLE_TOP + (TITLE_BOTTOM - TITLE_TOP - height) / 2
                      + size * TITLE_ASCENT)
    return lines, size, first_baseline, advance


def _subtitle(text):
    result = str(text or "Live Radio").strip() or "Live Radio"
    while _width(result, 21) > 375 and len(result) > 4:
        result = result[:-2].rstrip("…") + "…"
    return result


def cover_svg(station):
    """Render an accessible, high-resolution, font-responsive square SVG."""
    identifier = str(station["id"])
    title = str(station.get("artwork_title") or station.get("name") or "Live Radio")
    country = str(station.get("country_code") or "US").upper()
    description = _subtitle(station.get("genre") or station.get("description") or "Live Radio")
    label = str(station.get("language") or station.get("collection") or "World")
    background, intermediate, blue, pink = _palette(identifier)
    lines, show_font, start_y, line_height = title_layout(title)

    def escape(value):
        return html.escape(str(value).replace("\r", " ").replace("\n", " "), quote=True)

    title_markup = "\n".join(
        f' <text x="256" y="{round(start_y + n * line_height)}" '
        f'text-anchor="middle" font-family="Arial,Helvetica,sans-serif" '
        f'font-size="{show_font}" font-weight="750" letter-spacing="-0.7" '
        f'fill="#ffffff">{escape(line)}</text>'
        for n, line in enumerate(lines)
    )
    return f'''<svg xmlns="{SVG_NAMESPACE}" width="{SIZE}" height="{SIZE}" viewBox="{VIEWBOX}" role="img" aria-label="{escape(title)} radio cover">
 <defs>
  <linearGradient id="background" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{background}"/><stop offset=".55" stop-color="{intermediate}"/><stop offset="1" stop-color="{blue}"/></linearGradient>
  <radialGradient id="leftGlow" cx="0" cy="1" r=".82"><stop offset="0" stop-color="{pink}" stop-opacity=".78"/><stop offset=".74" stop-color="{pink}" stop-opacity=".11"/><stop offset="1" stop-color="{pink}" stop-opacity="0"/></radialGradient>
  <radialGradient id="rightGlow" cx="1" cy="0" r=".91"><stop offset="0" stop-color="{blue}" stop-opacity=".64"/><stop offset="1" stop-color="{blue}" stop-opacity="0"/></radialGradient>
  <linearGradient id="rim" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="{pink}"/><stop offset=".45" stop-color="#a5b7fc"/><stop offset="1" stop-color="#e6f4ff"/></linearGradient>
  <linearGradient id="pane" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#09142e" stop-opacity=".94"/><stop offset="1" stop-color="#091b40" stop-opacity=".92"/></linearGradient>
 </defs>
 <rect width="512" height="512" fill="url(#background)"/>
 <rect width="512" height="512" fill="url(#leftGlow)"/>
 <rect width="512" height="512" fill="url(#rightGlow)"/>
 <rect x="34" y="43" width="444" height="430" rx="61" fill="#040819" opacity=".34"/>
 <rect x="39" y="39" width="434" height="434" rx="56" fill="url(#pane)" stroke="url(#rim)" stroke-width="2.5"/>
 <rect x="49" y="49" width="414" height="414" rx="48" fill="none" stroke="#d0deff" stroke-opacity=".12"/>
 <text x="256" y="126" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="17" font-weight="700" letter-spacing="2.0" fill="#ebf2ff">{escape(label.upper())} · LIVE RADIO</text>
{title_markup}
 <text x="256" y="366" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="21" font-weight="400" fill="#dce6f9">{escape(description)}</text>
 <path d="M194 417H230 M282 417H318" fill="none" stroke="#cedcf9" stroke-width="2" stroke-linecap="round"/>
 <text x="256" y="425" text-anchor="middle" font-family="Arial,Helvetica,sans-serif" font-size="24" font-weight="700" letter-spacing="1" fill="#f5f8ff">{escape(country)}</text>
</svg>
'''


def verify_svg(path):
    """Reject invalid, externally referenced or non-vector station art."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing radio artwork: " + str(path))
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ValueError("Invalid SVG radio artwork: " + str(path)) from exc
    if (root.tag != "{" + SVG_NAMESPACE + "}svg"
            or root.get("viewBox") != VIEWBOX
            or root.get("width") != str(SIZE)
            or root.get("height") != str(SIZE)):
        raise ValueError("Invalid SVG geometry: " + str(path))
    if not any(node.tag.endswith("}text") for node in root.iter()):
        raise ValueError("SVG missing station title: " + str(path))
    for node in root.iter():
        tag = node.tag.rsplit("}", 1)[-1].lower()
        if tag in {"script", "foreignobject", "image"}:
            raise ValueError("Non-vector or unsafe SVG content: " + str(path))
        for key, value in node.attrib.items():
            if key.rsplit("}", 1)[-1].lower() in {"href", "onload", "onclick"}:
                raise ValueError("External SVG reference or script: " + str(path))
            if "url(http" in value.lower() or "javascript:" in value.lower():
                raise ValueError("External SVG resource: " + str(path))
    return True



def cover_jpg(station):
    """Render a native RGB JPEG from a station-specific internal vector template."""
    from io import BytesIO
    import cairosvg
    from PIL import Image

    png = cairosvg.svg2png(bytestring=cover_svg(station).encode("utf-8"),
                           output_width=SIZE, output_height=SIZE)
    with Image.open(BytesIO(png)) as src:
        rgba = src.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        data = BytesIO()
        canvas.save(data, format="JPEG", quality=90, subsampling=0, optimize=True)
        return data.getvalue()


def verify_jpg(path):
    """Validate the real JPEG encoding, full dimensions and readable contents."""
    from PIL import Image
    if not Path(path).is_file():
        raise ValueError("Missing radio artwork: " + str(path))
    try:
        with Image.open(path) as image:
            if image.format != "JPEG" or image.size != (SIZE, SIZE):
                raise ValueError("Wrong JPEG cover dimensions or format")
            image.verify()
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid JPEG cover: " + str(path)) from exc
    return True

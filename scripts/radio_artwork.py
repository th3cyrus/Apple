"""Dependency-free, scalable, station-specific SVG radio cover artwork.

All imagery is native vector (gradients, paths and text), not a PNG wrapped
in SVG. Legacy PNG originals remain as optional archived fallbacks.
"""
import html
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


def fitted_title(text):
    words = str(text).strip().split() or ["Live", "Radio"]
    for size in range(72, 25, -2):
        lines = []
        for word in words:
            if _width(word, size) > 388:
                lines = []
                break
            if lines and _width(lines[-1] + " " + word, size) <= 382:
                lines[-1] += " " + word
            else:
                lines.append(word)
        if 1 <= len(lines) <= 3:
            return lines, size
    whole = " ".join(words)
    return [whole], max(17, min(26, int(380 / max(_width(whole, 1), 1))))


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
    lines, fontsize = fitted_title(title)
    line_height = round(fontsize * 1.16)
    start_y = 246 - ((len(lines) - 1) * line_height) / 2
    show_font = fontsize - 2 if len(lines) == 3 and fontsize >= 50 else fontsize

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

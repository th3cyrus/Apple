#!/usr/bin/env python3
"""One-time conversion of every radio SVG cover to a real 1254px JPEG."""
from io import BytesIO
import json
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ("arabic", "english", "french", "german", "kurdish",
             "persian", "russian", "spanish", "turkish")
SIZE = 1254


def edit(relative, transform):
    path = ROOT / relative
    old = path.read_text(encoding="utf-8")
    new = transform(old)
    if new == old:
        raise RuntimeError("No transformation applied to " + relative)
    path.write_text(new, encoding="utf-8")


def replace_checked(text, old, new):
    if old not in text:
        raise RuntimeError("Unexpected input (missing): " + old)
    return text.replace(old, new)


def convert_all_images():
    originals = sorted(ROOT.rglob("*.svg"))
    if len(originals) != 211:
        raise RuntimeError(f"Expected 211 SVG covers, found {len(originals)}")
    images = []
    for source in originals:
        if "Covers" not in source.parts and "previews" not in source.parts:
            raise RuntimeError(f"SVG outside artwork folders: {source}")
        jpg = source.with_suffix(".jpg")
        png = cairosvg.svg2png(bytestring=source.read_bytes(),
                               output_width=SIZE, output_height=SIZE)
        with Image.open(BytesIO(png)) as src:
            rgba = src.convert("RGBA")
            canvas = Image.new("RGB", rgba.size, (255, 255, 255))
            canvas.paste(rgba, mask=rgba.getchannel("A"))
            canvas.save(jpg, "JPEG", quality=90, subsampling=0, optimize=True)
        with Image.open(jpg) as check:
            if check.format != "JPEG" or check.size != (SIZE, SIZE):
                raise RuntimeError("Invalid JPEG " + str(jpg))
            check.verify()
        images.append((source, jpg))
    for source, jpg in images:
        with Image.open(jpg) as img:
            img.verify()
        source.unlink()
    print(f"Created {len(images)} verified {SIZE}x{SIZE} JPEG covers")


def convert_catalogs_and_playlists():
    catalogs = [ROOT/"stations.json", ROOT/"world-radio/stations.json"]
    catalogs += [ROOT/"world-radio"/lang/"stations.json" for lang in LANGUAGES]
    playlists = [ROOT/"radio.m3u", ROOT/"world-radio/radio.m3u"]
    playlists += [ROOT/"world-radio"/lang/"radio.m3u" for lang in LANGUAGES]
    playlists += sorted((ROOT/"us-directory").glob("*.m3u"))
    for path in catalogs + playlists:
        old = path.read_text(encoding="utf-8")
        updated = old.replace(".svg", ".jpg")
        if updated == old:
            raise RuntimeError("Expected SVG cover links in " + str(path))
        if path in catalogs:
            stations = json.loads(updated)
            for item in stations:
                logo = item.get("logo", "")
                if not logo.endswith(".jpg"):
                    raise RuntimeError("Non-JPEG cover " + item["id"])
                local = ROOT / (logo if logo.startswith("Covers/")
                                else logo.split("/main/", 1)[-1])
                with Image.open(local) as image:
                    if image.format != "JPEG":
                        raise RuntimeError("Not a JPEG " + str(local))
        elif not updated.startswith("#EXTM3U\n"):
            raise RuntimeError("Invalid playlist " + str(path))
        path.write_text(updated, encoding="utf-8")
    print(f"Converted {len(catalogs)} catalogs and {len(playlists)} playlists")


def convert_python():
    for path in ("scripts/catalog.py", "scripts/check_language_radio.py",
                 "scripts/build_us_directory.py",
                 "tests/test_maintenance.py", "tests/test_audit_fixes.py"):
        edit(path, lambda s: s.replace(".svg", ".jpg"))
    def generator(s):
        s = replace_checked(s, "from radio_artwork import cover_svg, verify_svg",
                            "from radio_artwork import cover_jpg, verify_jpg")
        s = replace_checked(s,
                            'temporary.write_text(cover_svg(station), encoding="utf-8")',
                            'temporary.write_bytes(cover_jpg(station))')
        return s.replace("verify_svg(", "verify_jpg(").replace(".svg", ".jpg") \
                .replace("SVG covers", "JPEG covers").replace("SVG cover", "JPEG cover") \
                .replace("SVG files", "JPEG files")
    edit("scripts/generate_world_covers.py", generator)
    def curated(s):
        s = replace_checked(s, "from radio_artwork import cover_svg, verify_svg",
                            "from radio_artwork import cover_jpg, verify_jpg")
        s = replace_checked(s, "return cover_svg({**station,",
                            "return cover_jpg({**station,")
        s = replace_checked(s,
                            "temporary.write_text(artwork_placeholder(station), encoding='utf-8')",
                            "temporary.write_bytes(artwork_placeholder(station))")
        return s.replace("verify_svg(", "verify_jpg(").replace(".svg", ".jpg") \
                .replace("Generate self-hosted SVG", "Generate self-hosted JPG")
    edit("scripts/update.py", curated)
    edit("scripts/validate.py", lambda s: s.replace("verify_svg", "verify_jpg"))
    def reliability(s):
        s = replace_checked(s, "from radio_artwork import cover_svg, verify_svg",
                            "from radio_artwork import cover_jpg, verify_jpg")
        s = replace_checked(s,
                            '(self.root / "Covers" / "test-station.svg").write_text(',
                            '(self.root / "Covers" / "test-station.jpg").write_bytes(')
        s = replace_checked(s,
                            'cover_svg({"id": "test-station", "name": "Test Station"}), encoding="utf-8")',
                            'cover_jpg({"id": "test-station", "name": "Test Station"}))')
        return s.replace("verify_svg(", "verify_jpg(").replace(".svg", ".jpg")
    edit("tests/test_reliability.py", reliability)
    def visual_tests(s):
        s = s.replace("from radio_artwork import cover_svg, fitted_title, verify_svg",
                      "from radio_artwork import cover_svg, fitted_title, verify_svg, verify_jpg")
        s = s.replace('covers.PREFIX + "fr-fip.svg"', 'covers.PREFIX + "fr-fip.jpg"')
        s = s.replace('covers.PREFIX + "fr-fip-jazz.svg"', 'covers.PREFIX + "fr-fip-jazz.jpg"')
        s = s.replace('root / "Covers" / "fr-fip.svg"', 'root / "Covers" / "fr-fip.jpg"')
        s = s.replace('root / "Covers" / "fr-fip-jazz.svg"', 'root / "Covers" / "fr-fip-jazz.jpg"')
        s = s.replace('svg = Path(temp) / "ir-radio-nic.svg"',
                      'svg = Path(temp) / "ir-radio-nic.jpg"')
        s = s.replace("self.assertTrue(verify_svg(a))", "self.assertTrue(verify_jpg(a))")
        s = s.replace("self.assertTrue(verify_svg(b))", "self.assertTrue(verify_jpg(b))")
        s = s.replace("self.assertTrue(verify_svg(svg))", "self.assertTrue(verify_jpg(svg))")
        return s.replace("a.read_text(), b.read_text()", "a.read_bytes(), b.read_bytes()")
    edit("tests/test_world_covers.py", visual_tests)
    edit("tests/test_audit_fixes.py",
         lambda s: s.replace("patch.object(covers, 'verify_svg')",
                             "patch.object(covers, 'verify_jpg')"))

    source = ROOT/"scripts/radio_artwork.py"
    content = source.read_text(encoding="utf-8")
    content += '''


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
    try:
        with Image.open(path) as image:
            if image.format != "JPEG" or image.size != (SIZE, SIZE):
                raise ValueError("Wrong JPEG cover dimensions or format")
            image.verify()
    except (OSError, ValueError) as exc:
        raise ValueError("Invalid JPEG cover: " + str(path)) from exc
    return True
'''
    content = content.replace(
        "All artwork is native vector (gradients, paths and text), with no embedded\nraster files. SVG is the sole published artwork format.",
        "Vector templates are rendered to 1254x1254 JPEG cover files; no SVG\nassets are published in the repository.")
    source.write_text(content, encoding="utf-8")
    print("Updated automatic JPEG generators and verification tests")


def convert_documentation():
    license_path = ROOT/"ARTWORK_LICENSE.md"
    notice = license_path.read_text(encoding="utf-8")
    notice = notice.replace("SVG cover artwork", "JPG cover artwork")
    notice = notice.replace(
        "All PNG copies were deleted; the repository publishes only scalable SVG covers.",
        "The repository publishes 1254x1254 JPG covers; no PNG or SVG artwork files.")
    notice = notice.replace(
        "Earlier designs used AI-assisted artwork; the current SVG covers are code-generated vector treatments using text, paths and gradients. No raster images are embedded or distributed in the project.",
        "Earlier designs used AI assistance; current JPG images are rasterized from code-generated layouts with text, paths and gradients. Only finished JPEG files are published in the Covers folders.")
    license_path.write_text(notice, encoding="utf-8")

    for path in ("README.md", "world-radio/README.md", "us-directory/README.md",
                 "docs/MAINTENANCE.md", "docs/REPOSITORY_SETTINGS.md"):
        file = ROOT/path
        s = file.read_text(encoding="utf-8")
        s = s.replace("SVG-only", "JPG-only").replace("SVG vector", "JPG")
        s = s.replace("SVG", "JPG").replace(".svg", ".jpg")
        s = s.replace("scalable 1254×1254", "high-resolution 1254×1254")
        s = s.replace("scalable 1254-pixel", "high-resolution 1254-pixel")
        s = s.replace("scalable", "high-resolution")
        s = s.replace("vector-cover", "JPG-cover").replace("vector artwork", "JPG artwork")
        s = s.replace("vector covers", "JPG covers")
        s = s.replace("SVG is the only cover format in the repository.",
                      "JPG is the only distributed cover format.")
        file.write_text(s, encoding="utf-8")

    review = ROOT/"docs/RELIABILITY_REVIEW.md"
    review.write_text(
        review.read_text(encoding="utf-8") +
        "\n## 2026-11-10 JPG migration\n\n"
        "Earlier SVG references in dated historical notes describe the previous format. "
        "All 211 SVG assets were converted to real 1254×1254 JPEG images; "
        "catalogs, M3U playlists, generators, tests and current documentation use JPG. "
        "The internal drawing template still uses SVG markup solely to render JPEGs. "
        "No station audio streams were changed.\n", encoding="utf-8")

    dependencies = ROOT/"requirements.txt"
    dependencies.write_text(
        dependencies.read_text(encoding="utf-8") +
        "\n# Vector rendering is internal; only JPEG artwork is published.\n"
        "CairoSVG==2.8.2\n", encoding="utf-8")

    workflow = ROOT/".github/workflows/world-artwork.yml"
    text = workflow.read_text(encoding="utf-8")
    text = text.replace("*.svg", "*.jpg").replace(
        "Generate missing vector radio station covers",
        "Generate missing JPEG radio station covers")
    workflow.write_text(text, encoding="utf-8")


def main():
    if not list(ROOT.rglob("*.svg")):
        print("Already migrated: no SVG files remain")
        return
    convert_all_images()
    convert_catalogs_and_playlists()
    convert_python()
    convert_documentation()
    if list(ROOT.rglob("*.svg")):
        raise RuntimeError("Unexpected SVG artwork remains")
    print("Migration complete: JPEG artwork only")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate and verify all World, language and U.S. directory JPEG covers.

Deterministic vector layouts are rendered to JPEG using CairoSVG and Pillow.
All original PNG assets have been removed; only JPEG files are generated.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from radio_artwork import cover_jpg, verify_jpg

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
PREFIX = "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/Covers/"
LANGUAGE_PREFIX = "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/"


def targets(stations, root=WORLD):
    for station in stations:
        if urlsplit(station.get("logo", "")).path.endswith(
                "/world-radio/Covers/" + station["id"] + ".jpg"):
            yield station, Path(root) / "Covers" / (station["id"] + ".jpg")


def language_catalogs(root=WORLD):
    root = Path(root)
    for path in sorted(root.glob("*/stations.json")):
        yield path.parent.name, json.loads(path.read_text(encoding="utf-8"))


def language_targets(root=WORLD):
    for language, stations in language_catalogs(root):
        for station in stations:
            expected = f"/world-radio/{language}/Covers/{station['id']}.jpg"
            if not urlsplit(station.get("logo", "")).path.endswith(expected):
                raise ValueError("Language artwork URL mismatch: " + station["id"])
            yield station, Path(root) / language / "Covers" / (station["id"] + ".jpg")


def write_cover(station, path, force=False):
    path = Path(path)
    if path.is_file() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    try:
        temporary.write_bytes(cover_jpg(station))
        verify_jpg(temporary)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def generate(stations, root=WORLD, *, force=False):
    made = sum(write_cover(station, path, force) for station, path in targets(stations, root))
    print(f"World radio JPEG covers generated: {made}", flush=True)
    return made


def generate_languages(root=WORLD, *, force=False):
    made = sum(write_cover(station, path, force) for station, path in language_targets(root))
    print(f"Language radio JPEG covers generated: {made}", flush=True)
    return made


def verify(stations, root=WORLD):
    total = 0
    for _, path in targets(stations, root):
        verify_jpg(path)
        total += 1
    if total < 60:
        raise ValueError("Incomplete World Radio artwork set")
    print(f"Verified {total} world JPEG covers", flush=True)


def verify_languages(root=WORLD):
    counts = {}
    for station, path in language_targets(root):
        verify_jpg(path)
        counts[station["language"]] = counts.get(station["language"], 0) + 1
    if len(counts) < 5:
        raise ValueError("Too few language artwork collections")
    print("Verified language radio JPEG covers:", counts, flush=True)


DIRECTORY_GENRES = (
    "Hip-Hop & R&B", "Rock & Alternative", "Country",
    "Jazz & Blues", "Classical", "News & Talk",
    "Electronic & Dance", "Latin & Spanish",
    "Christian & Gospel", "Pop & Hits", "Other U.S. Radio",
)


def directory_genre_covers(root=ROOT, *, force=False):
    directory = Path(root) / "us-directory" / "Covers"
    for genre in DIRECTORY_GENRES:
        slug = "-".join(re.findall(r"[a-z0-9]+", genre.lower()))
        filename = directory / (slug + ".jpg")
        write_cover({"id": "us-directory-" + slug, "name": genre,
                     "country_code": "US", "genre": "USA RADIO DIRECTORY",
                     "language": "USA"}, filename, force=force)
        verify_jpg(filename)


def directory_cover(root=ROOT, *, force=False):
    filename = Path(root) / "us-directory" / "Covers" / "directory-cover.jpg"
    if not filename.is_file() or force:
        write_cover({"id": "us-directory-cover", "name": "USA Radio Directory",
                     "country_code": "US", "genre": "American Radio",
                     "language": "USA"}, filename, force=force)
    verify_jpg(filename)
    return filename


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restyle", action="store_true",
                        help="Rebuild existing World/Language JPEG covers")
    parser.add_argument("--force", action="store_true", help="Alias for --restyle")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--directory", type=Path, default=WORLD)
    args = parser.parse_args()
    stations = json.loads((args.directory / "stations.json").read_text(encoding="utf-8"))
    if not args.verify:
        rebuild = args.restyle or args.force
        generate(stations, args.directory, force=rebuild)
        generate_languages(args.directory, force=rebuild)
        directory_cover(root=args.directory.parent, force=rebuild)
        directory_genre_covers(root=args.directory.parent, force=rebuild)
    verify(stations, args.directory)
    verify_languages(args.directory)
    verify_jpg(args.directory.parent / "us-directory" / "Covers" / "directory-cover.jpg")
    for genre in DIRECTORY_GENRES:
        slug = "-".join(re.findall(r"[a-z0-9]+", genre.lower()))
        verify_jpg(args.directory.parent / "us-directory" / "Covers" / (slug + ".jpg"))


if __name__ == "__main__":
    main()

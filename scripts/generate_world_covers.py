#!/usr/bin/env python3
"""Generate consistent dark-glass cover art for World Radio and language playlists.

Four shared original U.S. covers stay untouched. Existing artwork is preserved
unless an explicit restyle is requested.
"""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image

from radio_artwork import SIZE, cover

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
PREFIX = "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/logos/"
LANGUAGE_PREFIX = "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/"


def targets(stations, root=WORLD):
    for station in stations:
        # Query fragments are allowed for versioned artwork in cached clients.
        if urlsplit(station.get("logo", "")).path.endswith("/world-radio/logos/" + station["id"] + ".png"):
            yield station, Path(root) / "logos" / (station["id"] + ".png")


def language_catalogs(root=WORLD):
    root = Path(root)
    for path in sorted(root.glob("*/stations.json")):
        folder = path.parent
        stations = json.loads(path.read_text(encoding="utf-8"))
        yield folder.name, stations


def language_targets(root=WORLD):
    for language, stations in language_catalogs(root):
        for station in stations:
            expected = f"/world-radio/{language}/logos/{station['id']}.png"
            if not urlsplit(station.get("logo", "")).path.endswith(expected):
                raise ValueError("Language artwork URL mismatch: " + station["id"])
            yield station, Path(root) / language / "logos" / (station["id"] + ".png")


# Radio NIC uses artwork supplied by its owner. Never re-render it.
PROTECTED_ARTWORK_IDS = frozenset({"ir-radio-nic"})


def write_cover(station, path, force=False):
    if path.is_file() and (not force or station["id"] in PROTECTED_ARTWORK_IDS):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name("." + path.name + ".tmp")
    try:
        cover(station).save(temp, "PNG", optimize=True)
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)
    return True


def generate(stations, root=WORLD, *, force=False):
    made = sum(write_cover(station, path, force)
               for station, path in targets(stations, root))
    print(f"World radio covers generated: {made}", flush=True)
    return made


def generate_languages(root=WORLD, *, force=False):
    made = sum(write_cover(station, path, force)
               for station, path in language_targets(root))
    print(f"Language radio covers generated: {made}", flush=True)
    return made


def verify_png(path):
    if not path.is_file():
        raise ValueError("Missing radio artwork: " + str(path))
    with Image.open(path) as image:
        # Preserve owner-supplied original artwork, including its native size.
        protected = path.stem in PROTECTED_ARTWORK_IDS
        valid_size = (image.width >= SIZE and image.height >= SIZE) if protected else image.size == (SIZE, SIZE)
        if image.format != "PNG" or not valid_size:
            raise ValueError("Invalid radio artwork: " + str(path))
        image.verify()


def verify(stations, root=WORLD):
    total = 0
    for _, path in targets(stations, root):
        verify_png(path)
        total += 1
    if total < 60:
        raise ValueError("Incomplete World Radio artwork set")
    print(f"Verified {total} world station covers", flush=True)


def verify_languages(root=WORLD):
    counts = {}
    for station, path in language_targets(root):
        verify_png(path)
        counts[station["language"]] = counts.get(station["language"], 0) + 1
    if len(counts) < 5:
        raise ValueError("Too few language artwork collections")
    print("Verified language radio covers:", counts, flush=True)


def directory_cover(root=ROOT, *, force=False):
    filename = Path(root) / "us-directory" / "directory-cover.png"
    if not filename.is_file() or force:
        write_cover({"id": "us-directory-cover", "name": "USA Radio Directory",
                     "country_code": "US", "genre": "American Radio"}, filename,
                    force=force)
    verify_png(filename)
    return filename


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restyle", action="store_true",
                        help="Rebuild generated world/language covers in the latest style")
    parser.add_argument("--force", action="store_true",
                        help="Alias for --restyle, used by local cover tooling")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--directory", type=Path, default=WORLD)
    args = parser.parse_args()
    stations = json.loads((args.directory / "stations.json").read_text(encoding="utf-8"))
    if not args.verify:
        rebuild = args.restyle or args.force
        generate(stations, args.directory, force=rebuild)
        generate_languages(args.directory, force=rebuild)
        directory_cover(root=args.directory.parent, force=rebuild)
    verify(stations, args.directory)
    verify_languages(args.directory)
    verify_png(args.directory.parent / "us-directory" / "directory-cover.png")


if __name__ == "__main__":
    main()

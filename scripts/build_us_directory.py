#!/usr/bin/env python3
"""Build optional, sharded U.S. radio directory subscriptions for Primuse.

The 36-station curated catalog is deliberately independent. Radio Browser
Radio Browser health metadata is separate from decoded-audio testing.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from safety import atomic_write, has_expiring_query, valid_url, unsupported_stream_suffix
from content_filters import is_excluded_program

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "us-directory"
API_BASES = (
    "https://de1.api.radio-browser.info",
    "https://all.api.radio-browser.info",
)
USER_AGENT = "ApplePrimuseUSDirectory/1.0 (https://github.com/th3cyrus/Apple)"
PAGE_SIZE = 2500
MAX_PAGES = 8
SHARDS = 12
SHARD_MAX = 900  # Primuse hard limit is 1000 entries per subscription.
MIN_RESULTS = 500
FEATURED_MAX = 100
MAX_HEALTH_AGE_DAYS = 30
MAX_DIRECTORY_SHRINK_RATIO = 0.65
FALLBACK_ARTWORK = "https://raw.githubusercontent.com/th3cyrus/Apple/main/us-directory/directory-cover.png"
# Editorial nonreligious additions replacing identified religious directory streams.
# These come from public broadcaster direct-stream listings, not Radio Browser votes.
PINNED_NONRELIGIOUS = (
    {"id": "us-radio-paradise-beyond", "name": "Radio Paradise Beyond Mix",
     "url": "https://stream.radioparadise.com/beyond-192", "group": "Rock & Alternative",
     "logo": FALLBACK_ARTWORK, "votes": 0},
    {"id": "us-somafm-boot-liquor", "name": "SomaFM Boot Liquor (128k MP3)",
     "url": "https://ice5.somafm.com/bootliquor-128-mp3", "group": "Country",
     "logo": FALLBACK_ARTWORK, "votes": 0},
)
ATTR_CLEAN = re.compile(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2066-\u2069"<>]')
BAD_AUDIO_PLAYLIST = re.compile(
    r'\.(?:mp3|aac|m4a|ogg|opus|flac|wav)\.(?:m3u|m3u8|pls)$', re.I)

GENRES = (
    ("Hip-Hop & R&B", ("hip hop", "hip-hop", "hiphop", "r&b", "soul")),
    ("Rock & Alternative", ("rock", "metal", "alternative", "punk", "indie")),
    ("Country", ("country", "bluegrass", "americana")),
    ("Jazz & Blues", ("jazz", "blues", "funk")),
    ("Classical", ("classical", "opera", "symphony")),
    ("News & Talk", ("news", "talk", "public radio", "npr", "sports", "politics")),
    ("Electronic & Dance", ("dance", "electronic", "house", "techno", "trance")),
    ("Latin & Spanish", ("latin", "spanish", "salsa", "reggaeton", "regional mexicano")),
    ("Christian & Gospel", ("christian", "gospel", "worship")),
    ("Pop & Hits", ("pop", "hits", "top 40", "adult contemporary", "oldies")),
)


def clean_text(value, max_chars=100):
    text = ATTR_CLEAN.sub(" ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip(" ,;-")[:max_chars].strip()


def public_https(value):
    if not valid_url(value) or urlsplit(value).scheme != "https":
        return False
    parts = urlsplit(value)
    host = (parts.hostname or "").lower().rstrip(".")
    if not host or host == "localhost" or host.endswith((".local", ".internal", ".test")):
        return False
    try:
        if not ipaddress.ip_address(host).is_global:
            return False
    except ValueError:
        pass
    if has_expiring_query(value):
        return False
    return not unsupported_stream_suffix(value) and not BAD_AUDIO_PLAYLIST.search(parts.path)


def genre(tags):
    value = clean_text(tags, 250).lower()
    for label, needles in GENRES:
        if any(word in value for word in needles):
            return label
    return "Other U.S. Radio"


def normalize(record):
    if not isinstance(record, dict) or str(record.get("countrycode", "")).upper() != "US":
        return None
    if record.get("lastcheckok") not in (True, 1, "1"):
        return None
    if record.get("ssl_error", 0) not in (False, 0, "0"):
        return None
    try:
        checked = datetime.fromisoformat(record["lastchecktime_iso8601"].replace("Z", "+00:00"))
        if checked.tzinfo is None:
            return None
        age = (datetime.now(timezone.utc) - checked.astimezone(timezone.utc)).total_seconds()
        if not -12 * 3600 <= age <= MAX_HEALTH_AGE_DAYS * 86400:
            return None
    except (KeyError, ValueError, TypeError, AttributeError):
        return None
    name = clean_text(record.get("name"), 100)
    if len(name) < 2 or is_excluded_program(
            name, record.get("tags"), record.get("homepage"),
            record.get("url_resolved"), record.get("url")):
        return None
    stream = record.get("url_resolved") or record.get("url")
    if not public_https(stream):
        # Resolved URL may be invalid; use the original only if it passes policy.
        stream = record.get("url")
        if not public_https(stream):
            return None
    # Playlist-wrapper URLs with misleading extension/content cannot be
    # diagnosed from directory metadata alone, so omit .m3u and .pls.
    path = urlsplit(stream).path.lower()
    if path.endswith((".m3u", ".pls")):
        return None
    logo = record.get("favicon")
    if not public_https(logo):
        logo = FALLBACK_ARTWORK
    station_id = clean_text(record.get("stationuuid"), 80) or hashlib.sha256(stream.encode()).hexdigest()
    try:
        votes = max(0, int(record.get("votes") or 0))
    except (ValueError, TypeError, OverflowError):
        votes = 0
    return {
        "id": station_id, "name": name, "url": stream,
        "logo": logo, "group": genre(record.get("tags", "")),
        "votes": votes,
    }


def catalog(records, curated_urls=()):
    curated = set(curated_urls)
    selected = {}
    for record in records:
        station = normalize(record)
        if station is None or station["url"] in curated:
            continue
        previous = selected.get(station["url"])
        if previous is None or station["votes"] > previous["votes"]:
            selected[station["url"]] = station
    items = list(selected.values())
    items.sort(key=lambda s: (s["group"], s["name"].casefold(), s["id"]))
    return items


def add_nonreligious_replacements(items, curated_urls=()):
    """Preserve two distinct vetted nonreligious choices after source filtering."""
    excluded = set(curated_urls)
    present = {station["url"] for station in items}
    for station in PINNED_NONRELIGIOUS:
        if (station["url"] not in present and station["url"] not in excluded
                and public_https(station["url"])
                and not is_excluded_program(station["name"], station["url"])):
            items.append(dict(station))
            present.add(station["url"])
    items.sort(key=lambda s: (s["group"], s["name"].casefold(), s["id"]))
    return items


def split(items):
    buckets = [[] for _ in range(SHARDS)]
    for item in items:
        number = int(hashlib.sha256(item["id"].encode()).hexdigest()[:12], 16) % SHARDS
        buckets[number].append(item)
    if any(len(bucket) > SHARD_MAX for bucket in buckets):
        raise ValueError("Directory outgrew Primuse-safe shards; increase SHARDS first")
    return buckets


def m3u(items):
    rows = ["#EXTM3U"]
    for item in items:
        attrs = [f'group-title="{clean_text(item["group"], 60)}"']
        if item["logo"]:
            if not public_https(item["logo"]):
                raise ValueError("Unsafe directory artwork URL")
            attrs.append(f'tvg-logo="{item["logo"]}"')
        rows.append(f'#EXTINF:-1 {" ".join(attrs)},{clean_text(item["name"])}')
        rows.append(item["url"])
    return "\n".join(rows) + "\n"


def get_records(session):
    error = None
    for base in API_BASES:
        found = []
        try:
            for page in range(MAX_PAGES):
                response = session.get(
                    base + "/json/stations/bycountrycodeexact/US",
                    params={"hidebroken": "true", "order": "votes",
                            "reverse": "true", "offset": page * PAGE_SIZE,
                            "limit": PAGE_SIZE},
                    headers={"User-Agent": USER_AGENT}, timeout=(6, 40),
                )
                response.raise_for_status()
                batch = response.json()
                if not isinstance(batch, list):
                    raise ValueError("Radio Browser did not return a JSON list")
                found.extend(batch)
                if len(batch) < PAGE_SIZE:
                    break
            else:
                raise ValueError("Source exceeded pagination budget; refuse truncation")
            if len(found) < MIN_RESULTS:
                raise ValueError("Source is unexpectedly small; refuse mass deletion")
            return found
        except (requests.RequestException, ValueError) as exc:
            error = exc
    raise RuntimeError("Unable to fetch full U.S. station directory") from error


def validate_outputs(output=OUTPUT):
    """Check every published shard and the featured preview without network access."""
    output = Path(output)
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    expected_files = [f"us-{number:02d}.m3u" for number in range(1, SHARDS + 1)]
    shards = index.get("shards", [])
    if (index.get("shard_count") != SHARDS or not isinstance(shards, list)
            or len(shards) != SHARDS
            or any(not isinstance(item, dict) for item in shards)
            or [item.get("file") for item in shards] != expected_files):
        raise ValueError("Invalid directory shard index")

    def read_playlist(filename):
        lines = (output / filename).read_text(encoding="utf-8").splitlines()
        if not lines or lines[0] != "#EXTM3U" or len(lines) % 2 != 1:
            raise ValueError("Invalid directory M3U structure: " + filename)
        entries = []
        urls = set()
        for metadata, url in zip(lines[1::2], lines[2::2]):
            match = re.fullmatch(
                r'#EXTINF:-1 group-title="([^"]+)"(?: tvg-logo="([^"]+)")?,(.+)', metadata)
            if not match or not public_https(url) or urlsplit(url).path.lower().endswith((".m3u", ".pls")):
                raise ValueError("Unsafe directory entry in " + filename)
            group, logo, name = match.groups()
            if (clean_text(group, 60) != group or clean_text(name) != name
                    or (logo and not public_https(logo))
                    or is_excluded_program(name, group, url)):
                raise ValueError("Invalid directory metadata/policy in " + filename)
            if url in urls:
                raise ValueError("Duplicate directory stream in " + filename)
            urls.add(url)
            entries.append((metadata, url))
        return entries

    all_entries = []
    for shard in shards:
        entries = read_playlist(shard["file"])
        if (type(shard.get("stations")) is not int
                or shard["stations"] != len(entries) or len(entries) > SHARD_MAX):
            raise ValueError("Directory shard count mismatch: " + shard["file"])
        all_entries.extend(entries)
    if (type(index.get("station_count")) is not int
            or index["station_count"] != len(all_entries)
            or len(all_entries) < MIN_RESULTS
            or len({url for _, url in all_entries}) != len(all_entries)):
        raise ValueError("Directory total/unique stream count mismatch")
    featured = read_playlist("featured.m3u")
    if (len(featured) != min(FEATURED_MAX, len(all_entries))
            or not set(featured).issubset(set(all_entries))):
        raise ValueError("Featured preview differs from published directory")
    return index


def build(session, output=OUTPUT, curated_path=ROOT / "stations.json"):
    curated = json.loads(Path(curated_path).read_text(encoding="utf-8"))
    existing = [station["stream"] for station in curated]
    items = add_nonreligious_replacements(catalog(get_records(session), existing), existing)
    if len(items) < MIN_RESULTS:
        raise ValueError("Not enough compatible U.S. streams; existing lists unchanged")
    existing_index = Path(output) / "index.json"
    if existing_index.is_file():
        try:
            previous_count = json.loads(existing_index.read_text(encoding="utf-8"))["station_count"]
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("Existing index corrupted; refuse to overwrite playlists") from exc
        if (type(previous_count) is not int or previous_count < MIN_RESULTS
                or len(items) < previous_count * MAX_DIRECTORY_SHRINK_RATIO):
            raise ValueError("U.S. directory shrank unexpectedly; manual review required")
    shards = split(items)
    # Prepare everything before publishing a single file.
    files = {}
    for index, stations in enumerate(shards, 1):
        files[f"us-{index:02d}.m3u"] = m3u(stations)
    featured = sorted(items, key=lambda s: (-s["votes"], s["name"].casefold(), s["id"]))[:FEATURED_MAX]
    files["featured.m3u"] = m3u(featured)
    files["index.json"] = json.dumps({
        "source": "Radio Browser: countrycode=US, lastcheckok=1",
        "scope": "Directory candidates, not individual audio playback verified",
        "transport": "HTTPS only",
        "station_count": len(items),
        "health_policy": f"checked within {MAX_HEALTH_AGE_DAYS} days, no reported SSL error; unsigned HTTPS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "shard_count": SHARDS,
        "shards": [{"file": f"us-{i:02d}.m3u", "stations": len(stations)}
                   for i, stations in enumerate(shards, 1)],
    }, ensure_ascii=False, indent=2) + "\n"
    intro = [
        "# U.S. Radio Directory for Primuse",
        "",
        f"{len(items):,} U.S. stream entries across {SHARDS} M3U subscriptions. "
        "Import each selected playlist into Primuse.",
        "",
        "Sources include Radio Browser and selected broadcaster streams. "
        "Directory entries are not individually audio-decoded. "
        "The [curated U.S. playlist](../radio.m3u) is maintained separately.",
        "",
        "Dedicated religious programming is excluded across all faiths. "
        "The generator filters signed links, stale health records, reported SSL errors "
        "and invalid playlists. Missing station artwork uses a shared fallback cover.",
        "",
        "| Subscription | Stations |",
        "|---|---:|",
    ]
    for i, stations in enumerate(shards, 1):
        filename = f"us-{i:02d}.m3u"
        url = f"https://raw.githubusercontent.com/th3cyrus/Apple/main/us-directory/{filename}"
        intro.append(f"| [U.S. Directory {i:02d}]({url}) | {len(stations)} |")
    files["README.md"] = "\n".join(intro) + "\n"
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # GitHub Action stages changes only if the whole build succeeds.
    for name, contents in files.items():
        atomic_write(output / name, contents)
    validate_outputs(output)
    print(f"Built {len(items)} U.S. stations in {SHARDS} Primuse-safe playlists")
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--validate", action="store_true", help="Validate published files offline")
    args = parser.parse_args()
    if args.validate:
        index = validate_outputs(args.output)
        print("Validated", index["station_count"], "directory streams and featured preview")
        return
    with requests.Session() as session:
        build(session, output=args.output)


if __name__ == "__main__":
    main()

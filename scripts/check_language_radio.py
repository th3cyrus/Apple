#!/usr/bin/env python3
"""Validate all independent language-based M3U subscriptions and audit audio.

Station catalogs are stable editorial data; temporary stream health stays in
GitHub Actions artifacts and never mutates station names or URLs automatically.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qsl, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
sys.path.insert(0, str(ROOT / "scripts"))
from content_filters import is_excluded_program
from safety import valid_url, unsupported_stream_suffix, safe_message
from stream_probe import stream_check

MAX_PER_LANGUAGE = 900
CONTENT_FIELDS = {"id", "name", "language", "country_code",
                  "genre", "stream", "logo"}
SIGNED_PARAMETERS = {"token", "policy", "signature", "expires", "zt", "key"}


def check_language(path, entry):
    path = Path(path)
    stations = json.loads((path / "stations.json").read_text(encoding="utf-8"))
    if not isinstance(stations, list) or not 1 <= len(stations) <= MAX_PER_LANGUAGE:
        raise ValueError(f"Invalid catalog length for {path.name}")
    if len(stations) != entry["count"]:
        raise ValueError(f"Language index count mismatch: {path.name}")
    stream_urls = set()
    station_ids = set()
    m3u = ["#EXTM3U"]
    for station in stations:
        if not isinstance(station, dict) or not CONTENT_FIELDS.issubset(station):
            raise ValueError(f"Incomplete station metadata in {path.name}")
        if any(not isinstance(station[key], str) or not station[key].strip()
               for key in CONTENT_FIELDS):
            raise ValueError(f"Blank station metadata in {path.name}")
        if station["language"] != entry["name"]:
            raise ValueError("Station language mismatch: " + station["id"])
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", station["id"]):
            raise ValueError("Invalid station identifier: " + station["id"])
        if not re.fullmatch(r"[A-Z]{2}", station["country_code"]):
            raise ValueError("Invalid station country code")
        if is_excluded_program(station["name"], station["genre"], station["stream"]):
            raise ValueError("Dedicated religious radio excluded: " + station["id"])
        url = station["stream"]
        parts = urlsplit(url)
        if (not valid_url(url) or parts.scheme != "https"
                or unsupported_stream_suffix(url)
                or parts.path.lower().endswith((".m3u", ".pls"))):
            raise ValueError("Invalid HTTPS stream: " + station["id"])
        if any(k.lower() in SIGNED_PARAMETERS for k, _ in parse_qsl(parts.query)):
            raise ValueError("Expiring URL parameter for: " + station["id"])
        if url in stream_urls or station["id"] in station_ids:
            raise ValueError("Duplicate station ID or URL in " + path.name)
        stream_urls.add(url)
        station_ids.add(station["id"])
        logo_parts = urlsplit(station["logo"])
        if logo_parts.scheme != "https" or not logo_parts.path.endswith(
                "/world-radio/" + path.name + "/logos/" + station["id"] + ".png"):
            raise ValueError("Incorrect station artwork URL: " + station["id"])

        safe_name = station["name"].replace('"', " ").replace("<", " ").replace(">", " ")
        if "\n" in safe_name or "\r" in safe_name:
            raise ValueError("Station name contains newline")
        m3u.append(
            f'#EXTINF:-1 tvg-logo="{station["logo"]}" logo="{station["logo"]}" '
            f'group-title="{entry["name"]} Radio",{safe_name} ({station["country_code"]})'
        )
        m3u.append(url)
    expected = "\n".join(m3u) + "\n"
    actual = (path / "radio.m3u").read_text(encoding="utf-8")
    if actual != expected:
        raise ValueError("M3U differs from station metadata: " + path.name)
    return stations


def load_all(root=WORLD):
    root = Path(root)
    entries = json.loads((root / "languages.json").read_text(encoding="utf-8"))
    if not isinstance(entries, list) or len(entries) < 5:
        raise ValueError("At least five independent language subscriptions required")
    used = set()
    records = []
    for entry in entries:
        language = entry["id"]
        if not re.fullmatch(r"[a-z]+", language) or language in used:
            raise ValueError("Duplicate or invalid language identifier")
        used.add(language)
        if entry["playlist"] != (
            "https://raw.githubusercontent.com/th3cyrus/Apple/main/world-radio/"
            + language + "/radio.m3u"):
            raise ValueError("Invalid language subscription URL: " + language)
        for station in check_language(root / language, entry):
            records.append(dict(station, collection=language))
    return entries, records


def probe_one(station):
    try:
        with requests.Session() as session:
            result = stream_check(session, station["stream"])
    except Exception as exc:
        result = {"ok": False, "error_type": type(exc).__name__,
                  "error": safe_message(exc)[:160]}
    return {
        "id": station["id"], "collection": station["collection"],
        "name": station["name"], "ok": bool(result.get("ok")),
        "codec": result.get("codec"),
        "error_type": result.get("error_type"),
        "http_status": result.get("http_status"),
        "error": result.get("error"),
    }


def audit(stations, output, workers=10):
    items = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        tasks = {pool.submit(probe_one, s): s for s in stations}
        for job in as_completed(tasks):
            entry = job.result()
            items.append(entry)
            print(("PASS" if entry["ok"] else "FAIL"),
                  entry["collection"], entry["name"],
                  entry["codec"] or entry["error_type"] or "", flush=True)
    position = {(s["collection"], s["id"]): i for i, s in enumerate(stations)}
    items.sort(key=lambda s: position[(s["collection"], s["id"])])
    passing = sum(x["ok"] for x in items)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_environment": "GitHub Actions audio decoding",
        "total": len(items), "passed": passing,
        "needs_review": len(items) - passing, "stations": items,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(f"Language Radio: {passing}/{len(items)} decoded-audio checks passed", flush=True)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--require-healthy", action="store_true")
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "logs" / "language-radio-audit.json")
    args = parser.parse_args()
    if args.require_healthy and not args.audit:
        parser.error("--require-healthy requires --audit")
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    entries, stations = load_all()
    print(f"Validated {len(entries)} language playlists, {len(stations)} radio entries",
          flush=True)
    if args.audit:
        report = audit(stations, args.output, workers=args.workers)
        if args.require_healthy and report["needs_review"]:
            failures = [x["collection"] + "/" + x["id"] for x in report["stations"]
                        if not x["ok"]]
            raise ValueError(f"{len(failures)} language streams require review: "
                             + ", ".join(failures[:16]))


if __name__ == "__main__":
    main()

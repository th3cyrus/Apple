#!/usr/bin/env python3
"""Validate World Radio Select and optionally audit real decoded live audio.

Audit reports are stored separately from station metadata.
Never remove stations solely because of an intermittent check failure.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time as local_time, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
sys.path.insert(0, str(ROOT / "scripts"))
from safety import (atomic_json, has_expiring_query, public_media_url, valid_url,
                    unsupported_stream_suffix, safe_message)
from content_filters import is_excluded_program
from stream_probe import stream_check

REGIONS = {"Europe", "North America", "Caribbean", "South America",
           "Africa", "Asia & Middle East", "Oceania"}
MAX_ENTRIES = 900
BAD_TEXT_EXT = (".m3u", ".pls")
FIELDS = {"id", "name", "country", "country_code", "region", "genre", "stream", "logo"}

# Explicitly published broadcast windows; never infer availability from timezone.
# Chula Radio Plus: https://curadio.car.chula.ac.th/contact (daily 06:00–21:00).
BROADCAST_HOURS = {
    "th-chula-radio-plus": ("Asia/Bangkok", local_time(6), local_time(21)),
}


def scheduled_off_air(station, moment=None):
    """True only for a station with verified hours, outside its local broadcast."""
    hours = BROADCAST_HOURS.get(station["id"])
    if hours is None:
        return False
    zone, opening, closing = hours
    instant = moment if moment is not None else datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Broadcast window checks require timezone-aware datetimes")
    clock = instant.astimezone(ZoneInfo(zone)).time()
    return not opening <= clock < closing


def load_and_validate(root=WORLD):
    root = Path(root)
    catalog = json.loads((root / "stations.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not (25 <= len(catalog) <= MAX_ENTRIES):
        raise ValueError("World radio selection must contain 25–900 entries")
    ids, urls = set(), set()
    for position, station in enumerate(catalog, start=1):
        if not isinstance(station, dict) or not FIELDS.issubset(station):
            raise ValueError(f"Entry {position} is incomplete")
        if "verification" in station:
            raise ValueError("Station audit status belongs in workflow reports, not stations.json")
        if any(not isinstance(station[key], str) or not station[key].strip()
               for key in FIELDS):
            raise ValueError(f"Entry {position} contains blank/invalid fields")
        if any(re.search(r'[\x00-\x1f\x7f"<>]', station[key])
               for key in ("name", "country", "genre")):
            raise ValueError(f"Unsafe station metadata at entry {position}")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", station["id"]):
            raise ValueError("Unsafe station ID: " + station["id"])
        if station["region"] not in REGIONS:
            raise ValueError("Unknown geographic region")
        if not re.fullmatch(r"[A-Z]{2}", station["country_code"]):
            raise ValueError("Invalid country code")
        url = station["stream"]
        if is_excluded_program(station["name"], station.get("genre"), url):
            raise ValueError("Religious radio station excluded: " + station["id"])
        parts = urlsplit(url)
        if (not public_media_url(url) or parts.scheme != "https"
                or unsupported_stream_suffix(url)
                or parts.path.lower().endswith(BAD_TEXT_EXT)):
            raise ValueError("Invalid or misleading station stream for " + station["id"])
        if has_expiring_query(url):
            raise ValueError("Potentially expiring stream token for " + station["id"])
        logo = station["logo"]
        if not isinstance(logo, str) or (logo and
                (not valid_url(logo) or urlsplit(logo).scheme != "https")):
            raise ValueError("Unsafe station artwork URL")
        if station["id"] in ids or url in urls:
            raise ValueError("Duplicate world-radio station ID or stream")
        ids.add(station["id"])
        urls.add(url)
    lines = (root / "radio.m3u").read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "#EXTM3U" or len(lines) != 1 + len(catalog) * 2:
        raise ValueError("World M3U header / length mismatch")
    for i, station in enumerate(catalog):
        inf = lines[1 + 2*i]
        expected = (f'#EXTINF:-1 group-title="{station["region"]}" '
                    f'tvg-country="{station["country_code"]}" '
                    f'tvg-logo="{station["logo"]}" logo="{station["logo"]}",'
                    f'{station["name"]} ({station["country_code"]})')
        if inf != expected or lines[2 + 2*i] != station["stream"]:
            raise ValueError("Playlist/stations.json mismatch at " + station["id"])
    return catalog


def probe_one(station):
    began = time.monotonic()
    if scheduled_off_air(station):
        # Preserve an explicit "not tested" result: off-air is not a pass.
        return {
            "id": station["id"], "name": station["name"],
            "country_code": station["country_code"], "ok": False,
            "skipped": True, "status": "scheduled_off_air",
            "reason": "Outside published daily 06:00–21:00 Asia/Bangkok broadcast",
            "codec": None, "decoded_seconds": None, "rms_dbfs": None,
            "http_status": None, "error_type": None, "error": None,
            "probe": None,
            "elapsed_seconds": round(time.monotonic() - began, 2),
        }
    try:
        with requests.Session() as session:
            result = stream_check(session, station["stream"])
    except Exception as exc:
        result = {"ok": False, "error_type": type(exc).__name__,
                  "error": safe_message(exc)[:150]}
    return {
        "id": station["id"], "name": station["name"],
        "country_code": station["country_code"],
        "ok": bool(result.get("ok", False)),
        "codec": result.get("codec"), "decoded_seconds": result.get("decoded_seconds"),
        "rms_dbfs": result.get("rms_dbfs"),
        "http_status": result.get("http_status"),
        "error_type": result.get("error_type"), "error": result.get("error"),
        "probe": result,
        "elapsed_seconds": round(time.monotonic()-began, 2)
    }


def audit(catalog, output, workers=12):
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(probe_one, station): station for station in catalog}
        for future in as_completed(jobs):
            item = future.result()
            results.append(item)
            label = "SKIP" if item.get("skipped") else ("PASS" if item["ok"] else "FAIL")
            print(label, item["name"],
                  item.get("codec") or item.get("status")
                  or item.get("error_type") or "Unknown", flush=True)
    order = {s["id"]: idx for idx, s in enumerate(catalog)}
    results.sort(key=lambda result: order[result["id"]])
    passed = sum(result["ok"] for result in results)
    skipped = sum(bool(result.get("skipped")) for result in results)
    checked = len(results) - skipped
    needs_review = checked - passed
    document = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "CI runner: decoded-audio sample",
        "total": len(results), "checked": checked,
        "passed": passed, "skipped_off_air": skipped,
        "needs_review": needs_review, "stations": results,
    }
    output = Path(output)
    atomic_json(output, document)
    summary = (f"World Radio Select: {passed}/{checked} scheduled-on-air streams "
               f"decoded non-silent audio; {skipped} scheduled off-air (not tested); "
               f"{needs_review} require review.")
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as file:
            file.write("### World Radio Select live audit\n\n"+summary+"\n\n")
            file.write("Results reflect a bounded audio sample from the CI runner.\n")
    return document


def require_audible(document):
    """Raise only after the audit report is persisted for troubleshooting."""
    if document['needs_review']:
        failed = [entry['id'] for entry in document['stations']
                  if not entry['ok'] and not entry.get('skipped')]
        raise ValueError(f'World radio audio degraded: {len(failed)} failed: '
                         + ', '.join(failed[:12]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--require-healthy", action="store_true",
                        help="Fail the workflow after persisting all stream diagnostics")
    parser.add_argument("--output", type=Path, default=ROOT / "logs" / "world-radio-audit.json")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    stations = load_and_validate()
    print("Validated World Radio Select", len(stations), "stations")
    if args.require_healthy and not args.audit:
        parser.error('--require-healthy requires --audit')
    if args.audit:
        result = audit(stations, args.output, args.workers)
        if args.require_healthy:
            require_audible(result)


if __name__ == "__main__":
    main()

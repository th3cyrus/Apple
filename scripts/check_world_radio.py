#!/usr/bin/env python3
"""Validate World Radio Select and optionally audit real decoded live audio.

Audit results are evidence from a GitHub runner, not proof of playability
in Primuse or in every country. Never automatically delete a station.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
WORLD = ROOT / "world-radio"
sys.path.insert(0, str(ROOT / "scripts"))
from safety import valid_url, unsupported_stream_suffix
from stream_probe import stream_check

REGIONS = {"Europe", "North America", "Caribbean", "South America",
           "Africa", "Asia & Middle East", "Oceania"}
MAX_ENTRIES = 900
BAD_TEXT_EXT = (".m3u", ".pls")
FIELDS = {"id", "name", "country", "country_code", "region", "genre", "stream", "logo"}


def load_and_validate(root=WORLD):
    root = Path(root)
    catalog = json.loads((root / "stations.json").read_text(encoding="utf-8"))
    if not isinstance(catalog, list) or not (25 <= len(catalog) <= MAX_ENTRIES):
        raise ValueError("World radio selection must contain 25–900 entries")
    ids, urls = set(), set()
    for position, station in enumerate(catalog, start=1):
        if not isinstance(station, dict) or not FIELDS.issubset(station):
            raise ValueError(f"Entry {position} is incomplete")
        if any(not isinstance(station[key], str) or not station[key].strip()
               for key in ("id", "name", "country", "country_code", "region", "genre", "stream")):
            raise ValueError(f"Entry {position} contains blank/invalid fields")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", station["id"]):
            raise ValueError("Unsafe station ID: " + station["id"])
        if station["region"] not in REGIONS:
            raise ValueError("Unknown geographic region")
        if not re.fullmatch(r"[A-Z]{2}", station["country_code"]):
            raise ValueError("Invalid country code")
        url = station["stream"]
        parts = urlsplit(url)
        if (not valid_url(url) or parts.scheme != "https"
                or unsupported_stream_suffix(url)
                or parts.path.lower().endswith(BAD_TEXT_EXT)):
            raise ValueError("Invalid or misleading station stream for " + station["id"])
        if any(key.lower() in {"token", "policy", "key", "zt"}
               for key in __import__("urllib.parse", fromlist=["parse_qsl"]).parse_qs(parts.query)):
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
        if (not inf.startswith("#EXTINF:-1 ") or
            f'group-title="{station["region"]}"' not in inf or
            f'tvg-country="{station["country_code"]}"' not in inf or
            not inf.endswith("," + station["name"] + " (" + station["country_code"] + ")") or
            lines[2 + 2*i] != station["stream"]):
            raise ValueError("Playlist/stations.json mismatch at " + station["id"])
    return catalog


def probe_one(station):
    began = time.monotonic()
    try:
        with requests.Session() as session:
            result = stream_check(session, station["stream"])
    except Exception as exc:
        result = {"ok": False, "error_type": type(exc).__name__,
                  "error": str(exc)[:150]}
    return {
        "id": station["id"], "name": station["name"],
        "country_code": station["country_code"],
        "ok": bool(result.get("ok", False)),
        "codec": result.get("codec"), "decoded_seconds": result.get("decoded_seconds"),
        "rms_dbfs": result.get("rms_dbfs"),
        "http_status": result.get("http_status"),
        "error_type": result.get("error_type"), "error": result.get("error"),
        "elapsed_seconds": round(time.monotonic()-began, 2)
    }


def audit(catalog, output, workers=12):
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(probe_one, station): station for station in catalog}
        for future in as_completed(jobs):
            item = future.result()
            results.append(item)
            print(("PASS" if item["ok"] else "FAIL"), item["name"],
                  item.get("codec") or item.get("error_type") or "Unknown",
                  flush=True)
    order = {s["id"]: idx for idx, s in enumerate(catalog)}
    results.sort(key=lambda result: order[result["id"]])
    passed = sum(result["ok"] for result in results)
    document = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scope": "Server-side decoded audio; NOT a Primuse or country-wide playback guarantee",
        "total": len(results), "passed": passed, "needs_review": len(results)-passed,
        "stations": results,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2)+"\n",encoding="utf-8")
    summary = (f"World Radio Select: {passed}/{len(results)} decoded non-silent audio; "
               f"{len(results)-passed} require review. Not validated from Iraq.")
    print(summary, flush=True)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as file:
            file.write("### World Radio Select live audit\n\n"+summary+"\n\n")
            file.write("Source URL response and audio decoding cannot guarantee Primuse playback.\n")
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "logs" / "world-radio-audit.json")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error("--workers must be between 1 and 16")
    stations = load_and_validate()
    print("Validated World Radio Select", len(stations), "stations")
    if args.audit:
        audit(stations, args.output, args.workers)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Regenerate Primuse radio playlists using custom, self-hosted artwork.

Both local and published playlists reference the custom covers in logos/.
Refresh mode may repair radio streams but never replaces custom artwork.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import traceback
from copy import deepcopy
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from radio_artwork import cover_svg, verify_svg
from radio_browser import RadioBrowserClient
from catalog import validate_catalog
from health_report import HealthReporter
from identity import candidate_score, candidate_rejection_reasons, hostname, site_match, simplify
from safety import atomic_json, atomic_write, safe_message, safe_url, valid_url
from stream_probe import stream_check

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'stations.json'
LOGOS = ROOT / 'logos'
M3U = ROOT / 'radio.m3u'
HEALTH_LOG = ROOT / 'logs' / 'stream-health.jsonl'
CURRENT_REPORT = ROOT / 'logs' / 'current-run.json'
FAILURE_INTERVAL_SECONDS = 24 * 3600
MAX_CANDIDATE_CHECKS = 3
REFRESH_BUDGET_SECONDS = 15 * 60
DEFAULT_REPO = 'th3cyrus/Apple'
def artwork_placeholder(station):
    """Provide new station-specific pure-vector cover art."""
    return cover_svg({**station, "language": "USA", "country_code": "US",
                      "genre": station.get("description") or "American Radio"})


def escape_attr(value):
    return str(value).replace('"', '').replace('\n', ' ').replace('\r', ' ')


def generate(stations, repo):
    validate_catalog(stations)
    artwork_repo = repo or DEFAULT_REPO
    result = ['#EXTM3U']
    for station in stations:
        artwork = station['logo']
        if not (ROOT / artwork).is_file():
            raise FileNotFoundError(f'Missing custom artwork: {artwork}')
        logo = f'https://raw.githubusercontent.com/{artwork_repo}/main/{artwork}'
        result.append(f'#EXTINF:-1 tvg-logo="{escape_attr(logo)}" logo="{escape_attr(logo)}" '
                      f'group-title="{escape_attr(station["group"])}",{escape_attr(station["name"])}')
        result.append(station['stream'])
    atomic_write(M3U, '\n'.join(result) + '\n')


def record_failure(station, now):
    """Count a failure at most once per 24 hours, independent of network retries."""
    previous = station.get('last_failure_counted_at')
    if previous:
        last = datetime.fromisoformat(previous.replace('Z', '+00:00'))
        if (now - last).total_seconds() < FAILURE_INTERVAL_SECONDS:
            return False
    elif station.get('fail_count', 0):
        # Old counters have no spacing evidence: start the new policy fresh.
        station['fail_count'] = 0
    station['fail_count'] = min(20, station.get('fail_count', 0) + 1)
    station['last_failure_counted_at'] = now.isoformat(timespec='seconds')
    return True


def reset_failures(station):
    station['fail_count'] = 0
    station.pop('last_failure_counted_at', None)


def select_replacement(session, station, scored, record, now):
    """Filter first, prefer verified HTTPS, and try bounded alternatives."""
    eligible = []
    seen = set()
    diagnostics = record.setdefault('candidates', [])
    for score, candidate in scored:
        url = candidate.get('url_resolved', '')
        reasons = candidate_rejection_reasons(station, candidate, score, now)
        if not reasons and url == station['stream']:
            reasons.append('candidate_same_as_current')
        if not reasons and url in seen:
            reasons.append('duplicate_candidate_url')
        diagnostic = {'name': candidate.get('name'), 'stationuuid': candidate.get('stationuuid'),
                      'url': safe_url(url), 'score': score, 'rejected_by': reasons}
        if valid_url(url):
            diagnostic['stream_protocol'] = urlsplit(url).scheme.upper()
            if diagnostic['stream_protocol'] == 'HTTP':
                diagnostic['security_warning'] = 'unencrypted_http_candidate'
        diagnostics.append(diagnostic)
        if not reasons:
            seen.add(url)
            eligible.append((score, candidate, diagnostic))
    eligible.sort(key=lambda item: (urlsplit(item[1]['url_resolved']).scheme != 'https', -item[0]))
    secure = [item for item in eligible if urlsplit(item[1]['url_resolved']).scheme == 'https']
    insecure = [item for item in eligible if urlsplit(item[1]['url_resolved']).scheme == 'http']
    # Reserve a final HTTP fallback even when the secure shortlist is exhausted.
    shortlist = secure[:MAX_CANDIDATE_CHECKS] + insecure[:1 if secure else MAX_CANDIDATE_CHECKS]
    fallback = None
    for score, candidate, diagnostic in shortlist:
        check = stream_check(session, candidate['url_resolved'])
        record.setdefault('candidate_checks', []).append({'url': safe_url(candidate['url_resolved']),
                                                        'check': check})
        if not check['ok']:
            diagnostic['live_check_failed'] = True
            continue
        if not check.get('http_used'):
            return candidate['url_resolved'], check
        if fallback is None:
            fallback = candidate['url_resolved'], check
    return fallback


def refresh_station(session, station, record, browser_factory, now, *, allow_repair=True):
    check = stream_check(session, station['stream'])
    record['stream_check'] = check
    selected_check = check
    repaired = False
    if check['ok']:
        reset_failures(station)
        record['radio_browser'] = {'skipped': 'stream_is_healthy'}
    else:
        record['failure_counted'] = record_failure(station, now)
        blocked = []
        if not allow_repair:
            blocked.append('report_only_mode')
        if station.get('manual_lock'):
            blocked.append('manual_lock_enabled')
        if station['fail_count'] < 3:
            blocked.append('waiting_for_three_spaced_failures')
        if not check.get('repairable'):
            blocked.append('network_access_or_unverified_media_requires_review')
        if blocked:
            record['radio_browser'] = {'skipped': 'replacement_not_eligible',
                                       'replacement_blocked_by': blocked}
        else:
            browser = browser_factory()
            scored, attempts = browser.search_candidates(station, candidate_score)
            record['radio_browser'] = {'attempts': attempts, 'candidate_count': len(scored)}
            selected = select_replacement(session, station, scored, record, now)
            if selected:
                station['stream'], selected_check = selected
                record['replacement_check'] = selected_check
                reset_failures(station)
                repaired = True
            else:
                record['radio_browser']['replacement_blocked_by'] = ['no_verified_replacement']
    record.update(status='repaired' if repaired else ('ok' if check['ok'] else 'needs_review'),
                  fail_count_after=station['fail_count'], current_stream=safe_url(station['stream']),
                  stream_protocol=urlsplit(station['stream']).scheme.upper())
    record['http_in_use'] = (record['stream_protocol'] == 'HTTP'
                             or bool(selected_check.get('ok') and selected_check.get('http_used')))
    if record['http_in_use'] or check.get('http_used'):
        record['security_warning'] = 'unencrypted_http_audio'
        print('WARNING: HTTP transport used for', station['name'])
    print(station['name'], record['status'], check.get('error_type', ''), check.get('error', ''))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--publish', action='store_true', help='Use GITHUB_REPOSITORY for artwork URLs')
    parser.add_argument('--refresh', action='store_true', help='Check audio and cautiously repair dead URLs')
    parser.add_argument('--report-only', action='store_true', help='Probe streams without changing catalog or playlist')
    args = parser.parse_args()
    if args.report_only and not args.refresh:
        parser.error('--report-only requires --refresh')
    repo = os.environ.get('GITHUB_REPOSITORY', '') if args.publish else ''
    if args.publish and not re.fullmatch(r'[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+', repo):
        parser.error('GITHUB_REPOSITORY must be present, e.g. th3cyrus/Apple')
    reporter = HealthReporter(CURRENT_REPORT, HEALTH_LOG) if args.refresh else None
    session = None
    browser = None
    error = None
    started = time.monotonic()
    try:
        stations = validate_catalog(json.loads(CATALOG.read_text(encoding='utf-8')))
        if reporter:
            reporter.report['expected_total'] = len(stations)
            reporter.checkpoint()
            if not shutil.which('ffprobe') or not shutil.which('ffmpeg'):
                raise RuntimeError('ffprobe and ffmpeg are required before refreshing')
            import requests
            session = requests.Session()
        def get_browser():
            nonlocal browser
            if browser is None:
                browser = RadioBrowserClient(session)
            return browser
        for index, station in enumerate(stations):
            if args.refresh:
                if time.monotonic() - started >= REFRESH_BUDGET_SECONDS:
                    raise TimeoutError('Refresh exceeded its 15-minute processing budget')
                record = {'id': station['id'], 'name': station['name'], 'status': 'checking',
                          'original_stream': safe_url(station['stream']),
                          'fail_count_before': station.get('fail_count', 0)}
                reporter.report['stations'].append(record)
                reporter.checkpoint()
                original = deepcopy(station)
                try:
                    refresh_station(session, station, record, get_browser, datetime.now(timezone.utc),
                                    allow_repair=not args.report_only)
                except Exception as exc:
                    stations[index] = original
                    record.update(status='needs_review', fail_count_after=original.get('fail_count', 0),
                                  current_stream=safe_url(original['stream']),
                                  unexpected_error={'error_type': type(exc).__name__, 'error': safe_message(exc),
                                                    'traceback': safe_message(traceback.format_exc())})
                    print('WARNING: Station processing failed for', original['name'], safe_message(exc))
                reporter.checkpoint()
            if not args.report_only:
                path = LOGOS / (station['id'] + '.svg')
                if not path.exists():
                    LOGOS.mkdir(parents=True, exist_ok=True)
                    # Keep original PNG fallbacks; generate SVG only when missing.
                    temporary = path.with_suffix('.tmp.svg')
                    try:
                        temporary.write_text(artwork_placeholder(station), encoding='utf-8')
                        verify_svg(temporary)
                        os.replace(temporary, path)
                    finally:
                        temporary.unlink(missing_ok=True)
        validate_catalog(stations)
        if not args.report_only:
            generate(stations, repo)
            if args.refresh:
                atomic_json(CATALOG, stations)
        if reporter:
            reporter.report['radio_browser'] = {
                'discovery': browser.discovery if browser else [],
                'servers': browser.servers if browser else [],
                'failed_servers': sorted(browser.failed_servers) if browser else [],
                'skipped': browser is None,
            }
            reporter.report['report_only'] = args.report_only
    except BaseException as exc:
        error = exc
        raise
    finally:
        if session is not None:
            session.close()
        if reporter:
            reporter.finish(error)
            print('Health report:', CURRENT_REPORT, 'summary:', reporter.report['summary'])
    print('Validated', len(stations), 'stations; report-only:', args.report_only)


if __name__ == '__main__':
    main()

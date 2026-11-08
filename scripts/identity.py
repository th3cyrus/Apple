"""Conservative broadcaster/channel matching for directory suggestions."""
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from safety import has_expiring_query, public_media_url, unsupported_stream_suffix, valid_url


def hostname(url):
    try:
        return (urlsplit(url).hostname or '').lower().removeprefix('www.')
    except (ValueError, TypeError, AttributeError):
        return ''


def site_match(first, second):
    a, b = hostname(first), hostname(second)
    if not (a and b and (a == b or a.endswith('.' + b) or b.endswith('.' + a))):
        return False
    # Shared broadcaster hosts may serve unrelated stations on different paths.
    expected = urlsplit(first).path.rstrip('/').lower()
    actual = urlsplit(second).path.rstrip('/').lower()
    return not expected or actual == expected or actual.startswith(expected + '/')


def simplify(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())


def station_identity(station):
    configured = station.get('identity', {})
    calls = re.findall(r'\b[KW][A-Z]{2,3}\b', station.get('search', ''))
    frequencies = re.findall(r'\b\d{2,3}\.\d\b', station['name'])
    return {
        'aliases': configured.get('aliases', [station['name']]),
        'callsigns': configured.get('callsigns', calls),
        'frequency': configured.get('frequency', frequencies[0] if frequencies else None),
        'band': configured.get('band', 'FM'),
        'channel': configured.get('channel', 'main'),
        'verified_stationuuids': configured.get('verified_stationuuids', []),
    }


def identity_reasons(station, candidate):
    identity = station_identity(station)
    name = str(candidate.get('name', ''))
    words = set(re.findall(r'[a-z0-9]+', name.lower()))
    reasons = []
    if identity['band'] == 'FM' and re.search(r'\bam(?:\b|(?=\d))', name, re.I):
        reasons.append('different_band')
    if identity['band'] == 'AM' and re.search(r'\bfm(?:\b|(?=\d))', name, re.I):
        reasons.append('different_band')
    hd = re.search(r'\bhd[ -]?([1-9])\b', name, re.I)
    if hd and identity['channel'] == 'main' and hd[1] != '1':
        reasons.append('different_subchannel')
    if identity['channel'] != 'main' and identity['channel'].lower() not in name.lower():
        reasons.append('different_program_channel')
    for channel in ('jazz', 'classical'):
        if channel in station['name'].lower() and channel not in name.lower():
            reasons.append('different_program_channel')
    frequencies = re.findall(r'\b\d{2,3}\.\d\b', name)
    if identity['frequency'] and frequencies and identity['frequency'] not in frequencies:
        reasons.append('different_frequency')
    callsign = any(call.lower() in words for call in identity['callsigns'])
    exact_alias = any(simplify(alias) == simplify(name) for alias in identity['aliases'])
    verified = (candidate.get('stationuuid') in identity['verified_stationuuids']
                and bool(identity['verified_stationuuids']))
    if not (callsign or exact_alias or verified):
        reasons.append('unverified_station_identity')
    return list(dict.fromkeys(reasons))


def candidate_score(station, candidate):
    if candidate.get('countrycode') != 'US' or candidate.get('lastcheckok') not in (1, True, '1'):
        return -1
    if identity_reasons(station, candidate):
        return -1
    score = 55
    if site_match(station['homepage'], candidate.get('homepage', '')):
        score += 45
    try:
        votes = max(0, int(candidate.get('votes', 0) or 0))
    except (TypeError, ValueError):
        votes = 0
    return score + min(10, votes // 20)


def candidate_rejection_reasons(station, candidate, score, now=None):
    if not isinstance(candidate, dict):
        return ['no_high_confidence_candidate']
    reasons = identity_reasons(station, candidate)
    if score < 90:
        reasons.append('no_high_confidence_candidate')
    if not site_match(station['homepage'], candidate.get('homepage', '')):
        reasons.append('homepage_mismatch')
    if candidate.get('countrycode') != 'US':
        reasons.append('wrong_country')
    if candidate.get('lastcheckok') not in (1, True, '1'):
        reasons.append('not_recently_working')
    url = candidate.get('url_resolved', '')
    if unsupported_stream_suffix(url):
        reasons.append('misleading_stream_suffix')
    if not public_media_url(url):
        reasons.append('invalid_candidate_url')
    elif has_expiring_query(url):
        reasons.append('expiring_candidate_url')
    elif urlsplit(url).scheme == 'https' and candidate.get('ssl_error') not in (0, False, '0'):
        reasons.append('directory_ssl_error')
    try:
        checked = datetime.fromisoformat(candidate['lastchecktime_iso8601'].replace('Z', '+00:00'))
        age = ((now or datetime.now(timezone.utc)) - checked).total_seconds()
        if age < 0 or age > 14 * 86400:
            reasons.append('stale_directory_health_check')
    except (KeyError, AttributeError, TypeError, ValueError):
        reasons.append('missing_directory_check_date')
    return list(dict.fromkeys(reasons))

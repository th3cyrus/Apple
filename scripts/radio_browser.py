"""Resilient Radio Browser discovery and lookup client.

The radio catalog is third-party, crowd-maintained data: API results can
suggest replacements, but the caller must verify broadcaster identity and
test each replacement stream before updating a user-maintained playlist.
"""
import random
import re
import socket
import time

DISCOVERY_URL = 'https://all.api.radio-browser.info/json/servers'
DNS_DISCOVERY_HOST = 'all.api.radio-browser.info'
FALLBACK_SERVERS = (
    'https://all.api.radio-browser.info',
    'https://de1.api.radio-browser.info',
)
USER_AGENT = 'ApplePrimuseRadio/1.1 (https://github.com/th3cyrus/Apple)'


def clean_server_name(value):
    """Never turn untrusted API data into requests to arbitrary hosts."""
    if not isinstance(value, str):
        return ''
    hostname = value.strip().lower().rstrip('.')
    if re.fullmatch(r'[a-z0-9-]+\.api\.radio-browser\.info', hostname):
        return hostname
    return ''


def safe_error(exc):
    """Avoid placing query-string credentials in public error reports."""
    return re.sub(r'(https?://[^\s?]+)\?[^\s)]+', r'\1?[redacted]', str(exc))[:400]


class RadioBrowserClient:
    def __init__(self, session):
        self.session = session
        self.failed_servers = set()
        self.servers, self.discovery = self._discover()

    def _discover(self):
        attempts = []
        found = []
        attempt = {'method': 'mirror_api', 'server': DISCOVERY_URL}
        start = time.monotonic()
        try:
            response = self.session.get(
                DISCOVERY_URL, timeout=(3, 6),
                headers={'User-Agent': USER_AGENT},
            )
            attempt['http_status'] = response.status_code
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError('Radio Browser mirror list is not a JSON array')
            found = sorted({
                host for item in data if isinstance(item, dict)
                for host in [clean_server_name(item.get('name'))] if host
            })
            if not found:
                raise ValueError('Radio Browser returned no valid mirror hosts')
            attempt['result_count'] = len(found)
        except Exception as exc:
            attempt['error_type'] = type(exc).__name__
            attempt['error'] = safe_error(exc)
        finally:
            attempt['elapsed_ms'] = round((time.monotonic()-start)*1000)
            attempts.append(attempt)

        if not found:
            attempt = {'method': 'dns', 'host': DNS_DISCOVERY_HOST}
            start = time.monotonic()
            try:
                answers = socket.getaddrinfo(
                    DNS_DISCOVERY_HOST, 443, type=socket.SOCK_STREAM,
                )
                ips = sorted({answer[4][0] for answer in answers})
                for ip in ips:
                    try:
                        hostname = clean_server_name(socket.gethostbyaddr(ip)[0])
                        if hostname:
                            found.append(hostname)
                    except (OSError, socket.herror):
                        continue
                found = sorted(set(found))
                attempt['addresses'] = len(ips)
                attempt['result_count'] = len(found)
            except Exception as exc:
                attempt['error_type'] = type(exc).__name__
                attempt['error'] = safe_error(exc)
            finally:
                attempt['elapsed_ms'] = round((time.monotonic()-start)*1000)
                attempts.append(attempt)

        random.shuffle(found)
        servers = ['https://' + host for host in found]
        for fallback in FALLBACK_SERVERS:
            if fallback not in servers:
                servers.append(fallback)
        return servers, attempts

    def search(self, station, scorer):
        """Try healthy mirrors and quarantine failures for this run.

        A valid empty/no-match response is not an outage; trying mirrors in
        that situation would amplify API traffic without better evidence.
        """
        attempts = []
        words = re.findall(r'[a-z0-9]+', station['search'].lower())
        meaningful = [word for word in words if word not in ('the', 'radio', 'fm')]
        search_term = meaningful[0] if meaningful else station['search']
        for base in list(self.servers):
            if base in self.failed_servers:
                continue
            attempt = {'server': base}
            started = time.monotonic()
            try:
                response = self.session.get(
                    base + '/json/stations/search',
                    params={
                        'name': search_term, 'countrycode': 'US',
                        'hidebroken': 'true', 'limit': 75,
                        'order': 'votes', 'reverse': 'true',
                    },
                    timeout=(4, 8),
                    headers={'User-Agent': USER_AGENT},
                )
                attempt['http_status'] = response.status_code
                response.raise_for_status()
                records = response.json()
                if not isinstance(records, list):
                    raise ValueError('Station search returned non-list JSON')
                attempt['results'] = len(records)
                scored = sorted(
                    ((scorer(station, rec), rec) for rec in records if isinstance(rec, dict)),
                    key=lambda pair: pair[0], reverse=True,
                )
                score = scored[0][0] if scored else 0
                attempt['candidate_score'] = score
                # Prefer the last responsive mirror for subsequent lookups.
                self.servers.remove(base)
                self.servers.insert(0, base)
                if score >= 55:
                    return score, scored[0][1], attempts
                return 0, None, attempts
            except Exception as exc:
                attempt['error_type'] = type(exc).__name__
                attempt['error'] = safe_error(exc)
                self.failed_servers.add(base)
            finally:
                attempt['elapsed_ms'] = round((time.monotonic()-started)*1000)
                attempts.append(attempt)
        if not attempts:
            attempts.append({
                'error_type': 'NoHealthyMirrors',
                'error': 'All configured mirror hosts failed earlier in this run',
            })
        return 0, None, attempts

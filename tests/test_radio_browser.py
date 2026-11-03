"""Offline regression tests for Radio Browser discovery, failover and repairs."""
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import radio_browser
import update


class Response:
    def __init__(self, payload=None, status=200, mime='application/json'):
        self.payload = payload
        self.status_code = status
        self.headers = {'Content-Type': mime}
        self.reason = 'Test response'

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f'HTTP {self.status_code}')

    def json(self):
        return self.payload


class Session:
    def __init__(self, replies):
        self.replies = list(replies)
        self.urls = []
        self.calls = []

    def get(self, url, **kwargs):
        self.urls.append(url)
        self.calls.append((url, kwargs))
        if not self.replies:
            raise AssertionError(f'Unexpected request: {url}')
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


STATION = {
    'search': 'KEXP',
    'name': 'KEXP 90.3',
    'homepage': 'https://www.kexp.org/',
}
CANDIDATE = {
    'name': 'KEXP 90.3',
    'countrycode': 'US',
    'lastcheckok': 1,
    'ssl_error': 0,
    'homepage': 'https://www.kexp.org/',
    'votes': 200,
    'url_resolved': 'https://example.com/kexp.mp3',
}


class RadioBrowserTests(unittest.TestCase):
    def test_rejects_arbitrary_server_names(self):
        session = Session([
            Response([
                {'name': 'de1.api.radio-browser.info'},
                {'name': 'evil.example.org'},
                {'name': 'de1.api.radio-browser.info'},
                {'name': 'https://attacker.test'},
            ]),
        ])
        browser = radio_browser.RadioBrowserClient(session)
        self.assertEqual(browser.servers, [
            'https://de1.api.radio-browser.info',
            'https://all.api.radio-browser.info',
        ])

    def test_dns_discovery_after_api_failure(self):
        session = Session([ConnectionError('discovery unavailable')])
        with patch.object(radio_browser.socket, 'getaddrinfo', return_value=[
            (None,None,None,None,('192.0.2.1',443)),
        ]), patch.object(radio_browser.socket, 'gethostbyaddr', return_value=(
            'nl1.api.radio-browser.info', [], [],
        )):
            browser = radio_browser.RadioBrowserClient(session)
        self.assertEqual(browser.servers[0], 'https://nl1.api.radio-browser.info')
        self.assertEqual(len(browser.discovery), 2)

    def test_failed_mirror_is_skipped_on_subsequent_lookups(self):
        session = Session([
            Response([{'name': 'de1.api.radio-browser.info'}]),
            ConnectionError('primary temporarily unavailable'),
            Response([CANDIDATE]),
            Response([CANDIDATE]),
        ])
        browser = radio_browser.RadioBrowserClient(session)
        score, candidate, attempts = browser.search(STATION, update.candidate_score)
        self.assertGreaterEqual(score, 90)
        self.assertEqual(candidate['name'], CANDIDATE['name'])
        self.assertEqual(len(attempts), 2)
        self.assertIn('https://de1.api.radio-browser.info', browser.failed_servers)
        _, _, second_attempts = browser.search(STATION, update.candidate_score)
        self.assertEqual(len(second_attempts), 1)
        self.assertEqual(second_attempts[0]['server'], 'https://all.api.radio-browser.info')

    def test_valid_empty_response_does_not_retry(self):
        session = Session([
            Response([{'name': 'de1.api.radio-browser.info'}]),
            Response([]),
        ])
        browser = radio_browser.RadioBrowserClient(session)
        score, candidate, attempts = browser.search(STATION, update.candidate_score)
        self.assertEqual(score, 0)
        self.assertIsNone(candidate)
        self.assertEqual(len(attempts), 1)

    def test_malformed_results_trigger_failover(self):
        session = Session([
            Response([{'name': 'de1.api.radio-browser.info'}]),
            Response({'error': 'unexpected'}),
            Response([CANDIDATE]),
        ])
        browser = radio_browser.RadioBrowserClient(session)
        score, _, attempts = browser.search(STATION, update.candidate_score)
        self.assertGreaterEqual(score, 90)
        self.assertEqual(attempts[0]['error_type'], 'ValueError')

    def test_jazz_does_not_replace_classical(self):
        station = {
            'name': 'WRTI Classical', 'search': 'WRTI Classical',
            'homepage': 'https://www.wrti.org/',
        }
        candidate = dict(CANDIDATE, name='WRTI Jazz', homepage='https://www.wrti.org/')
        self.assertEqual(update.candidate_score(station, candidate), -1)

    def test_the_current_search_has_meaningful_keyword(self):
        session = Session([
            Response([{'name': 'de1.api.radio-browser.info'}]),
            Response([]),
        ])
        browser = radio_browser.RadioBrowserClient(session)
        browser.search({
            'name': 'The Current 89.3', 'search': 'The Current KCMP',
            'homepage': 'https://www.thecurrent.org/',
        }, update.candidate_score)
        self.assertEqual(len(session.urls), 2)
        # Explicitly avoid searching for the overly broad word "the".
        self.assertEqual(session.calls[1][1]['params']['name'], 'current')

    def test_candidate_rejected_if_wrong_website_or_stale(self):
        candidate = dict(CANDIDATE, lastchecktime_iso8601=(
            datetime.now(timezone.utc)-timedelta(days=30)
        ).isoformat())
        reasons = update.candidate_rejection_reasons(STATION, candidate, 110)
        self.assertIn('stale_directory_health_check', reasons)
        candidate['lastchecktime_iso8601'] = datetime.now(timezone.utc).isoformat()
        candidate['homepage'] = 'https://someone-else.org/'
        reasons = update.candidate_rejection_reasons(STATION, candidate, 110)
        self.assertIn('homepage_mismatch', reasons)

    def test_candidate_rejected_if_http_or_ssl_invalid(self):
        candidate = dict(CANDIDATE,
            lastchecktime_iso8601=datetime.now(timezone.utc).isoformat(),
            ssl_error=1, url_resolved='http://example.com/unverified',
        )
        reasons = update.candidate_rejection_reasons(STATION, candidate, 110)
        self.assertIn('directory_ssl_error', reasons)
        self.assertIn('unsafe_or_non_https_url', reasons)

    def test_verified_candidate_meets_all_guards(self):
        candidate = dict(CANDIDATE,
            lastchecktime_iso8601=datetime.now(timezone.utc).isoformat(),
        )
        self.assertEqual(update.candidate_rejection_reasons(STATION, candidate, 110), [])

    def test_malformed_catalog_fields_are_ignored_safely(self):
        candidate = dict(CANDIDATE, votes='not-an-integer', homepage=123)
        self.assertGreaterEqual(update.candidate_score(STATION, candidate), 55)

    def test_stream_check_logs_http_reason(self):
        session = Session([Response(status=403, mime='text/html')])
        result = update.stream_check(session, 'https://example.org/live.mp3')
        self.assertFalse(result['ok'])
        self.assertEqual(result['http_status'], 403)
        self.assertEqual(result['error_type'], 'HTTPStatus')


if __name__ == '__main__':
    unittest.main()

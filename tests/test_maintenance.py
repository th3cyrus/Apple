"""Regression coverage for real bytes, replacement policy and failed runs."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib3.exceptions import ReadTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import catalog
from health_report import HealthReporter
import safety
import stream_probe
import update
import validate
from test_radio_browser import CANDIDATE, STATION, Response, Session, audio_sample

NOW = datetime(2026, 11, 3, 18, tzinfo=timezone.utc)


def station(**changes):
    result = dict(STATION, id='kexp-90-3', group='Independent', stream='https://example.org/old',
                  logo='logos/kexp-90-3.png', fail_count=0, manual_lock=False)
    result.update(changes)
    return result


def candidate(**changes):
    result = dict(CANDIDATE, votes=0, lastchecktime_iso8601=NOW.isoformat())
    result.update(changes)
    return result


class MediaTests(unittest.TestCase):
    def test_empty_audio_body_is_not_healthy(self):
        response = Response(mime='audio/mpeg')
        response.raw = io.BytesIO(b'')
        result = update.stream_check(Session([response]), 'https://example.org/empty.mp3')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'EmptyStream')

    def test_audio_header_with_non_audio_bytes_is_not_healthy(self):
        response = Response(mime='audio/mpeg')
        response.raw = io.BytesIO(b'this is not an audio stream')
        result = update.stream_check(Session([response]), 'https://example.org/fake.mp3')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'UnverifiedMedia')

    def test_unknown_content_type_can_contain_verified_audio(self):
        result = update.stream_check(Session([Response(mime='application/octet-stream')]),
                                     'https://example.org/audio')
        self.assertTrue(result['ok'])
        self.assertGreater(result['audio_packets'], 0)
        self.assertGreaterEqual(result['decoded_seconds'], 0.5)
        self.assertGreater(result['peak_dbfs'], -60)

    def test_intermediate_http_redirect_is_logged(self):
        a, b = Response(status=302), Response(status=302)
        a.headers['Location'] = 'http://example.org/intermediate'
        b.headers['Location'] = 'https://example.org/final'
        result = update.stream_check(Session([a, b, Response(mime='audio/aac')]),
                                     'https://example.org/start')
        self.assertTrue(result['ok'])
        self.assertTrue(result['http_used'])
        self.assertEqual(result['final_protocol'], 'HTTPS')
        self.assertEqual(len(result['attempts'][0]['requests']), 3)

    def test_redirect_credentials_are_never_requested(self):
        response = Response(status=302)
        response.headers['Location'] = 'https://user:password@example.org/private'
        session = Session([response])
        result = update.stream_check(session, 'https://example.org/start')
        self.assertFalse(result['ok'])
        self.assertEqual(len(session.calls), 1)

    def test_invalid_types_do_not_escape_probe(self):
        for value in (None, 123, [], 'https://[broken', 'https://host:bad/stream'):
            with self.subTest(value=value):
                result = update.stream_check(Session([]), value)
                self.assertEqual(result['error_type'], 'InvalidURL')

    def test_network_failure_is_not_permission_to_replace(self):
        result = update.stream_check(Session([Response(status=403)]), 'https://example.org/restricted')
        self.assertFalse(result['repairable'])

    def test_body_read_timeout_retries_and_recovers(self):
        response = Response(mime='audio/mpeg')
        class TimeoutBody:
            def read(self, size):
                raise ReadTimeoutError(None, '/live?token=PRIVATE', 'body stalled')
        response.raw = TimeoutBody()
        with patch.object(stream_probe, 'sleep') as delay:
            result = update.stream_check(Session([response, Response(mime='audio/mpeg')]),
                                         'https://example.org/live')
        self.assertTrue(result['ok'])
        self.assertEqual(len(result['attempts']), 2)
        delay.assert_called_once_with(1)
        self.assertNotIn('PRIVATE', json.dumps(result))


class PlaylistServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = audio_sample()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                routes = {
                    '/media': ('audio/wav', cls.audio),
                    '/audio.m3u': ('audio/mpeg', cls.audio),
                    '/empty': ('audio/mpeg', b''),
                    '/simple.m3u': ('audio/mpegurl', b'#EXTM3U\n/media\n'),
                    '/radio.pls': ('audio/x-scpls', b'[playlist]\nFile1=/media\nNumberOfEntries=1\n'),
                    '/master.m3u8': ('application/vnd.apple.mpegurl', b'#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=128000\n/live.m3u8\n'),
                    '/live.m3u8': ('application/vnd.apple.mpegurl', b'#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\n/media\n'),
                    '/broken.m3u8': ('application/vnd.apple.mpegurl', b'#EXTM3U\n#EXTINF:10,\n/missing\n'),
                    '/loop.m3u': ('audio/mpegurl', b'#EXTM3U\n/loop.m3u\n'),
                    '/encrypted.m3u8': ('audio/mpegurl', b'#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="/key"\n/media\n'),
                }
                if self.path not in routes:
                    self.send_response(404)
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                mime, body = routes[self.path]
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def probe(self, path):
        import requests
        with requests.Session() as session:
            session.trust_env = False
            return update.stream_check(session, self.base + path)

    def test_plain_m3u_and_pls_resolve_media(self):
        for path in ('/simple.m3u', '/radio.pls'):
            with self.subTest(path=path):
                result = self.probe(path)
                self.assertTrue(result['ok'])
                self.assertEqual(len(result['attempts'][0]['requests']), 2)

    def test_playlist_extension_with_actual_audio_is_rejected(self):
        result = self.probe('/audio.m3u')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'PlaylistContentMismatch')

    def test_double_extension_is_rejected_without_network(self):
        result = update.stream_check(Session([]), 'https://example.org/stream.mp3.m3u')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'MisleadingStreamSuffix')
        self.assertTrue(result['repairable'])

    def test_silent_decodable_audio_is_not_healthy(self):
        import wave
        buf = io.BytesIO()
        with wave.open(buf, 'wb') as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(8000)
            handle.writeframes(b'\x00\x00' * 8000)
        response = Response(mime='audio/wav')
        response.raw = io.BytesIO(buf.getvalue())
        result = update.stream_check(Session([response]), 'https://example.org/silent.wav')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'SilentAudio')

    def test_catalog_disallows_double_extension(self):
        with self.assertRaisesRegex(ValueError, 'Misleading audio/playlist'):
            catalog.validate_catalog([station(stream='https://example.org/live.mp3.m3u')])

    def test_directory_rejects_misleading_candidate(self):
        reasons = update.candidate_rejection_reasons(
            station(), candidate(url_resolved='https://example.org/live.mp3.m3u'), 100, NOW)
        self.assertIn('misleading_stream_suffix', reasons)

    def test_hls_master_and_media_segment_are_verified(self):
        result = self.probe('/master.m3u8')
        self.assertTrue(result['ok'])
        self.assertGreater(result['audio_packets'], 0)
        self.assertEqual(len(result['attempts'][0]['requests']), 3)

    def test_hls_with_missing_segment_fails(self):
        result = self.probe('/broken.m3u8')
        self.assertFalse(result['ok'])
        self.assertEqual(result['http_status'], 404)

    def test_cyclic_playlist_is_bounded(self):
        result = self.probe('/loop.m3u')
        self.assertFalse(result['ok'])
        self.assertEqual(result['error_type'], 'PlaylistLoop')

    def test_encrypted_hls_requires_review(self):
        result = self.probe('/encrypted.m3u8')
        self.assertFalse(result['ok'])
        self.assertFalse(result['repairable'])


class ReplacementTests(unittest.TestCase):
    def test_wnyc_am_is_not_wnyc_fm(self):
        target = station(name='WNYC 93.9', search='WNYC', homepage='https://www.wnyc.org/')
        other = candidate(name='WNYC AM 820', homepage='https://www.wnyc.org/')
        self.assertLess(update.candidate_score(target, other), 0)
        self.assertIn('different_band', update.candidate_rejection_reasons(target, other, 110, NOW))
        self.assertLess(update.candidate_score(target, dict(other, name='WNYC AM820')), 0)

    def test_hd2_is_not_primary_fm(self):
        other = candidate(name='KEXP HD2')
        self.assertLess(update.candidate_score(station(), other), 0)

    def test_similar_callsign_is_not_same_station(self):
        target = station(name='KUT 90.5', search='KUT', homepage='https://www.kut.org/')
        other = candidate(name='KUTX 98.9', homepage='https://www.kut.org/')
        self.assertLess(update.candidate_score(target, other), 0)

    def test_shared_website_different_path_is_rejected(self):
        self.assertFalse(update.site_match('https://www.audacy.com/kroq', 'https://www.audacy.com/other'))

    def test_stale_best_candidate_does_not_hide_healthy_runner_up(self):
        stale = candidate(lastchecktime_iso8601=(NOW - timedelta(days=30)).isoformat())
        fresh = candidate(url_resolved='https://example.org/fresh')
        record = {}
        chosen = update.select_replacement(Session([Response(mime='audio/aac')]), station(),
                                            [(110, stale), (100, fresh)], record, NOW)
        self.assertEqual(chosen[0], fresh['url_resolved'])
        self.assertIn('stale_directory_health_check', record['candidates'][0]['rejected_by'])

    def test_https_precedes_higher_scored_http(self):
        https = candidate(url_resolved='https://example.org/secure')
        http = candidate(url_resolved='http://example.org/legacy')
        chosen = update.select_replacement(Session([Response(mime='audio/aac')]), station(),
                                            [(110, http), (100, https)], {}, NOW)
        self.assertEqual(chosen[0], https['url_resolved'])

    def test_failed_first_live_check_does_not_hide_second(self):
        first = candidate(url_resolved='https://example.org/dead')
        second = candidate(url_resolved='https://example.org/working')
        session = Session([Response(status=404), Response(mime='audio/aac')])
        chosen = update.select_replacement(session, station(), [(110, first), (100, second)], {}, NOW)
        self.assertEqual(chosen[0], second['url_resolved'])

    def test_malformed_candidate_does_not_block_valid_candidate(self):
        bad = candidate(url_resolved='https://[broken')
        good = candidate(url_resolved='https://example.org/good')
        chosen = update.select_replacement(Session([Response(mime='audio/aac')]), station(),
                                            [(110, bad), (100, good)], {}, NOW)
        self.assertEqual(chosen[0], good['url_resolved'])

    def test_http_fallback_is_permitted_when_https_fails(self):
        http = candidate(url_resolved='http://example.org/live')
        chosen = update.select_replacement(Session([Response(mime='audio/aac')]), station(), [(100, http)], {}, NOW)
        self.assertTrue(chosen[1]['http_used'])

    def test_http_fallback_is_checked_after_secure_shortlist_fails(self):
        choices = [(100, candidate(url_resolved=f'https://example.org/{index}')) for index in range(3)]
        choices.append((100, candidate(url_resolved='http://example.org/fallback')))
        with patch.object(update, 'stream_check', side_effect=[
                {'ok': False}, {'ok': False}, {'ok': False}, {'ok': True, 'http_used': True}]):
            chosen = update.select_replacement(None, station(), choices, {}, NOW)
        self.assertEqual(chosen[0], 'http://example.org/fallback')

    def test_https_url_with_http_hop_does_not_beat_pure_https(self):
        mixed = candidate(url_resolved='https://example.org/mixed')
        secure = candidate(url_resolved='https://example.org/secure')
        checks = [{'ok': True, 'http_used': True}, {'ok': True, 'http_used': False}]
        with patch.object(update, 'stream_check', side_effect=checks):
            chosen = update.select_replacement(None, station(), [(110, mixed), (100, secure)], {}, NOW)
        self.assertEqual(chosen[0], secure['url_resolved'])

    def test_three_spaced_failures_can_repair_and_reset_counter(self):
        target = station(fail_count=2, last_failure_counted_at=(NOW - timedelta(days=1)).isoformat())
        replacement = candidate(url_resolved='https://example.org/repaired')
        class Browser:
            def search_candidates(self, *args):
                return [(100, replacement)], []
        record = {}
        with patch.object(update, 'stream_check', side_effect=[
                {'ok': False, 'repairable': True}, {'ok': True, 'http_used': False}]):
            update.refresh_station(None, target, record, Browser, NOW)
        self.assertEqual(record['status'], 'repaired')
        self.assertEqual(target['stream'], replacement['url_resolved'])
        self.assertEqual(target['fail_count'], 0)

    def test_maximum_live_candidate_checks_is_bounded(self):
        choices = [(100, candidate(url_resolved=f'https://example.org/{index}')) for index in range(10)]
        with patch.object(update, 'stream_check', return_value={'ok': False}) as probe:
            self.assertIsNone(update.select_replacement(None, station(), choices, {}, NOW))
        self.assertEqual(probe.call_count, 3)

    def test_manual_lock_prevents_directory_lookup(self):
        target = station(manual_lock=True, fail_count=2,
                         last_failure_counted_at=(NOW - timedelta(days=1)).isoformat())
        record = {}
        with patch.object(update, 'stream_check', return_value={'ok': False, 'repairable': True}):
            update.refresh_station(None, target, record,
                                   lambda: self.fail('Locked stream requested directory'), NOW)
        self.assertIn('manual_lock_enabled', record['radio_browser']['replacement_blocked_by'])

    def test_report_only_does_not_attempt_repair(self):
        target = station(fail_count=2, last_failure_counted_at=(NOW - timedelta(days=1)).isoformat())
        record = {}
        with patch.object(update, 'stream_check', return_value={'ok': False, 'repairable': True}):
            update.refresh_station(None, target, record,
                                   lambda: self.fail('Report-only attempted directory repair'),
                                   NOW, allow_repair=False)
        self.assertEqual(target['stream'], 'https://example.org/old')
        self.assertIn('report_only_mode', record['radio_browser']['replacement_blocked_by'])

    def test_retries_and_manual_reruns_cannot_accelerate_failure_counter(self):
        target = station()
        self.assertTrue(update.record_failure(target, NOW))
        self.assertFalse(update.record_failure(target, NOW + timedelta(minutes=1)))
        self.assertFalse(update.record_failure(target, NOW + timedelta(hours=23)))
        self.assertTrue(update.record_failure(target, NOW + timedelta(days=1)))
        self.assertEqual(target['fail_count'], 2)

    def test_legacy_unspaced_counter_restarts(self):
        target = station(fail_count=2)
        update.record_failure(target, NOW)
        self.assertEqual(target['fail_count'], 1)

    def test_success_resets_spaced_failures(self):
        target = station(fail_count=2, last_failure_counted_at=NOW.isoformat())
        record = {}
        with patch.object(update, 'stream_check', return_value={'ok': True}):
            update.refresh_station(None, target, record, lambda: None, NOW)
        self.assertEqual(target['fail_count'], 0)
        self.assertNotIn('last_failure_counted_at', target)


class ReportingAndCatalogTests(unittest.TestCase):
    def test_queries_are_redacted_in_relative_exception_paths(self):
        message = "HTTPSConnectionPool(host='example.org'): url: /live?token=PRIVATE&client=x (timeout)"
        self.assertNotIn('PRIVATE', safety.safe_message(message))

    def test_credentials_and_query_are_not_logged(self):
        text = safety.safe_message('https://user:PRIVATE@example.org/live?key=SECRET')
        self.assertNotIn('PRIVATE', text)
        self.assertNotIn('SECRET', text)

    def test_catalog_rejects_path_traversal_and_wrong_types(self):
        for change in ({'id': '../outside'}, {'manual_lock': 'false'}, {'fail_count': True},
                       {'stream': 123}, {'stream': 'https://user:pass@example.org/'},
                       {'name': 'KEXP\nInjected'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                catalog.validate_catalog([station(**change)])

    def test_catalog_rejects_duplicate_ids(self):
        with self.assertRaises(ValueError):
            catalog.validate_catalog([station(), station()])

    def test_checkpoint_survives_partial_failure_and_retains_30_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            current, history = Path(tmp) / 'current.json', Path(tmp) / 'history.jsonl'
            history.write_text(''.join(json.dumps({'github_run_id': str(i)}) + '\n' for i in range(40)))
            reporter = HealthReporter(current, history)
            reporter.report['stations'].append({'id': 'kexp', 'status': 'ok'})
            reporter.checkpoint()
            self.assertEqual(len(json.loads(current.read_text())['stations']), 1)
            try:
                raise RuntimeError('/live?token=PRIVATE')
            except RuntimeError as exc:
                reporter.finish(exc)
            data = json.loads(current.read_text())
            self.assertEqual(data['status'], 'failed')
            self.assertIn('traceback', data['fatal_error'])
            self.assertNotIn('PRIVATE', current.read_text())
            self.assertEqual(len(history.read_text().splitlines()), 30)

    def test_stale_report_cannot_validate_as_current_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'current.json'
            reporter = HealthReporter(path, Path(tmp) / 'history.jsonl')
            reporter.finish()
            with self.assertRaises(ValueError):
                validate.validate_report(path, 'different-run', allow_partial=True)

    def test_atomic_write_failure_keeps_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'file.txt'; path.write_text('original')
            with patch.object(safety.os, 'replace', side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):
                    safety.atomic_write(path, 'replacement')
            self.assertEqual(path.read_text(), 'original')
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def run_main(self, stations, probe=None, generation_error=False, report_only=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name); (root / 'logos').mkdir()
        cp = root / 'stations.json'; cp.write_text(json.dumps(stations))
        for item in stations:
            (root / item['logo']).write_bytes(b'preserved artwork')
        m3u = root / 'radio.m3u'; m3u.write_text('original playlist')
        current = root / 'current.json'
        session = Session([]); session.close = lambda: None
        arguments = ['update.py', '--refresh'] + (['--report-only'] if report_only else [])
        with patch.multiple(update, ROOT=root, CATALOG=cp, M3U=m3u, LOGOS=root / 'logos',
                            CURRENT_REPORT=current, HEALTH_LOG=root / 'history.jsonl'), \
                patch('requests.Session', return_value=session), \
                patch.object(update, 'stream_check', side_effect=probe or (lambda *a: {'ok': True})), \
                patch.object(sys, 'argv', arguments), contextlib.redirect_stdout(io.StringIO()):
            if generation_error:
                with patch.object(update, 'generate', side_effect=OSError('disk failure')):
                    with self.assertRaises(OSError):
                        update.main()
            else:
                update.main()
        return root, json.loads(current.read_text())

    def test_station_error_does_not_stop_later_stations(self):
        items = [station(), station(id='second', logo='logos/second.png')]
        calls = iter([RuntimeError('unexpected'), {'ok': True}])
        def probe(*args):
            value = next(calls)
            if isinstance(value, Exception):
                raise value
            return value
        root, report = self.run_main(items, probe)
        self.assertEqual([s['status'] for s in report['stations']], ['needs_review', 'ok'])
        self.assertEqual(report['status'], 'complete_with_errors')

    def test_fatal_generation_error_still_saves_current_report(self):
        root, report = self.run_main([station()], generation_error=True)
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(len(report['stations']), 1)
        self.assertEqual((root / 'radio.m3u').read_text(), 'original playlist')

    def test_report_only_does_not_rewrite_catalog_playlist_or_artwork(self):
        original = station(fail_count=2)
        root, report = self.run_main([original], report_only=True)
        self.assertEqual(json.loads((root / 'stations.json').read_text()), [original])
        self.assertEqual((root / 'radio.m3u').read_text(), 'original playlist')
        self.assertEqual((root / original['logo']).read_bytes(), b'preserved artwork')
        self.assertTrue(report['report_only'])


if __name__ == '__main__':
    unittest.main()

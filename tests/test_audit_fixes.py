"""Reproduce integrity gaps found during the repository reliability review."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_us_directory as directory
import check_language_radio as language
import check_world_radio as world
import generate_world_covers as covers
import identity
import safety
import stream_probe
from test_radio_browser import audio_sample
from test_us_directory import record
from test_maintenance import candidate, station, NOW


class WorldMetadataTests(unittest.TestCase):
    def check_modified(self, mutate_catalog=None, mutate_playlist=None):
        stations = json.loads((world.WORLD / 'stations.json').read_text())
        playlist = (world.WORLD / 'radio.m3u').read_text()
        original = deepcopy(stations)
        if mutate_catalog:
            mutate_catalog(stations)
            for old, new in zip(original, stations):
                for field in ('name', 'stream', 'logo'):
                    playlist = playlist.replace(old[field], new[field])
        if mutate_playlist:
            playlist = mutate_playlist(playlist)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'stations.json').write_text(json.dumps(stations))
            (root / 'radio.m3u').write_text(playlist)
            return world.load_and_validate(root)

    def test_wrong_artwork_in_playlist_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'mismatch'):
            self.check_modified(mutate_playlist=lambda text: text.replace(
                '/world-radio/logos/at-fm4.png', '/world-radio/logos/wrong.png'))

    def test_expiring_and_blank_auth_parameters_are_rejected(self):
        for query in ('signature=temporary', 'expires=123', 'token=', 'X-Amz-Signature=x'):
            with self.subTest(query=query), self.assertRaisesRegex(ValueError, 'expiring'):
                self.check_modified(mutate_catalog=lambda stations: stations[0].update(
                    stream=stations[0]['stream'] + '?' + query))

    def test_quoted_station_metadata_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'metadata'):
            self.check_modified(mutate_catalog=lambda stations: stations[0].update(
                name='FM4" group-title="Injected'))


class LanguageMetadataTests(unittest.TestCase):
    def check_modified(self, mutate):
        index = json.loads((language.WORLD / 'languages.json').read_text())[0]
        source = language.WORLD / index['id']
        stations = json.loads((source / 'stations.json').read_text())
        mutate(stations)
        # Keep the published text consistent so only catalog policy is tested.
        original = json.loads((source / 'stations.json').read_text())
        playlist = (source / 'radio.m3u').read_text()
        for old, new in zip(original, stations):
            for field in ('stream', 'logo'):
                playlist = playlist.replace(old[field], new[field])
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / index['id']
            root.mkdir()
            (root / 'stations.json').write_text(json.dumps(stations))
            (root / 'radio.m3u').write_text(playlist)
            return language.check_language(root, index)

    def test_artwork_url_credentials_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'artwork'):
            self.check_modified(lambda stations: stations[0].update(
                logo=stations[0]['logo'].replace('https://', 'https://user:password@')))

    def test_empty_signed_parameter_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Expiring'):
            self.check_modified(lambda stations: stations[0].update(
                stream=stations[0]['stream'] + '?token='))


class DirectoryPublicationTests(unittest.TestCase):
    def test_featured_preview_is_regenerated_from_current_filtered_directory(self):
        records = [record(f'Station {i}', f'https://radio{i}.example.org/live',
                          f'uuid-{i}', votes=i) for i in range(600)]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'stations.json').write_text('[]')
            output = root / 'us-directory'
            output.mkdir()
            (output / 'featured.m3u').write_text('obsolete preview')
            with patch.object(directory, 'get_records', return_value=records):
                files = directory.build(Mock(), output, root / 'stations.json')
            self.assertTrue('featured.m3u' in files)
            preview = (output / 'featured.m3u').read_text()
            self.assertNotIn('obsolete', preview)
            self.assertIn('https://radio599.example.org/live', preview)
            self.assertLessEqual(preview.count('#EXTINF'), 100)
            shard_urls = {line for name, text in files.items() if name.startswith('us-')
                          for line in text.splitlines() if line.startswith('https://')}
            preview_urls = {line for line in preview.splitlines() if line.startswith('https://')}
            self.assertTrue(preview_urls.issubset(shard_urls))
            directory.validate_outputs(output)

    def check_published_mutation(self, mutate):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for source in directory.OUTPUT.glob('*'):
                if source.suffix in ('.m3u', '.json'):
                    shutil.copyfile(source, root / source.name)
            mutate(root)
            directory.validate_outputs(root)

    def test_offline_validation_rejects_wrong_counts(self):
        def mutate(root):
            path = root / 'index.json'
            index = json.loads(path.read_text())
            index['station_count'] += 1
            path.write_text(json.dumps(index))
        with self.assertRaisesRegex(ValueError, 'count mismatch'):
            self.check_published_mutation(mutate)

    def test_offline_validation_rejects_obsolete_featured_entry(self):
        def mutate(root):
            path = root / 'featured.m3u'
            lines = path.read_text().splitlines()
            lines[2] = 'https://obsolete.example.org/live'
            path.write_text('\n'.join(lines) + '\n')
        with self.assertRaisesRegex(ValueError, 'Featured preview'):
            self.check_published_mutation(mutate)

    def test_long_artwork_url_is_preserved_without_truncation(self):
        logo = 'https://images.example.org/' + 'a' * 550 + '.png'
        text = directory.m3u([{'name': 'Long cover', 'group': 'Music',
                               'logo': logo, 'url': 'https://radio.example.org/live'}])
        self.assertIn('tvg-logo="' + logo + '"', text)


class MediaIsolationTests(unittest.TestCase):
    def test_directory_and_repair_reject_internal_hosts(self):
        for url in (
            'https://127.0.0.1/private',
            'http://169.254.169.254/latest/meta-data',
            'https://radio.local/live',
            'https://2130706433/live',
            'https://[::1]/live',
        ):
            with self.subTest(url=url):
                self.assertFalse(safety.public_media_url(url))
                reasons = identity.candidate_rejection_reasons(
                    station(), candidate(url_resolved=url), 100, NOW)
                self.assertIn('invalid_candidate_url', reasons)
                self.assertFalse(directory.public_https(url))
        self.assertTrue(safety.public_media_url('https://radio.example.org/live'))

    def test_auto_repair_does_not_publish_temporary_signed_candidates(self):
        for query in ('token=', 'signature=temporary', 'X-Amz-Signature=temporary'):
            replacement = candidate(url_resolved='https://radio.example.org/live?' + query)
            with self.subTest(query=query):
                reasons = identity.candidate_rejection_reasons(station(), replacement, 100, NOW)
                self.assertIn('expiring_candidate_url', reasons)

    def test_decoder_is_confined_to_supplied_bytes_and_bounded_pcm_duration(self):
        real_run = stream_probe.subprocess.run
        calls = []
        def capture(command, **kwargs):
            calls.append(command)
            return real_run(command, **kwargs)
        with patch.object(stream_probe.subprocess, 'run', side_effect=capture):
            stream_probe.check_audio(audio_sample())
        for command in calls:
            with self.subTest(tool=command[0]):
                self.assertIn('-protocol_whitelist', command)
                self.assertEqual(command[command.index('-protocol_whitelist') + 1], 'pipe')
        decoder = next(command for command in calls if command[0] == 'ffmpeg')
        self.assertIn('-t', decoder)
        self.assertLessEqual(float(decoder[decoder.index('-t') + 1]), 10)

    def test_raw_url_attribute_injection_is_rejected(self):
        for character in ('"', '<', '>', '\\'):
            with self.subTest(character=character):
                self.assertFalse(safety.valid_url('https://radio.example.org/a' + character + 'b'))


class ArtworkCommandTests(unittest.TestCase):
    def test_custom_directory_supplies_catalog_and_shared_cover_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'world-radio'
            root.mkdir()
            stations = [{'id': 'custom-station', 'name': 'Custom'}]
            (root / 'stations.json').write_text(json.dumps(stations))
            with patch.object(sys, 'argv', ['covers', '--directory', str(root)]), \
                    patch.object(covers, 'generate') as generate, \
                    patch.object(covers, 'generate_languages'), \
                    patch.object(covers, 'verify'), \
                    patch.object(covers, 'verify_languages'), \
                    patch.object(covers, 'verify_png'), \
                    patch.object(covers, 'directory_cover') as shared:
                covers.main()
            generate.assert_called_once_with(stations, root, force=False)
            shared.assert_called_once_with(root=root.parent, force=False)

    def test_verify_reports_missing_shared_cover_without_creating_it(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'world-radio'
            root.mkdir()
            (root / 'stations.json').write_text('[]')
            with patch.object(sys, 'argv', ['covers', '--directory', str(root), '--verify']), \
                    patch.object(covers, 'verify'), \
                    patch.object(covers, 'verify_languages'), \
                    self.assertRaisesRegex(ValueError, 'Missing radio artwork'):
                covers.main()
            self.assertFalse((root.parent / 'us-directory').exists())


if __name__ == '__main__':
    unittest.main()

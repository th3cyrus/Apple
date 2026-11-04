"""Offline policy tests for sharded U.S. radio directory generation."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_us_directory as directory


def record(name, url, uuid="uuid-1", **fields):
    data = {
        "stationuuid": uuid, "name": name, "countrycode": "US",
        "lastcheckok": 1, "url_resolved": url, "url": url,
        "tags": "rock", "votes": 12, "favicon": "",
        "ssl_error": 0,
        "lastchecktime_iso8601": datetime.now(timezone.utc).isoformat(),
    }
    data.update(fields)
    return data


class DirectoryTests(unittest.TestCase):
    def test_accepts_healthy_us_https_and_skips_other_countries(self):
        one = record("Example Rock", "https://radio.example.org/live.mp3")
        results = directory.catalog([
            one, record("Wrong country", "https://other.example.org/hi", countrycode="CA"),
            record("Broken", "https://broken.example.org/hi", lastcheckok=0),
            record("HTTP", "http://radio.example.org/live.mp3"),
            record("Misleading", "https://radio.example.org/live.mp3.m3u"),
            record("Playlist bytes unknown", "https://radio.example.org/stream.m3u"),
            one,
        ])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["group"], "Rock & Alternative")

    def test_rejects_private_and_invalid_urls(self):
        for url in ("https://127.0.0.1/live", "https://10.0.0.1/stream",
                    "https://host.local/live", "https://a:b@example.com/live",
                    "https://[::1]/live", "ftp://example.com/live"):
            with self.subTest(url=url):
                self.assertFalse(directory.public_https(url))

    def test_stale_ssl_error_and_signed_urls_are_excluded(self):
        cases = [
            record("Stale", "https://old.example.org/live",
                   lastchecktime_iso8601=(datetime.now(timezone.utc)
                                           - timedelta(days=45)).isoformat()),
            record("SSL", "https://ssl.example.org/live", ssl_error=1),
            record("Token", "https://token.example.org/live?token=123"),
            record("Zeno", "https://zeno.example.org/live?zt=123"),
            record("Key", "https://key.example.org/live?key=123"),
            record("Missing date", "https://missing.example.org/live",
                   lastchecktime_iso8601=""),
        ]
        self.assertEqual(directory.catalog(cases), [])

    def test_bad_vote_count_is_not_a_build_error(self):
        items = directory.catalog([record("Station", "https://station.example.org/live",
                                          votes="invalid")])
        self.assertEqual(items[0]["votes"], 0)

    def test_mass_deletion_is_prevented(self):
        with tempfile.TemporaryDirectory() as temp:
            directory_path = Path(temp) / "us-directory"
            directory_path.mkdir()
            (directory_path / "index.json").write_text(json.dumps({"station_count": 5000}))
            curated = Path(temp) / "stations.json"
            curated.write_text(json.dumps([{"stream": "https://old.example.org/stream"}]))
            response = Mock()
            response.json.return_value = [
                record(f"Station {i}", f"https://radio{i}.example.org/live", f"uuid{i}")
                for i in range(600)
            ]
            session = Mock()
            session.get.return_value = response
            with self.assertRaisesRegex(ValueError, "shrank unexpectedly"):
                directory.build(session, output=directory_path, curated_path=curated)
            self.assertEqual(json.loads((directory_path / "index.json").read_text())
                             ["station_count"], 5000)

    def test_dedupe_curated_stream(self):
        records = [record("A", "https://radio.example.org/live")]
        self.assertEqual(directory.catalog(records, ["https://radio.example.org/live"]), [])

    def test_shards_are_bounded_deterministic(self):
        sample = [record(f"Station {i}", f"https://radio{i}.example.org/live", f"id{i}")
                  for i in range(200)]
        items = directory.catalog(sample)
        shards = directory.split(items)
        self.assertEqual(len(shards), directory.SHARDS)
        self.assertEqual(sum(map(len, shards)), 200)
        self.assertTrue(all(len(s) <= directory.SHARD_MAX for s in shards))
        self.assertEqual(shards, directory.split(items))
        self.assertEqual(directory.m3u(shards[0]).count("#EXTINF"), len(shards[0]))

    def test_rejects_short_source_without_writing_anything(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            catalog = path / "stations.json"
            catalog.write_text(json.dumps([{"stream": "https://original.example.org/live"}]))
            output = path / "us-directory"
            output.mkdir()
            marker = output / "us-01.m3u"
            marker.write_text("old content")
            session = Mock()
            response = Mock()
            response.json.return_value = [record("A", "https://a.example.org/live")]
            session.get.return_value = response
            with self.assertRaises(RuntimeError):
                directory.build(session, output=output, curated_path=catalog)
            self.assertEqual(marker.read_text(), "old content")


if __name__ == "__main__":
    unittest.main()

"""Offline integrity and editorial policy regression tests for language playlists."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from check_language_radio import load_all
from content_filters import is_excluded_program


class LanguageRadioTests(unittest.TestCase):
    def test_subscriptions_are_consistent_and_nonreligious(self):
        entries, stations = load_all()
        self.assertGreaterEqual(len(entries), 9)
        self.assertGreaterEqual(len(stations), 50)
        self.assertEqual(sum(item["count"] for item in entries), len(stations))
        self.assertTrue(all(not is_excluded_program(
            station["name"], station["genre"], station["stream"])
            for station in stations))

    def test_every_language_has_a_separate_stable_playlist(self):
        entries, stations = load_all()
        paths = [x["playlist"] for x in entries]
        self.assertEqual(len(set(paths)), len(paths))
        self.assertTrue(all("/world-radio/" in url for url in paths))

    def test_mutating_stream_without_regenerating_m3u_fails(self):
        source = Path(__file__).resolve().parents[1] / "world-radio"
        index = json.loads((source / "languages.json").read_text())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "languages.json").write_text(json.dumps(index))
            for entry in index:
                language = entry["id"]
                directory = root / language
                directory.mkdir()
                content = (source / language / "stations.json").read_text()
                (directory / "stations.json").write_text(content)
                (directory / "radio.m3u").write_text(
                    (source / language / "radio.m3u").read_text())
            target = root / index[0]["id"] / "stations.json"
            records = json.loads(target.read_text())
            records[0]["stream"] = "https://different.example.org/live"
            target.write_text(json.dumps(records))
            with self.assertRaisesRegex(ValueError, "M3U differs"):
                load_all(root)

    def test_multilingual_religious_programs_are_excluded(self):
        phrases = (
            "إذاعة القرآن الكريم", "Quran Talk", "Christian Gospel FM",
            "Diyanet Radyo", "Радио Православное", "رادیو مسیحی",
            "Ancient Faith Talk", "Sufi Devotional Radio",
            "Kurdish Quran Radio", "German Worship FM",
        )
        self.assertTrue(all(is_excluded_program(name) for name in phrases))
        self.assertFalse(is_excluded_program("Kurdistan 24", "News & Culture"))
        self.assertFalse(is_excluded_program("FIP Jazz", "Music"))


if __name__ == "__main__":
    unittest.main()

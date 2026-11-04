"""World Radio Select schema and playlist regression tests (no network)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_world_radio as world


class WorldRadioTests(unittest.TestCase):
    def test_current_world_catalog_and_playlist(self):
        stations = world.load_and_validate()
        self.assertGreaterEqual(len(stations), 25)
        self.assertGreaterEqual(len({s["country_code"] for s in stations}), 15)

    def test_double_extension_is_rejected(self):
        original = world.load_and_validate()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            item = dict(original[0], stream="https://radio.example.net/live.mp3.m3u")
            entries = [item] + original[1:]
            (path / "stations.json").write_text(json.dumps(entries))
            (path / "radio.m3u").write_text((world.WORLD / "radio.m3u").read_text())
            with self.assertRaisesRegex(ValueError, "Invalid or misleading"):
                world.load_and_validate(path)

    def test_playlist_must_match_catalog(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "stations.json").write_text((world.WORLD / "stations.json").read_text())
            (path / "radio.m3u").write_text("#EXTM3U\n")
            with self.assertRaisesRegex(ValueError, "M3U header / length"):
                world.load_and_validate(path)


if __name__ == "__main__":
    unittest.main()

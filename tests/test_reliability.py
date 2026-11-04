"""Regression tests for complete playlist metadata and actionable health gates."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate import expected_extinf, validate_outputs, validate_report
from check_world_radio import require_audible


class PlaylistMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "logos").mkdir()
        Image.new("RGB", (16, 16), (30, 40, 60)).save(
            self.root / "logos" / "test-station.png", format="PNG")
        self.station = {
            "id": "test-station", "name": "Test Station", "group": "Rock & Alternative",
            "search": "Test Station", "homepage": "https://station.example.net/",
            "stream": "https://station.example.net/radio.mp3",
            "logo": "logos/test-station.png",
        }
        (self.root / "stations.json").write_text(
            json.dumps([self.station]), encoding="utf-8")
        repo = os.environ.get("GITHUB_REPOSITORY") or "th3cyrus/Apple"
        self.extinf = expected_extinf(self.station, repo)
        self.media_url = self.station["stream"]
        self.write_playlist(self.extinf)

    def write_playlist(self, metadata):
        (self.root / "radio.m3u").write_text(
            f"#EXTM3U\n{metadata}\n{self.media_url}\n", encoding="utf-8")

    def test_full_metadata_matches(self):
        self.assertEqual(len(validate_outputs(self.root, minimum=1)), 1)

    def test_wrong_title_is_rejected_even_if_stream_is_the_same(self):
        self.write_playlist(self.extinf.replace("Test Station", "Old Title"))
        with self.assertRaisesRegex(ValueError, "metadata"):
            validate_outputs(self.root, minimum=1)

    def test_wrong_group_or_logo_is_rejected(self):
        for old, new in [("Rock & Alternative", "News & Talk"),
                         ("logos/test-station.png", "logos/wrong.png")]:
            with self.subTest(old=old):
                self.write_playlist(self.extinf.replace(old, new))
                with self.assertRaisesRegex(ValueError, "metadata"):
                    validate_outputs(self.root, minimum=1)


class StreamHealthGateTests(unittest.TestCase):
    def report(self, folder, unhealthy=True):
        stations = [{"id": "one", "status": "ok"},
                    {"id": "two", "status": "needs_review" if unhealthy else "ok"}]
        summary = {"checked": 2, "healthy": 1 if unhealthy else 2,
                   "needs_review": 1 if unhealthy else 0, "station_errors": 0}
        output = Path(folder) / "report.json"
        output.write_text(json.dumps({
            "schema_version": 2,
            "github_run_id": "test-run",
            "status": "complete",
            "expected_total": 2,
            "stations": stations,
            "summary": summary,
        }), encoding="utf-8")
        return output

    def test_unhealthy_station_causes_actionable_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.report(folder, unhealthy=True)
            # Structure remains valid; strict health gate reports the actual issue.
            validate_report(path, "test-run", expected_total=2)
            with self.assertRaisesRegex(ValueError, "two"):
                validate_report(path, "test-run", expected_total=2, require_healthy=True)

    def test_all_healthy_report_passes_strict_gate(self):
        with tempfile.TemporaryDirectory() as folder:
            path = self.report(folder, unhealthy=False)
            report = validate_report(path, "test-run", expected_total=2,
                                     require_healthy=True)
            self.assertEqual(report["summary"]["healthy"], 2)

    def test_world_health_gate_raises_only_when_a_station_fails(self):
        require_audible({"needs_review": 0, "stations": [{"id": "ok", "ok": True}]})
        with self.assertRaisesRegex(ValueError, "broken"):
            require_audible({
                "needs_review": 1,
                "stations": [{"id": "ok", "ok": True}, {"id": "broken", "ok": False}],
            })


class WorldArtworkCoverageTests(unittest.TestCase):
    def test_world_station_artwork_files_exist_and_are_valid(self):
        root = Path(__file__).resolve().parents[1]
        stations = json.loads((root / "world-radio" / "stations.json").read_text(encoding="utf-8"))
        own = [s for s in stations if "/world-radio/logos/" in s["logo"]]
        self.assertEqual(len(own), 68)
        self.assertTrue(all(s["logo"] for s in stations))
        for station in own:
            path = root / "world-radio" / "logos" / (station["id"] + ".png")
            with self.subTest(station=station["id"]):
                self.assertTrue(path.is_file(), f"Missing artwork: {path}")
                with Image.open(path) as image:
                    self.assertEqual(image.size, (512, 512))
                    self.assertEqual(image.format, "PNG")
                    image.verify()


if __name__ == "__main__":
    unittest.main()

"""World Radio Select schema and playlist regression tests (no network)."""
from datetime import datetime, timezone
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_world_radio as world


class WorldRadioTests(unittest.TestCase):
    def test_current_world_catalog_and_playlist(self):
        stations = world.load_and_validate()
        self.assertGreaterEqual(len(stations), 25)
        self.assertGreaterEqual(len({s["country_code"] for s in stations}), 15)

    def test_catalog_excludes_transient_audit_metadata(self):
        stations = world.load_and_validate()
        self.assertTrue(all("verification" not in s for s in stations))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            modified = [dict(station) for station in stations]
            modified[0]["verification"] = "old health result"
            (path / "stations.json").write_text(json.dumps(modified))
            (path / "radio.m3u").write_text((world.WORLD / "radio.m3u").read_text())
            with self.assertRaisesRegex(ValueError, "workflow reports"):
                world.load_and_validate(path)

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



class BroadcastScheduleTests(unittest.TestCase):
    def setUp(self):
        self.station = {
            "id": "th-chula-radio-plus", "name": "Chula Radio Plus",
            "country_code": "TH", "stream": "https://radio.example.org/stream",
        }

    def test_bangkok_broadcast_boundary_is_timezone_aware(self):
        cases = (
            ((2026, 11, 8, 22, 59), True),   # 05:59 next day in Bangkok
            ((2026, 11, 8, 23, 0), False),   # 06:00 next day
            ((2026, 11, 8, 13, 59), False),  # 20:59
            ((2026, 11, 8, 14, 0), True),    # 21:00
        )
        for fields, expected in cases:
            with self.subTest(utc=fields):
                instant = datetime(*fields, tzinfo=timezone.utc)
                self.assertEqual(world.scheduled_off_air(self.station, instant), expected)
        self.assertFalse(world.scheduled_off_air(
            dict(self.station, id="some-other-radio"),
            datetime(2026, 11, 8, 14, 0, tzinfo=timezone.utc)))
        with self.assertRaisesRegex(ValueError, "timezone-aware"):
            world.scheduled_off_air(self.station, datetime(2026, 11, 8, 14, 0))

    def test_off_air_station_is_explicitly_untested_and_no_connection_is_made(self):
        with patch.object(world, "scheduled_off_air", return_value=True), \
                patch.object(world.requests, "Session") as session:
            result = world.probe_one(self.station)
        session.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertTrue(result["skipped"])
        self.assertEqual(result["status"], "scheduled_off_air")
        self.assertIsNone(result["probe"])

    def test_off_air_does_not_count_as_success_or_ci_failure(self):
        off_air = {"id": self.station["id"], "name": self.station["name"],
                   "ok": False, "skipped": True, "status": "scheduled_off_air"}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(world, "probe_one", return_value=off_air), \
                patch.dict(world.os.environ, {"GITHUB_STEP_SUMMARY": ""}):
            output = Path(folder) / "audit.json"
            report = world.audit([self.station], output, workers=1)
            self.assertEqual(json.loads(output.read_text())["skipped_off_air"], 1)
        self.assertEqual(report["passed"], 0)
        self.assertEqual(report["checked"], 0)
        self.assertEqual(report["skipped_off_air"], 1)
        self.assertEqual(report["needs_review"], 0)
        world.require_audible(report)

    def test_on_air_silence_still_fails_strict_gate(self):
        with patch.object(world, "scheduled_off_air", return_value=False), \
                patch.object(world, "stream_check",
                             return_value={"ok": False, "error_type": "SilentAudio"}):
            result = world.probe_one(self.station)
        self.assertFalse(result["ok"])
        self.assertFalse(result.get("skipped", False))
        with self.assertRaisesRegex(ValueError, "th-chula-radio-plus"):
            world.require_audible({"needs_review": 1, "stations": [result]})


if __name__ == "__main__":
    unittest.main()

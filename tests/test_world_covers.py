"""Deterministic, independent station-specific World Radio artwork tests."""
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_world_covers as covers


class WorldCoverTests(unittest.TestCase):
    def test_generated_cover_is_square_and_depends_on_station(self):
        first = {"id": "fr-fip", "name": "FIP", "country_code": "FR",
                 "logo": covers.PREFIX + "fr-fip.png"}
        second = {"id": "fr-fip-jazz", "name": "FIP Jazz", "country_code": "FR",
                  "logo": covers.PREFIX + "fr-fip-jazz.png"}
        with tempfile.TemporaryDirectory() as temp:
            location = Path(temp)
            self.assertEqual(covers.generate([first, second], location), 2)
            with Image.open(location / "logos" / "fr-fip.png") as a:
                self.assertEqual(a.size, (512, 512))
                self.assertEqual(a.format, "PNG")
                first_pixels = a.tobytes()
            with Image.open(location / "logos" / "fr-fip-jazz.png") as b:
                self.assertEqual(b.size, (512, 512))
                self.assertNotEqual(first_pixels, b.tobytes())
            self.assertEqual(covers.generate([first, second], location), 0)

    def test_title_can_wrap_without_failing(self):
        station = {"id": "test-long", "name": "Very Long International National Radio Broadcasting Service",
                   "country_code": "GB"}
        img = covers.cover(station)
        self.assertEqual(img.size, (512, 512))


if __name__ == "__main__":
    unittest.main()

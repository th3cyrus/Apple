"""Regression tests for deterministic, station-specific SVG radio covers."""
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_world_covers as covers
from radio_artwork import cover_svg, fitted_title, verify_svg


class WorldCoverTests(unittest.TestCase):
    def test_generated_covers_are_vector_and_station_specific(self):
        first = {"id": "fr-fip", "name": "FIP", "country_code": "FR",
                 "logo": covers.PREFIX + "fr-fip.svg"}
        second = {"id": "fr-fip-jazz", "name": "FIP Jazz", "country_code": "FR",
                  "logo": covers.PREFIX + "fr-fip-jazz.svg"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(covers.generate([first, second], root), 2)
            a = root / "logos" / "fr-fip.svg"
            b = root / "logos" / "fr-fip-jazz.svg"
            self.assertTrue(verify_svg(a))
            self.assertTrue(verify_svg(b))
            self.assertNotEqual(a.read_text(), b.read_text())
            self.assertEqual(covers.generate([first, second], root), 0)

    def test_owner_supplied_png_remains_untouched_while_svg_is_generated(self):
        with tempfile.TemporaryDirectory() as temp:
            png = Path(temp) / "ir-radio-nic.png"
            svg = Path(temp) / "ir-radio-nic.svg"
            original = b"owner supplied artwork archive"
            png.write_bytes(original)
            station = {"id": "ir-radio-nic", "name": "Radio NIC",
                       "country_code": "IR", "genre": "Talk"}
            self.assertTrue(covers.write_cover(station, svg, force=True))
            self.assertEqual(png.read_bytes(), original)
            self.assertTrue(verify_svg(svg))

    def test_text_is_accessible_and_native_vector_without_embedded_raster(self):
        sample = {"id": "test-contrast", "name": "Radio Mirchi Hindi",
                  "country_code": "IN", "genre": "Hindi Pop & Bollywood"}
        tile = cover_svg(sample)
        self.assertIn('width="1254"', tile)
        self.assertIn('viewBox="0 0 512 512"', tile)
        self.assertIn("Radio Mirchi Hindi", tile)
        self.assertIn('fill="#ffffff"', tile)
        self.assertNotIn("<image", tile)
        root = ET.fromstring(tile)
        self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")

    def test_long_names_wrap_and_xml_metacharacters_are_escaped(self):
        lines, size = fitted_title("Very Long International National Radio Broadcasting Service")
        self.assertLessEqual(len(lines), 3)
        self.assertGreaterEqual(size, 17)
        tile = cover_svg({"id": "test-xml", "name": 'Jazz & Blues <Live>',
                          "country_code": "US", "genre": "News & Culture"})
        self.assertIn("Jazz &amp;", tile)
        ET.fromstring(tile)

    def test_rejects_external_images_or_broken_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.svg"
            path.write_text("<svg", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid SVG"):
                verify_svg(path)
            bad = cover_svg({"id": "test-bad", "name": "Radio"})
            bad = bad.replace("</svg>", '<image href="https://other.example/cover.png"/></svg>')
            path.write_text(bad, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Non-vector"):
                verify_svg(path)


if __name__ == "__main__":
    unittest.main()

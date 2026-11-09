"""Regression tests for deterministic, station-specific SVG radio covers."""
import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_world_covers as covers
from radio_artwork import cover_svg, fitted_title, verify_svg, verify_jpg


class WorldCoverTests(unittest.TestCase):
    def test_generated_covers_are_vector_and_station_specific(self):
        first = {"id": "fr-fip", "name": "FIP", "country_code": "FR",
                 "logo": covers.PREFIX + "fr-fip.jpg"}
        second = {"id": "fr-fip-jazz", "name": "FIP Jazz", "country_code": "FR",
                  "logo": covers.PREFIX + "fr-fip-jazz.jpg"}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.assertEqual(covers.generate([first, second], root), 2)
            a = root / "Covers" / "fr-fip.jpg"
            b = root / "Covers" / "fr-fip-jazz.jpg"
            self.assertTrue(verify_jpg(a))
            self.assertTrue(verify_jpg(b))
            self.assertNotEqual(a.read_bytes(), b.read_bytes())
            self.assertEqual(covers.generate([first, second], root), 0)

    def test_existing_svg_is_preserved_unless_force_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            svg = Path(temp) / "ir-radio-nic.jpg"
            station = {"id": "ir-radio-nic", "name": "Radio NIC",
                       "country_code": "IR", "genre": "Talk"}
            self.assertTrue(covers.write_cover(station, svg))
            original = svg.read_bytes()
            self.assertFalse(covers.write_cover(station, svg))
            self.assertEqual(svg.read_bytes(), original)
            self.assertTrue(verify_jpg(svg))


    def test_text_is_accessible_and_native_vector_without_embedded_raster(self):
        sample = {"id": "test-contrast", "name": "Radio Mirchi Hindi",
                  "country_code": "IN", "genre": "Hindi Pop & Bollywood"}
        tile = cover_svg(sample)
        self.assertIn('width="1254"', tile)
        self.assertIn('viewBox="0 0 512 512"', tile)
        self.assertIn("Radio Mirchi Hindi", tile)
        self.assertIn('fill="#ffffff"', tile)
        self.assertNotIn('d="M205 150H307"', tile)
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

    def test_three_line_title_does_not_overlap_header_or_subtitle(self):
        from radio_artwork import (TITLE_TOP, TITLE_BOTTOM, TITLE_MAX_WIDTH,
                                   TITLE_ASCENT, TITLE_DESCENT, _width, title_layout)
        for name in (
            "88Nine Radio Milwaukee",
            "Very Long International National Radio Broadcasting Service",
            "BBC Radio 6 Music",
            "Jazz & Blues Live Radio",
            "United Kingdom Alternative Rock",
            "Classical Music Community Radio Station",
        ):
            with self.subTest(station=name):
                lines, fontsize, first_baseline, advance = title_layout(name)
                self.assertTrue(1 <= len(lines) <= 3)
                self.assertLessEqual(max(_width(line, fontsize) for line in lines),
                                     TITLE_MAX_WIDTH)
                self.assertGreaterEqual(first_baseline - fontsize * TITLE_ASCENT,
                                        TITLE_TOP - 1)
                self.assertLessEqual(first_baseline + (len(lines) - 1) * advance
                                     + fontsize * TITLE_DESCENT, TITLE_BOTTOM + 1)
                svg = cover_svg({"id": "test-overlap", "name": name, "language": "USA"})
                self.assertIn("LIVE RADIO", svg)
                root = ET.fromstring(svg)
                text_nodes = [node for node in root.iter() if node.tag.endswith("}text")]
                rendered = [node for node in text_nodes if node.get("font-weight") == "750"]
                self.assertEqual(len(rendered), len(lines))
                self.assertEqual(float(rendered[0].get("y")), round(first_baseline))

    def test_all_curated_station_titles_fit_reserved_zone(self):
        import json
        root = Path(__file__).resolve().parents[1]
        from radio_artwork import (TITLE_TOP, TITLE_BOTTOM, TITLE_MAX_WIDTH,
                                   TITLE_ASCENT, TITLE_DESCENT, _width, title_layout)
        catalogs = [root / "stations.json", root / "world-radio" / "stations.json"]
        catalogs.extend(sorted((root / "world-radio").glob("*/stations.json")))
        for catalog in catalogs:
            for station in json.loads(catalog.read_text(encoding="utf-8")):
                name = station.get("artwork_title") or station["name"]
                with self.subTest(catalog=str(catalog), name=name):
                    lines, size, baseline, advance = title_layout(name)
                    self.assertLessEqual(len(lines), 3)
                    self.assertLessEqual(max(_width(x, size) for x in lines),
                                         TITLE_MAX_WIDTH + .1)
                    self.assertGreaterEqual(baseline - TITLE_ASCENT * size,
                                            TITLE_TOP - 1)
                    self.assertLessEqual(baseline + (len(lines) - 1) * advance
                                         + TITLE_DESCENT * size, TITLE_BOTTOM + 1)

    def test_rejects_external_images_or_broken_xml(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.svg"
            path.write_text("<svg", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid SVG"):
                verify_svg(path)
            bad = cover_svg({"id": "test-bad", "name": "Radio"})
            bad = bad.replace("</svg>", '<image href="https://other.example/cover.svg"/></svg>')
            path.write_text(bad, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Non-vector"):
                verify_svg(path)


if __name__ == "__main__":
    unittest.main()

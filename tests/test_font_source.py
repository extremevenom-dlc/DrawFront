"""A font exported by DrawFont (phone or PC) carries its own drawings, so it can be reopened anywhere."""
import os
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "android", "app", "src", "main", "python"))

import fontcore as fc  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402


def full_alphabet_project():
    """Worst-case size: every one of the 94 slots drawn with a wobbly, densely sampled stroke."""
    import math
    import random
    rnd = random.Random(3)
    p = fc.Project.new_pua("Full Hand")
    p.settings["latin_aliases"] = True
    for i, ch in enumerate(p.charset):
        pts = [(300 + 250 * math.cos(t / 20.0) + rnd.uniform(-2, 2), 300 + 250 * math.sin(t / 20.0) + rnd.uniform(-2, 2))
               for t in range(130)]
        p.add_stroke(ch, pts, 40 + i % 30)
    p.add_chars("é")
    return p


def one_glyph_project(name="X"):
    p = fc.Project.new_pua(name)
    p.add_stroke(chr(0xE000), [(0, 0), (150, 700), (300, 0)], 50)
    return p


class RoundTripTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name="f.ttf"):
        return os.path.join(self.tmp.name, name)

    def test_everything_survives_the_trip(self):
        p = full_alphabet_project()
        fc.build_font(p, self.path())
        q = fc.Project.from_font(self.path())
        self.assertEqual(q.to_dict(), p.to_dict())            # strokes, labels, keys, settings, name, pua flag
        self.assertTrue(q.pua)
        self.assertEqual(q.keymap, p.keymap)
        self.assertEqual(q.new_symbol("next"), chr(0xE05F))    # keeps counting where the phone stopped

    def test_font_stays_a_normal_font(self):
        p = full_alphabet_project()
        fc.build_font(p, self.path("with.ttf"))
        fc.build_font(p, self.path("without.ttf"), embed_source=False)
        a, b = TTFont(self.path("with.ttf")), TTFont(self.path("without.ttf"))
        self.assertIn("DRFT", a)
        self.assertNotIn("DRFT", b)
        self.assertEqual(a.getBestCmap(), b.getBestCmap())
        self.assertEqual(a["glyf"].keys(), b["glyf"].keys())
        for name in a["glyf"].keys():
            self.assertEqual(a["hmtx"][name], b["hmtx"][name])
        self.assertLess(os.path.getsize(self.path("with.ttf")) - os.path.getsize(self.path("without.ttf")), 150_000)

    def test_exporting_from_an_opened_font_gives_the_same_font(self):
        p = full_alphabet_project()
        fc.build_font(p, self.path("a.ttf"))
        fc.build_font(fc.Project.from_font(self.path("a.ttf")), self.path("b.ttf"))
        a, b = TTFont(self.path("a.ttf")), TTFont(self.path("b.ttf"))
        self.assertEqual(a.getBestCmap(), b.getBestCmap())
        for name in a["glyf"].keys():
            self.assertEqual(a["glyf"][name].coordinates if a["glyf"][name].numberOfContours else None,
                             b["glyf"][name].coordinates if b["glyf"][name].numberOfContours else None)

    def test_keyboard_layout_can_be_made_from_the_font_alone(self):
        import kblayout
        fc.build_font(one_glyph_project("Kb"), self.path())
        q = fc.Project.from_font(self.path())
        self.assertIn("e01a", kblayout.build_klc("Kb", q.keymap))

    def test_android_bridge_reads_fonts(self):
        import json
        import bridge
        p = full_alphabet_project()
        fc.build_font(p, self.path())
        d = json.loads(bridge.project_json_from_font(self.path()))
        self.assertEqual(d["glyphs"][chr(0xE000)][0]["pts"][0], p.glyphs[chr(0xE000)][0]["pts"][0])
        self.assertEqual(d["keymap"], p.keymap)


class BadInputTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "f.ttf")
        fc.build_font(one_glyph_project(), self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def tamper(self, payload):
        f = TTFont(self.path)
        f["DRFT"].data = payload
        f.save(self.path)

    def test_not_a_drawfont_font(self):
        f = TTFont(self.path)
        del f["DRFT"]
        f.save(self.path)
        with self.assertRaises(ValueError) as cm:
            fc.Project.from_font(self.path)
        self.assertIn("not made with DrawFont", str(cm.exception))

    def test_damaged_payloads(self):
        for payload in (b"DRF1garbage", b"XXXX" + b"\x00" * 10, b"DRF1" + zlib.compress(b"not json"),
                        b"DRF1" + zlib.compress(b'{"format": "something else"}'), b""):
            self.tamper(payload)
            with self.assertRaises(ValueError, msg=repr(payload[:12])):
                fc.Project.from_font(self.path)

    def test_decompression_bomb_is_refused(self):
        self.tamper(b"DRF1" + zlib.compress(b"0" * (80 * 1024 * 1024), 9))
        with self.assertRaises(ValueError):
            fc.Project.from_font(self.path)

    def test_not_a_font_at_all(self):
        with open(self.path, "wb") as f:
            f.write(b"hello, I am a text file")
        with self.assertRaises(ValueError):
            fc.Project.from_font(self.path)
        with self.assertRaises(ValueError):
            fc.Project.from_font(os.path.join(self.tmp.name, "missing.ttf"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

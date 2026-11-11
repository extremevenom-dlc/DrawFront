import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fontcore as fc  # noqa: E402
import kblayout as kb  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402


def sample():
    p = fc.Project("My Script")
    p.settings["smoothing"] = 0
    ka = p.new_symbol("ka", "k")
    ki = p.new_symbol("KI", "K")
    p.add_stroke(ka, [(0, 0), (0, 600), (250, 300), (0, 300)], 50)
    p.add_stroke(ki, [(0, 0), (300, 600), (600, 0)], 50)
    p.add_stroke("A", [(0, 0), (150, 700), (300, 0)], 50)
    return p, ka, ki


class SymbolTests(unittest.TestCase):
    def test_symbols_get_private_use_codepoints(self):
        p, ka, ki = sample()
        self.assertEqual((ord(ka), ord(ki)), (0xE000, 0xE001))
        self.assertEqual(p.display_name(ka), "ka")
        self.assertEqual(p.display_name("A"), "A")
        self.assertIn(ka, p.charset)

    def test_keymap_rules(self):
        p, ka, ki = sample()
        self.assertEqual(p.keymap, {"k": ka, "K": ki})
        p.set_key(ki, "k")                       # steals key from ka, drops KI's old key
        self.assertEqual(p.keymap, {"k": ki})
        p.set_key(ki, "")
        self.assertEqual(p.keymap, {})
        with self.assertRaises(ValueError):
            p.set_key(ka, "ab")
        with self.assertRaises(ValueError):
            p.new_symbol("bad", "  x y")
        n = len(p.charset)
        with self.assertRaises(ValueError):
            p.new_symbol("bad", "ab")
        self.assertEqual(len(p.charset), n)      # failed add must not leave a half-made symbol

    def test_translate(self):
        p, ka, ki = sample()
        self.assertEqual(p.translate("kK x"), ka + ki + " x")

    def test_roundtrip_keeps_labels_and_keys(self):
        p, ka, ki = sample()
        q = fc.Project.from_dict(p.to_dict())
        self.assertEqual(q.labels, p.labels)
        self.assertEqual(q.keymap, p.keymap)
        self.assertEqual(q.new_symbol("next"), chr(0xE002))

    def test_old_project_files_still_load(self):
        d = {"format": fc.PROJECT_FORMAT, "version": 1, "name": "Old", "settings": {},
             "charset": "AB", "glyphs": {"A": [{"w": 40, "pts": [[0, 0], [10, 10]]}]}}
        q = fc.Project.from_dict(d)
        self.assertEqual(q.keymap, {})
        self.assertTrue(q.strokes("A"))

    def test_font_contains_private_use_glyphs(self):
        p, ka, ki = sample()
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "s.ttf")
            fc.build_font(p, path)
            f = TTFont(path)
            cmap = f.getBestCmap()
            for cp in (0xE000, 0xE001, ord("A"), 32):
                self.assertIn(cp, cmap)
            from PIL import Image, ImageDraw, ImageFont
            im = Image.new("L", (500, 500), 0)
            ImageDraw.Draw(im).text((50, 400), ka, font=ImageFont.truetype(path, 400), fill=255, anchor="ls")
            self.assertGreater(sum(im.histogram()[128:]), 500)   # glyph really renders


class PngTests(unittest.TestCase):
    def test_png_transparent_and_white(self):
        from PIL import Image
        p, ka, ki = sample()
        with tempfile.TemporaryDirectory() as d:
            a, b = os.path.join(d, "a.png"), os.path.join(d, "b.png")
            w, h = fc.render_png(p, "kK A\nA", a, height=200)
            im = Image.open(a)
            self.assertEqual(im.size, (w, h))
            self.assertEqual(im.mode, "RGBA")
            self.assertEqual(im.getpixel((0, 0))[3], 0)            # corner transparent
            self.assertGreater(im.getchannel("A").getextrema()[1], 250)   # ink is opaque
            fc.render_png(p, "kK", b, background=(255, 255, 255), use_keymap=True)
            self.assertEqual(Image.open(b).getpixel((0, 0)), (255, 255, 255, 255))

    def test_png_errors(self):
        p, _, _ = sample()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                fc.render_png(p, "zzz", os.path.join(d, "x.png"))
            with self.assertRaises(ValueError):
                fc.render_png(p, "A" * 4000, os.path.join(d, "x.png"), height=400)


class KeyboardTests(unittest.TestCase):
    def test_klc_structure(self):
        p, ka, ki = sample()
        text = kb.build_klc("My Script", p.keymap)
        lines = text.split("\r\n")
        self.assertTrue(lines[0].startswith("KBD\tMyScript\t"))
        self.assertEqual(lines[-2], "ENDKBD")
        row_k = next(l for l in lines if l.startswith("25\t"))      # scancode 0x25 = K key
        self.assertTrue(row_k.startswith("25\tK\t0\te000\te001"))
        row_a = next(l for l in lines if l.startswith("1e\t"))      # unmapped A keeps US letters, Caps works
        self.assertTrue(row_a.startswith("1e\tA\t1\t0061\t0041"))
        self.assertEqual(sum(1 for l in lines if l and l[0] in "0123456789abcdef" and l[2:3] == "\t" and len(l.split("\t")) >= 5), 48)

    def test_klc_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            kb.build_klc("x", {"é": ""})
        with self.assertRaises(ValueError):
            kb.build_klc("x", {"k": "ab"})
        with self.assertRaises(ValueError):
            kb.build_klc("x", {"k": "\U0001F600"})

    def test_klc_file_is_utf16(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "k.klc")
            kb.write_klc(path, "Name", {"a": ""})
            with open(path, "rb") as f:
                raw = f.read()
            self.assertIn(raw[:2], (b"\xff\xfe", b"\xfe\xff"))
            self.assertIn("KBD\tName", raw.decode("utf-16"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

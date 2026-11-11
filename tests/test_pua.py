import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fontcore as fc  # noqa: E402
import kblayout as kb  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402


def pua(key):
    return chr(0xE000 + fc.DEFAULT_CHARSET.index(key))


def drawn_project():
    p = fc.Project.new_pua("My Script")
    p.settings["smoothing"] = 0
    p.add_stroke(pua("a"), [(0, 0), (0, 500), (250, 250)], 50)
    p.add_stroke(pua("A"), [(0, 0), (150, 700), (300, 0)], 50)
    p.add_stroke(pua("1"), [(0, 0), (0, 700)], 50)
    return p


class TableTests(unittest.TestCase):
    def test_fixed_codepoint_table(self):
        p = fc.Project.new_pua()
        self.assertTrue(p.pua)
        self.assertEqual(len(p.charset), 94)
        self.assertEqual(len(set(p.charset)), 94)
        self.assertEqual(ord(pua("A")), 0xE000)
        self.assertEqual(ord(pua("Z")), 0xE019)
        self.assertEqual(ord(pua("a")), 0xE01A)
        self.assertEqual(ord(pua("z")), 0xE033)
        self.assertEqual(ord(pua("0")), 0xE034)
        self.assertEqual(ord(pua("9")), 0xE03D)
        self.assertEqual(ord(pua(".")), 0xE03E)
        self.assertEqual(ord(pua("`")), 0xE05D)
        for ch in p.charset:
            self.assertTrue(0xE000 <= ord(ch) <= 0xF8FF)

    def test_every_us_qwerty_key_is_covered(self):
        p = fc.Project.new_pua()
        self.assertEqual(set(p.keymap), kb.MAPPABLE)                     # all 94 typeable characters
        self.assertEqual(set(p.keymap.values()), set(p.charset))
        self.assertEqual(p.labels[pua("a")], "a")
        self.assertEqual(p.display_name(pua("Q")), "Q")

    def test_translate_gives_only_private_use_chars(self):
        p = fc.Project.new_pua()
        out = p.translate("Hello, World 42!")
        spaces = out.count(" ")
        self.assertEqual(spaces, 2)
        self.assertTrue(all(0xE000 <= ord(c) <= 0xF8FF for c in out if c != " "))


class FontTests(unittest.TestCase):
    def build(self, **settings):
        p = drawn_project()
        p.settings.update(settings)
        d = tempfile.mkdtemp()
        path = os.path.join(d, "f.ttf")
        fc.build_font(p, path)
        return p, TTFont(path), path

    def test_font_holds_only_private_use_glyphs(self):
        _, f, _ = self.build()
        cps = set(f.getBestCmap())
        self.assertEqual(cps, {32, ord(pua("a")), ord(pua("A")), ord(pua("1"))})
        self.assertFalse(any(ord(c) in cps for c in "aA1"))              # nothing mapped to Latin

    def test_aliases_are_opt_in_and_share_the_same_glyph(self):
        _, f, _ = self.build(latin_aliases=True)
        cmap = f.getBestCmap()
        for key in "aA1":
            self.assertEqual(cmap[ord(key)], cmap[ord(pua(key))])
        self.assertNotIn(ord("b"), cmap)                                 # undrawn stays absent

    def test_glyph_renders(self):
        from PIL import Image, ImageDraw, ImageFont
        _, _, path = self.build()
        im = Image.new("L", (500, 500), 0)
        ImageDraw.Draw(im).text((50, 400), pua("A"), font=ImageFont.truetype(path, 400), fill=255, anchor="ls")
        self.assertGreater(sum(im.histogram()[128:]), 500)

    def test_png_uses_keyboard_translation(self):
        from PIL import Image
        p = drawn_project()
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x.png")
            fc.render_png(p, "aA1", out, height=120, use_keymap=True)
            self.assertGreater(Image.open(out).getchannel("A").getextrema()[1], 250)
            with self.assertRaises(ValueError):                           # raw Latin text has no glyphs
                fc.render_png(p, "aA1", out, height=120, use_keymap=False)


class KeyboardTests(unittest.TestCase):
    def test_klc_is_standard_qwerty_with_every_key_on_its_code_point(self):
        p = fc.Project.new_pua()
        lines = kb.build_klc("My Script", p.keymap).split("\r\n")
        rows = {l.split("\t")[0]: l.split("\t") for l in lines
                if len(l.split("\t")) >= 5 and len(l.split("\t")[0]) == 2 and l[0] in "0123456789abcdef"}
        for sc, vk, base, shift in kb._ROWS:
            if base == " ":
                continue
            fields = rows[sc]
            self.assertEqual(fields[1], vk)                                # physical key unchanged: QWERTY
            self.assertEqual(int(fields[3], 16), ord(pua(base)), f"{vk} base")
            self.assertEqual(int(fields[4], 16), ord(pua(shift)), f"{vk} shift")
        self.assertEqual(int(rows["39"][3], 16), 0x20)                     # space bar stays a space

    def test_q_key_is_in_qwerty_position(self):
        p = fc.Project.new_pua()
        lines = kb.build_klc("x", p.keymap).split("\r\n")
        q = next(l for l in lines if l.startswith("10\t"))
        self.assertTrue(q.startswith("10\tQ\t0\t"))                        # scancode 0x10 is the Q key


class ExtraCharTests(unittest.TestCase):
    def test_extra_characters_become_new_private_use_symbols(self):
        p = fc.Project.new_pua()
        added = p.add_chars("é অ A")                                       # 'A' already exists -> skipped
        self.assertEqual([ord(c) for c in added], [0xE05E, 0xE05F])
        self.assertEqual(p.display_name(added[0]), "é")
        self.assertEqual(p.add_chars("é"), [])                              # no duplicates
        kb.build_klc("x", p.keymap)                                         # keyboard file still valid

    def test_roundtrip_keeps_pua_mode(self):
        p = drawn_project()
        q = fc.Project.from_dict(p.to_dict())
        self.assertTrue(q.pua)
        self.assertEqual([ord(c) for c in q.add_chars("é")], [0xE05E])
        self.assertEqual(q.keymap, p.keymap)

    def test_old_plain_projects_are_not_pua(self):
        q = fc.Project.from_dict({"format": fc.PROJECT_FORMAT, "version": 1, "charset": "AB"})
        self.assertFalse(q.pua)
        self.assertEqual(q.add_chars("C"), ["C"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

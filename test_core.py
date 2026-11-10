import math
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fontcore as fc  # noqa: E402
from fontTools.ttLib import TTFont  # noqa: E402


def circle_pts(cx, cy, r, n=60, jitter=0.0):
    import random
    rnd = random.Random(1)
    return [[cx + r * math.cos(2 * math.pi * k / n) + rnd.uniform(-jitter, jitter),
             cy + r * math.sin(2 * math.pi * k / n) + rnd.uniform(-jitter, jitter)]
            for k in range(n + 1)]


def make_project(smoothing=0):
    p = fc.Project("Test Hand")
    p.settings["smoothing"] = smoothing
    p.add_stroke("A", [(0, 0), (150, 700), (300, 0)], 50)
    p.add_stroke("A", [(60, 250), (240, 250)], 50)
    p.add_stroke("O", circle_pts(200, 350, 300 - 150, jitter=0.0), 50)
    p.add_stroke("L", [(0, 700), (0, 0), (300, 0)], 60)          # sharp corner
    p.add_stroke("i", [(0, 0), (0, 500)], 50)
    p.add_stroke("i", [(0, 650)], 70)                            # a tap = dot
    p.add_stroke(".", [(0, 0)], 80)
    return p


class GeometryTests(unittest.TestCase):
    def test_all_polygons_clockwise(self):
        for ch, strokes in make_project().glyphs.items():
            for poly in fc.glyph_polygons(strokes, 2):
                self.assertLessEqual(fc._area(poly), 1e-6, f"{ch}: contour not clockwise")

    def test_single_point_is_dot(self):
        polys = fc.stroke_polygons([(10, 10)], 40)
        self.assertEqual(len(polys), 1)
        minx, miny, maxx, maxy = fc.bounds(polys)
        self.assertAlmostEqual(maxx - minx, 40, delta=1)

    def test_long_stroke_no_recursion_error(self):
        pts = [(i * 0.3, math.sin(i / 40.0) * 100) for i in range(20000)]
        self.assertGreater(len(fc.stroke_polygons(pts, 30, 2)), 2)

    def test_spacing_modes(self):
        p = make_project()
        _, dx, adv = p.geometry("L")
        minx, _, maxx, _ = fc.bounds(p.geometry("L")[0])
        self.assertAlmostEqual(minx + dx, p.settings["sidebearing"], places=3)
        self.assertAlmostEqual(adv, (maxx - minx) + 2 * p.settings["sidebearing"], places=3)
        p.settings["spacing"] = "fixed"
        _, dx, adv = p.geometry("L")
        self.assertEqual(adv, p.settings["fixed_advance"])
        minx, _, maxx, _ = fc.bounds(p.geometry("L")[0])
        self.assertAlmostEqual((minx + maxx) / 2 + dx, adv / 2, places=3)


class EditingTests(unittest.TestCase):
    def test_undo_redo_semantics(self):
        p = fc.Project()
        p.add_stroke("A", [(0, 0), (10, 10)], 40)
        p.add_stroke("B", [(0, 0), (10, 10)], 40)
        self.assertEqual(p.undo(), "B")
        self.assertFalse(p.strokes("B"))
        self.assertEqual(p.undo(), "A")
        self.assertFalse(p.strokes("A"))
        self.assertIsNone(p.undo())

    def test_erase_near_and_undo(self):
        p = fc.Project()
        p.add_stroke("A", [(0, 0), (500, 0)], 40)
        p.add_stroke("A", [(0, 400), (500, 400)], 40)
        self.assertFalse(p.erase_near("A", 250, 200, 20))
        self.assertTrue(p.erase_near("A", 250, 10, 5))
        self.assertEqual(len(p.strokes("A")), 1)
        p.undo()
        self.assertEqual(len(p.strokes("A")), 2)

    def test_clear_and_undo(self):
        p = make_project()
        p.clear("A")
        self.assertFalse(p.strokes("A"))
        p.undo()
        self.assertEqual(len(p.strokes("A")), 2)

    def test_cache_invalidated_on_edit(self):
        p = fc.Project()
        p.add_stroke("A", [(0, 0), (100, 0)], 40)
        w1 = p.geometry("A")[2]
        p.add_stroke("A", [(0, 0), (400, 0)], 40)
        self.assertGreater(p.geometry("A")[2], w1)

    def test_project_roundtrip(self):
        p = make_project(smoothing=3)
        p.add_chars("é অ")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "x.json")
            p.save(path)
            q = fc.Project.load(path)
        self.assertEqual(q.name, "Test Hand")
        self.assertEqual(q.settings["smoothing"], 3)
        self.assertEqual(q.glyphs["A"], p.glyphs["A"])
        self.assertIn("অ", q.charset)

    def test_bad_project_file(self):
        with self.assertRaises(ValueError):
            fc.Project.from_dict({"hello": 1})

    def test_layout_uses_space_and_gaps(self):
        p = make_project()
        _, adv_a = p.layout("A")
        _, adv_aa = p.layout("A A")
        self.assertAlmostEqual(adv_aa, 2 * adv_a + p.settings["space_width"], places=3)
        _, adv_missing = p.layout("Z")          # not drawn -> placeholder gap
        self.assertEqual(adv_missing, 500)


class ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "t.ttf")
        self.project = make_project(smoothing=0)
        self.info = fc.build_font(self.project, self.path)
        self.font = TTFont(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_font_structure(self):
        f = self.font
        self.assertEqual(self.info["glyphs"], 5)
        cmap = f.getBestCmap()
        for ch in "AOLi.":
            self.assertIn(ord(ch), cmap)
        self.assertIn(32, cmap)
        self.assertEqual(f["head"].unitsPerEm, 1000)
        self.assertEqual(f["name"].getDebugName(1), "Test Hand")
        self.assertEqual(f["name"].getDebugName(6), "TestHand-Regular")
        self.assertEqual(f["hmtx"]["space"][0], self.project.settings["space_width"])

    def test_metrics_match_geometry(self):
        for ch in "AOLi.":
            _, dx, adv = self.project.geometry(ch)
            name = self.font.getBestCmap()[ord(ch)]
            self.assertEqual(self.font["hmtx"][name][0], int(round(adv)))
            self.assertEqual(self.font["hmtx"][name][1], self.font["glyf"][name].xMin)

    def test_overlap_flag_survives_save(self):
        g = self.font["glyf"][self.font.getBestCmap()[ord("A")]]
        self.assertTrue(g.flags[0] & 0x40)

    def test_nothing_drawn_raises(self):
        with self.assertRaises(ValueError):
            fc.build_font(fc.Project(), os.path.join(self.tmp.name, "e.ttf"))

    def test_rendered_font_matches_drawing(self):
        """Render the .ttf with FreeType and compare with a naive pen raster of the raw strokes."""
        from PIL import Image, ImageDraw, ImageFont
        W, H, BASE, ORIGIN = 700, 1100, 850, 100
        font = ImageFont.truetype(self.path, 1000)
        for ch in "AOLi.":
            strokes = self.project.strokes(ch)
            _, dx, _ = self.project.geometry(ch)

            real = Image.new("L", (W, H), 0)
            ImageDraw.Draw(real).text((ORIGIN, BASE), ch, font=font, fill=255, anchor="ls")

            ref = Image.new("L", (W, H), 0)
            d = ImageDraw.Draw(ref)
            for st in strokes:
                pts = [(ORIGIN + x + dx, BASE - y) for x, y in st["pts"]]
                r = st["w"] / 2
                if len(pts) > 1:
                    d.line(pts, fill=255, width=int(st["w"]), joint="curve")
                for x, y in pts:
                    d.ellipse((x - r, y - r, x + r, y + r), fill=255)

            from PIL import ImageChops, ImageFilter
            a = real.point(lambda v: 255 if v > 127 else 0)
            b = ref.point(lambda v: 255 if v > 127 else 0)
            union = ImageChops.lighter(a, b).histogram()[255]
            inter = ImageChops.darker(a, b).histogram()[255]
            self.assertGreater(union, 1000, f"{ch}: nothing rendered")
            self.assertGreater(inter / union, 0.94, f"{ch}: IoU {inter / union:.3f}")

            # Edge-bias-proof check: no pixel of either shape may be more than
            # 2 px (0.2% of an em) away from the other shape.
            grow = lambda im: im.filter(ImageFilter.MaxFilter(5))  # noqa: E731
            self.assertIsNone(ImageChops.subtract(a, grow(b)).getbbox(),
                              f"{ch}: font has ink that was not drawn")
            self.assertIsNone(ImageChops.subtract(b, grow(a)).getbbox(),
                              f"{ch}: drawn ink missing from font")


if __name__ == "__main__":
    unittest.main(verbosity=2)

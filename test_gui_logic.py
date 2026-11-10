"""
Drives drawfont.App's real event handlers with a stand-in for Tkinter, so the
GUI logic can be tested on machines with no display (CI, containers).
This does NOT test how it looks - only what happens when you click and draw.
"""
import os
import sys
import tempfile
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class Var:
    def __init__(self, master=None, value=None):
        self.v = value

    def get(self):
        return self.v

    def set(self, v):
        self.v = v

    def trace_add(self, *a, **k):
        pass


def install_fake_tk():
    tk = types.ModuleType("tkinter")
    for n in ("StringVar", "IntVar", "BooleanVar"):
        setattr(tk, n, type(n, (Var,), {}))
    for n in ("Tk", "Canvas", "Listbox", "Menu", "Frame", "Label", "Entry"):
        setattr(tk, n, mock.MagicMock(name=n))
    fd, mb, ttk = (types.ModuleType("tkinter." + n) for n in ("filedialog", "messagebox", "ttk"))
    ttk_mock = mock.MagicMock(name="ttk")
    for n in ("Frame", "Label", "Entry", "Button", "Radiobutton", "Checkbutton",
              "Scale", "Scrollbar", "LabelFrame"):
        setattr(ttk, n, getattr(ttk_mock, n))
    fd.askopenfilename = mock.Mock()
    fd.asksaveasfilename = mock.Mock()
    for n in ("showinfo", "showerror", "askyesnocancel"):
        setattr(mb, n, mock.Mock())
    tk.filedialog, tk.messagebox, tk.ttk = fd, mb, ttk
    sys.modules.update({"tkinter": tk, "tkinter.filedialog": fd,
                        "tkinter.messagebox": mb, "tkinter.ttk": ttk})
    return tk, fd, mb


TK, FD, MB = install_fake_tk()
import drawfont as df  # noqa: E402
import fontcore as fc  # noqa: E402


def ev(x, y):
    return types.SimpleNamespace(x=x, y=y)


class GuiLogicTests(unittest.TestCase):
    def setUp(self):
        for m in (MB.showinfo, MB.showerror, MB.askyesnocancel, FD.askopenfilename, FD.asksaveasfilename):
            m.reset_mock(return_value=False, side_effect=True)
        self.root = mock.MagicMock()
        self.app = df.App(self.root)
        self.app.listbox = mock.MagicMock()
        self.app.tool.set("pen")

    def draw(self, pts):
        self.app._press(ev(*pts[0]))
        for p in pts[1:]:
            self.app._motion(ev(*p))
        self.app._release(ev(*pts[-1]))

    def test_coordinate_roundtrip(self):
        for x, y in ((0, 0), (300, 700), (-20, -150)):
            fx, fy = df.to_font(*df.to_px(x, y))
            self.assertAlmostEqual(fx, x)
            self.assertAlmostEqual(fy, y)

    def test_baseline_is_at_font_y0_and_up_is_positive(self):
        self.draw([(100, df.Y0), (300, df.Y0)])                 # along the baseline
        pts = self.app.project.strokes("A")[0]["pts"]
        self.assertTrue(all(abs(p[1]) < 1e-6 for p in pts))
        self.draw([(100, df.Y0), (100, df.Y0 - 100)])           # drag UP the screen
        self.assertGreater(self.app.project.strokes("A")[1]["pts"][-1][1], 0)

    def test_drawing_creates_stroke_with_pen_width(self):
        self.app.project.settings["pen"] = 64
        self.draw([(100, 100), (150, 160), (220, 200)])
        st = self.app.project.strokes("A")
        self.assertEqual(len(st), 1)
        self.assertEqual(st[0]["w"], 64)
        self.assertEqual(len(st[0]["pts"]), 3)
        self.assertEqual(self.app.live, [])

    def test_tap_makes_a_dot(self):
        self.app.select_char(".")
        self.app._press(ev(200, 300))
        self.app._release(ev(200, 300))
        self.assertEqual(len(self.app.project.strokes(".")), 1)
        self.assertEqual(len(self.app.project.strokes(".")[0]["pts"]), 1)

    def test_pointer_clamped_to_canvas(self):
        self.draw([(-50, -50), (5000, 5000)])
        pts = self.app.project.strokes("A")[0]["pts"]
        fx0, fy0 = pts[0]
        self.assertAlmostEqual(fx0, df.to_font(0, 0)[0], places=1)

    def test_motion_without_press_is_ignored(self):
        self.app._motion(ev(10, 10))
        self.app._release(ev(10, 10))
        self.assertFalse(self.app.project.strokes("A"))

    def test_eraser_removes_only_the_stroke_under_it(self):
        self.draw([(100, 200), (300, 200)])
        self.draw([(100, 400), (300, 400)])
        self.app.tool.set("erase")
        self.app._press(ev(200, 201))
        self.app._release(ev(200, 201))
        self.assertEqual(len(self.app.project.strokes("A")), 1)
        self.assertAlmostEqual(self.app.project.strokes("A")[0]["pts"][0][1], df.to_font(0, 400)[1], delta=0.1)
        self.assertEqual(self.app.live, [])                     # eraser never starts a stroke

    def test_undo_switches_to_the_char_it_restores(self):
        self.draw([(100, 100), (200, 200)])
        self.app.select_char("B")
        self.draw([(100, 100), (200, 200)])
        self.app.undo()
        self.assertEqual(self.app.current, "B")
        self.app.undo()
        self.assertEqual(self.app.current, "A")
        self.assertFalse(self.app.project.strokes("A"))
        self.app.undo()                                         # nothing left: must not crash

    def test_clear_current_only(self):
        self.draw([(100, 100), (200, 200)])
        self.app.select_char("B")
        self.draw([(100, 100), (200, 200)])
        self.app.clear()
        self.assertFalse(self.app.project.strokes("B"))
        self.assertTrue(self.app.project.strokes("A"))

    def test_add_characters(self):
        self.app.add_entry = mock.MagicMock()
        self.app.add_entry.get.return_value = "é অ A"
        self.app.add_chars()
        self.assertIn("é", self.app.project.charset)
        self.assertIn("অ", self.app.project.charset)
        self.assertEqual(self.app.project.charset.count("A"), 1)   # no duplicate
        self.assertEqual(self.app.current, "é")

    def test_settings_apply_and_reflow(self):
        self.draw([(100, 200), (300, 200)])
        a1 = self.app.project.geometry("A")[2]
        self.app.v_side.set(120.4)
        self.app.v_smooth.set(5.0)
        self.app.v_mode.set("fixed")
        self.app._settings_changed()
        s = self.app.project.settings
        self.assertEqual((s["sidebearing"], s["smoothing"], s["spacing"]), (120, 5, "fixed"))
        self.assertEqual(self.app.project.geometry("A")[2], s["fixed_advance"])
        self.assertNotEqual(a1, s["fixed_advance"])

    def test_save_open_roundtrip_through_handlers(self):
        self.draw([(100, 100), (200, 250), (300, 100)])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "p.dfont.json")
            FD.asksaveasfilename.return_value = path
            self.assertTrue(self.app.save_project())
            self.assertFalse(self.app.project.dirty)
            MB.askyesnocancel.return_value = False
            FD.askopenfilename.return_value = path
            self.app.new_project()
            self.assertFalse(self.app.project.strokes("A"))
            self.app.open_project()
            self.assertEqual(len(self.app.project.strokes("A")), 1)
            FD.askopenfilename.return_value = __file__            # not a project file
            self.app.open_project()
            MB.showerror.assert_called_once()

    def test_export_writes_ttf(self):
        self.app.export_font()                                  # nothing drawn
        MB.showinfo.assert_called_once()
        self.draw([(100, 100), (200, 250), (300, 100)])
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "f.ttf")
            FD.asksaveasfilename.return_value = out
            self.app.export_font()
            self.assertTrue(os.path.getsize(out) > 300)
            from fontTools.ttLib import TTFont
            self.assertIn(ord("A"), TTFont(out).getBestCmap())
        MB.showerror.assert_not_called()

    def test_quit_respects_unsaved_changes(self):
        self.draw([(100, 100), (200, 200)])
        MB.askyesnocancel.return_value = None                   # user presses Cancel
        self.app.quit()
        self.root.destroy.assert_not_called()
        MB.askyesnocancel.return_value = False                  # "don't save"
        self.app.quit()
        self.root.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
